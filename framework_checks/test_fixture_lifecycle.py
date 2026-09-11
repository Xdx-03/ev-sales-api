"""Real pytest fixture setup/teardown with isolated transport substitutes."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("fixture", ["anonymous_client", "customer_client", "admin_client"])
@pytest.mark.parametrize("mode", ["pass", "body-failure", "setup-failure"])
def test_clients_close_on_setup_body_and_teardown(tmp_path, fixture, mode):
    source = (PROJECT / "tests" / "conftest.py").read_text(encoding="utf-8")
    substitute = f"""
import json
from pathlib import Path
from types import SimpleNamespace
import requests

MODE = {mode!r}
TARGET = {fixture!r}
class ApiClient:
    counter = 0
    def __init__(self, *args, **kwargs):
        type(self).counter += 1
        self.identifier = type(self).counter
    def close(self):
        with Path("closed.txt").open("a", encoding="utf-8") as stream:
            stream.write(str(self.identifier) + "\\n")
    def set_token(self, token): pass
    def get(self, path):
        response = requests.Response()
        response.status_code = 200
        code = 500 if MODE == "setup-failure" and TARGET == "anonymous_client" else 200
        response._content = json.dumps({{"code": code}}).encode()
        return response
    def post(self, path, **kwargs):
        response = requests.Response()
        response.status_code = 200
        code = 401 if MODE == "setup-failure" else 200
        response._content = json.dumps({{"code": code, "data": {{"token": "synthetic"}}}}).encode()
        return response

@pytest.fixture(scope="session")
def api_config():
    account = SimpleNamespace(username="synthetic", password="synthetic")
    return SimpleNamespace(base_url="http://127.0.0.1", timeout=1, customer=account, admin=account)
"""
    (tmp_path / "conftest.py").write_text(source + substitute, encoding="utf-8")
    assertion = (
        "assert False, 'synthetic test failure'" if mode == "body-failure" else "assert True"
    )
    (tmp_path / "test_lifecycle.py").write_text(
        f"def test_first({fixture}): {assertion}\ndef test_second({fixture}): {assertion}\n",
        encoding="utf-8",
    )
    environment = {key: value for key, value in os.environ.items() if not key.startswith("EV_")}
    environment.update(
        PYTHONPATH=str(PROJECT), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONIOENCODING="utf-8"
    )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=tmp_path,
        env=environment,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert (completed.returncode == 0) == (mode == "pass"), completed.stdout + completed.stderr
    closed = (tmp_path / "closed.txt").read_text(encoding="utf-8").splitlines()
    # Anonymous client is immutable and shared; authenticated clients belong to each test.
    assert len(closed) == (1 if fixture == "anonymous_client" else 3)
    assert len(set(closed)) == len(closed)
    if mode == "body-failure":
        assert "synthetic test failure" in completed.stdout
