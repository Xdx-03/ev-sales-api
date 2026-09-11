from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import requests


def _json_object(response: requests.Response) -> dict[str, Any]:
    """Reject malformed envelopes without including response bodies or credentials."""
    try:
        payload = response.json()
    except ValueError:
        raise AssertionError("Response must contain valid JSON (body omitted).") from None
    assert isinstance(payload, dict), "Response JSON must be an object (body omitted)."
    return payload


def assert_http_status(response: requests.Response, expected: int | Iterable[int]) -> None:
    expected_set = {expected} if isinstance(expected, int) else set(expected)
    assert response.status_code in expected_set, (
        f"Expected HTTP status {sorted(expected_set)}, got {response.status_code}."
    )


def assert_json_code(response: requests.Response, expected: int = 200) -> dict[str, Any]:
    if expected == 200:
        assert_http_status(response, 200)
    payload = _json_object(response)
    actual = payload.get("code")
    safe_code = actual if isinstance(actual, int) else "missing or invalid type"
    assert actual == expected, f"Expected business code {expected}, got {safe_code} (body omitted)."
    return payload


def assert_json_code_in(response: requests.Response, expected: Iterable[int]) -> dict[str, Any]:
    expected_set = set(expected)
    payload = _json_object(response)
    actual = payload.get("code")
    safe_code = actual if isinstance(actual, int) else "missing or invalid type"
    assert isinstance(actual, int) and actual in expected_set, (
        f"Expected business code in {sorted(expected_set)}, got {safe_code} (body omitted)."
    )
    if payload["code"] == 200:
        assert_http_status(response, 200)
    return payload


def assert_table_response(response: requests.Response) -> dict[str, Any]:
    payload = assert_json_code(response)
    assert "rows" in payload, "Table response must contain rows."
    assert "total" in payload, "Table response must contain total."
    assert isinstance(payload["rows"], list), "rows must be a list."
    return payload


def assert_unauthorized_or_forbidden(response: requests.Response) -> dict[str, Any]:
    assert_http_status(response, {401, 403})
    return assert_json_code_in(response, {401, 403})


def assert_ai_reply(data: Any, min_reply_length: int) -> tuple[str, str]:
    """Check transport-level AI reply shape and known backend fallbacks, not factuality."""
    assert isinstance(data, dict), "AI response data must be an object."
    session_id = data.get("sessionId")
    reply = data.get("reply")
    assert isinstance(session_id, str) and len(session_id) == 32, "Invalid AI session identifier."
    assert isinstance(reply, str), "AI reply must be a string."
    reply = reply.strip()
    assert reply, "AI reply must not be empty."
    assert len(reply) >= min_reply_length, "AI reply is shorter than the configured minimum."
    # Confirmed AiServiceImpl fallbacks; deliberately not a general language/quality heuristic.
    assert reply != "抱歉，我暂时没有生成有效回复，请稍后再试。", (
        "AI returned the empty-reply fallback."
    )
    assert not (
        reply.startswith("抱歉，本地 AI 服务暂时不可用，请确认 Ollama 已启动且模型 ")
        and reply.endswith(" 可以正常运行。")
    ), "AI returned the unavailable-service fallback."
    return session_id, reply


def assert_ai_history(records: Any, session_id: str, question: str, reply: str) -> None:
    """Verify that the same session persisted the exact question and textual answer."""
    assert isinstance(records, list) and records, "AI history must be a non-empty list."
    latest = records[-1]
    assert isinstance(latest, dict), "AI history record must be an object."
    assert latest.get("sessionId") == session_id, "AI history session does not match."
    assert latest.get("question") == question, "AI history question does not match."
    answer = latest.get("answer")
    assert isinstance(answer, str), "AI history answer must be a string."
    assert answer.strip() == reply, "AI history answer does not match the reply."
