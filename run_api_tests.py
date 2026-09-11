from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

from ev_api.config import load_config
from ev_api.feishu import TestSummary, sanitize_report_reference, send_feishu_notification
from ev_api.run_context import create_test_run_context

ROOT_DIR = Path(__file__).resolve().parent
REPORTS_DIR = ROOT_DIR / "reports"
ALLURE_RESULTS = REPORTS_DIR / "allure-results"
JUNIT_XML = REPORTS_DIR / "junit.xml"


def _is_link(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def configure_output_encoding() -> None:
    """Keep local Windows and CI logs readable without changing test semantics."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EV sales API automation tests.")
    parser.add_argument(
        "--env", default="default", help="environment name in the selected config file"
    )
    parser.add_argument("--config", default=None, help="custom config yaml path")
    parser.add_argument("--no-feishu", action="store_true", help="do not send Feishu notification")
    args, pytest_args = parser.parse_known_args(argv)
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]
    args.pytest_args = pytest_args
    return args


def prepare_report_outputs() -> None:
    workspace_root = ROOT_DIR.resolve()
    reports_root = REPORTS_DIR.resolve()
    try:
        reports_root.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError(
            f"Refusing to clean reports outside the project root {workspace_root}: {reports_root}"
        ) from exc
    if reports_root == workspace_root:
        raise ValueError(
            f"Refusing to use the project root itself as the reports directory: {workspace_root}"
        )

    if _is_link(REPORTS_DIR):
        raise ValueError(f"Refusing to clean a linked reports directory: {REPORTS_DIR}")

    for output in (ALLURE_RESULTS, JUNIT_XML):
        if _is_link(output):
            raise ValueError(f"Refusing to clean a linked report output: {output}")
        resolved = output.resolve()
        try:
            resolved.relative_to(reports_root)
        except ValueError as exc:
            raise ValueError(
                f"Refusing to clean report output outside {reports_root}: {resolved}"
            ) from exc
        if resolved == reports_root:
            raise ValueError(f"Refusing to clean the reports root itself: {reports_root}")

    if ALLURE_RESULTS.is_dir():
        shutil.rmtree(ALLURE_RESULTS)
    elif ALLURE_RESULTS.exists():
        ALLURE_RESULTS.unlink()
    if JUNIT_XML.exists():
        JUNIT_XML.unlink()
    ALLURE_RESULTS.mkdir(parents=True, exist_ok=True)


def parse_junit(path: Path, duration_seconds: float, env_name: str, report_url: str) -> TestSummary:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        raise ValueError("JUnit report is missing, unreadable, or malformed.") from None
    if root.tag not in {"testsuite", "testsuites"}:
        raise ValueError("JUnit report has an unsupported root element.")
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    total = failed = skipped = errors = 0
    for suite in suites:
        try:
            counts = [int(suite.attrib[key]) for key in ("tests", "failures", "errors", "skipped")]
        except (KeyError, ValueError):
            raise ValueError("JUnit report contains missing or invalid counters.") from None
        if any(count < 0 for count in counts) or sum(counts[1:]) > counts[0]:
            raise ValueError("JUnit report contains inconsistent counters.")
        total += counts[0]
        failed += counts[1]
        errors += counts[2]
        skipped += counts[3]
    failed += errors
    passed = max(total - failed - skipped, 0)
    return TestSummary(
        "新能源汽车销售系统接口自动化",
        env_name,
        total,
        passed,
        failed,
        skipped,
        duration_seconds,
        report_url,
    )


def main(argv: Sequence[str] | None = None) -> int:
    configure_output_encoding()
    args = parse_args(argv)
    prepare_report_outputs()
    config = load_config(args.env, args.config)
    test_run = create_test_run_context()

    command = [sys.executable, "-m", "pytest"]
    command.extend(args.pytest_args)
    command.append(f"--env={args.env}")
    if args.config:
        command.append(f"--config={args.config}")
    # Keep runner-owned outputs last so forwarded pytest arguments cannot move
    # reports outside the validated directory or make the summary read stale files.
    command.extend([f"--junitxml={JUNIT_XML}", f"--alluredir={ALLURE_RESULTS}"])

    start = time.time()
    process_env = os.environ.copy()
    process_env["EV_TEST_RUN_ID"] = test_run.run_id
    process_env["PYTHONIOENCODING"] = "utf-8"
    process_env["PYTHONUTF8"] = "1"
    exit_code = subprocess.call(command, cwd=ROOT_DIR, env=process_env)
    duration = time.time() - start

    local_report_reference = ALLURE_RESULTS.relative_to(ROOT_DIR).as_posix()
    report_reference = sanitize_report_reference(config.feishu.report_url or local_report_reference)
    try:
        summary = parse_junit(JUNIT_XML, duration, args.env, report_reference)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        summary = TestSummary(
            "新能源汽车销售系统接口自动化", args.env, 0, 0, 0, 0, duration, report_reference
        )
    summary.run_id = test_run.run_id
    effective_exit_code = exit_code
    if exit_code == 0 and (summary.passed == 0 or summary.skipped > 0 or summary.failed > 0):
        effective_exit_code = 1
        print(
            "The run has missing results, zero passes, skipped scenarios, failures or errors; "
            "refusing a successful exit.",
            file=sys.stderr,
        )
    summary.exit_code = effective_exit_code
    print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))

    if not args.no_feishu and config.feishu.webhook:
        try:
            send_feishu_notification(config.feishu.webhook, summary)
        except Exception as exc:
            print(
                f"Feishu notification failed ({type(exc).__name__}); pytest exit code preserved.",
                file=sys.stderr,
            )
        else:
            print("Feishu notification sent.")
    elif not args.no_feishu:
        print("Feishu webhook is empty, notification skipped.")

    return effective_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
