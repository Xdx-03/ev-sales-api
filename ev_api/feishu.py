from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from ev_api.redaction import redact_text


@dataclass
class TestSummary:
    """Minimal test-run result used by console and Feishu notifications."""

    project: str
    env: str
    total: int
    passed: int
    failed: int
    skipped: int
    duration_seconds: float
    report_url: str = ""
    run_id: str = ""
    exit_code: int = 0

    @property
    def pass_rate(self) -> str:
        if self.total == 0:
            return "0.00%"
        return f"{self.passed / self.total * 100:.2f}%"

    @property
    def successful(self) -> bool:
        return self.exit_code == 0 and self.failed == 0 and self.passed > 0


def sanitize_report_reference(value: str) -> str:
    """Remove URL credentials, query strings, and fragments before logs/notifications."""
    if not value:
        return value
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return redact_text(value)

    hostname = parsed.hostname
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    try:
        port = parsed.port
    except ValueError:
        return redact_text(value)
    if port:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def build_message(summary: TestSummary) -> dict[str, Any]:
    status = "通过" if summary.successful else "失败"
    lines = [
        f"项目：{summary.project}",
        f"环境：{summary.env}",
        f"运行ID：{summary.run_id or '-'}",
        f"结果：{status}",
        f"总数：{summary.total}",
        f"通过：{summary.passed}",
        f"失败：{summary.failed}",
        f"跳过：{summary.skipped}",
        f"通过率：{summary.pass_rate}",
        f"耗时：{summary.duration_seconds:.2f}s",
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    if summary.report_url:
        lines.append(f"Allure报告：{sanitize_report_reference(summary.report_url)}")
    return {"msg_type": "text", "content": {"text": "\n".join(lines)}}


def send_feishu_notification(webhook: str, summary: TestSummary, timeout: int = 10) -> bool:
    if not webhook:
        return False
    response = requests.post(
        webhook,
        data=json.dumps(build_message(summary), ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    return True
