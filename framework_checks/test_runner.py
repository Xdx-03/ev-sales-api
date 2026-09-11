"""Run the public CLI against temporary synthetic pytest suites, never business data."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import run_api_tests as runner

PROJECT = Path(__file__).resolve().parents[1]


def run_synthetic_suite(
    tmp_path: Path, mode: str, local_config: str = "staging: {}\n"
) -> subprocess.CompletedProcess[str]:
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    config_path = tmp_path / "synthetic-env.yaml"
    config_path.write_text("default: {}\n", encoding="utf-8")
    # Model an unrelated local config without opening or modifying the user's file.
    (tmp_path / "local-env.yaml").write_text(local_config, encoding="utf-8")
    test_body = {
        "zero": "",
        "skip": "import pytest\ndef test_example(): pytest.skip('synthetic skip')\n",
        "failure": "def test_example(): assert False, 'synthetic failure'\n",
    }.get(mode, "def test_example(): assert True\n")
    (tmp_path / "test_synthetic.py").write_text(test_body, encoding="utf-8")
    (tmp_path / "conftest.py").write_text(
        "import pytest\nfrom pathlib import Path\n"
        "def pytest_addoption(parser):\n"
        "    parser.addoption('--env')\n    parser.addoption('--config')\n"
        "    parser.addoption('--alluredir')\n"
        "@pytest.hookimpl(trylast=True)\n"
        "def pytest_sessionfinish(session):\n"
        "    path = Path(session.config.getoption('xmlpath'))\n"
        f"    mode = {mode!r}\n"
        "    if mode == 'missing': path.unlink(missing_ok=True)\n"
        "    if mode in {'malformed', 'malformed-exit-seven'}:\n"
        "        path.write_text('<broken', encoding='utf-8')\n"
        "    if mode == 'invalid-count':\n"
        "        path.write_text('<testsuite tests=\"bad\"/>', encoding='utf-8')\n"
        "    if mode in {'reported-failure', 'reported-error'}:\n"
        "        attribute = 'failures' if mode == 'reported-failure' else 'errors'\n"
        "        fields = dict(tests=2, failures=0, errors=0, skipped=0)\n"
        "        fields[attribute] = 1\n"
        "        counters = ' '.join(f'{key}=\"{value}\"' for key, value in fields.items())\n"
        "        path.write_text(f'<testsuite {counters}/>', encoding='utf-8')\n"
        "    if mode in {'exit-seven', 'malformed-exit-seven'}: session.exitstatus = 7\n",
        encoding="utf-8",
    )
    driver = (
        "import sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(PROJECT)!r})\n"
        "import run_api_tests as runner\n"
        "import ev_api.config as config\n"
        "config.DEFAULT_CONFIG_PATH = Path.cwd() / 'local-env.yaml'\n"
        "runner.ROOT_DIR = Path.cwd()\n"
        "runner.REPORTS_DIR = Path.cwd() / 'reports'\n"
        "runner.ALLURE_RESULTS = runner.REPORTS_DIR / 'allure-results'\n"
        "runner.JUNIT_XML = runner.REPORTS_DIR / 'junit.xml'\n"
        "raise SystemExit(runner.main(sys.argv[1:]))\n"
    )
    environment = {key: value for key, value in os.environ.items() if not key.startswith("EV_")}
    environment.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [
            sys.executable,
            "-c",
            driver,
            "--no-feishu",
            "--config",
            str(config_path),
            "-q",
            "--junitxml=unowned.xml",
            "--alluredir=unowned-allure",
        ],
        cwd=tmp_path,
        env=environment,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("success", 0),
        ("zero", 5),
        ("skip", 1),
        ("failure", 1),
        ("missing", 1),
        ("malformed", 1),
        ("invalid-count", 1),
        ("reported-failure", 1),
        ("reported-error", 1),
        ("exit-seven", 7),
        ("malformed-exit-seven", 7),
    ],
)
def test_cli_preserves_real_exit_and_rejects_incomplete_reports(tmp_path, mode, expected):
    completed = run_synthetic_suite(tmp_path, mode)
    assert completed.returncode == expected, completed.stdout + completed.stderr
    assert not (tmp_path / "unowned.xml").exists()
    assert "Feishu notification sent" not in completed.stdout
    if mode == "success":
        assert (tmp_path / "reports" / "junit.xml").is_file()


@pytest.mark.parametrize("local_config", ["staging: {}\n", "default: [invalid YAML\n"])
def test_cli_synthetic_config_is_independent_of_local_configuration(tmp_path, local_config):
    completed = run_synthetic_suite(tmp_path, "success", local_config)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (tmp_path / "reports" / "junit.xml").is_file()
    assert (tmp_path / "local-env.yaml").read_text(encoding="utf-8") == local_config


def configure_outputs(monkeypatch, root, allure, junit):
    monkeypatch.setattr(runner, "ROOT_DIR", root)
    monkeypatch.setattr(runner, "REPORTS_DIR", root / "reports")
    monkeypatch.setattr(runner, "ALLURE_RESULTS", allure)
    monkeypatch.setattr(runner, "JUNIT_XML", junit)


def test_cleanup_validates_all_targets_before_deleting(monkeypatch, tmp_path):
    root = tmp_path / "project"
    allure = root / "reports" / "allure-results"
    allure.mkdir(parents=True)
    evidence = allure / "keep.txt"
    evidence.write_text("synthetic evidence", encoding="utf-8")
    configure_outputs(monkeypatch, root, allure, tmp_path / "outside.xml")
    with pytest.raises(ValueError, match="outside"):
        runner.prepare_report_outputs()
    assert evidence.is_file()


@pytest.mark.parametrize("linked_output", ["reports", "allure"])
def test_cleanup_rejects_actual_directory_link(monkeypatch, tmp_path, linked_output):
    import importlib

    root = tmp_path / "project"
    root.mkdir()
    target = root / "retained"
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("synthetic evidence", encoding="utf-8")
    allure = root / "reports" / "allure-results"
    link = root / "reports" if linked_output == "reports" else allure
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        importlib.import_module("_winapi").CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)
    configure_outputs(monkeypatch, root, allure, root / "reports" / "junit.xml")
    try:
        with pytest.raises(ValueError, match="linked"):
            runner.prepare_report_outputs()
        assert sentinel.read_text(encoding="utf-8") == "synthetic evidence"
    finally:
        # Remove the link itself, never recursively traverse the retained directory.
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()


def test_cleanup_rejects_windows_reparse_output(monkeypatch, tmp_path):
    import stat
    from types import SimpleNamespace

    root = tmp_path / "project"
    root.mkdir()
    linked = root / "reports" / "allure-results"
    configure_outputs(monkeypatch, root, linked, root / "reports" / "junit.xml")
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        if path == linked:
            return SimpleNamespace(
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT, st_mode=stat.S_IFDIR
            )
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(ValueError, match="linked"):
        runner.prepare_report_outputs()
