from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import requests

from ev_api.redaction import redact_sensitive, redact_text


def _safe_body(response: requests.Response) -> str:
    return redact_text(response.text)[:5000]


def assert_http_status(response: requests.Response, expected: int | Iterable[int]) -> None:
    expected_set = {expected} if isinstance(expected, int) else set(expected)
    assert response.status_code in expected_set, (
        f"Expected HTTP status {sorted(expected_set)}, got {response.status_code}. Body: {_safe_body(response)}"
    )


def assert_json_code(response: requests.Response, expected: int = 200) -> dict[str, Any]:
    payload = response.json()
    assert payload.get("code") == expected, (
        f"Expected business code {expected}, got {redact_sensitive(payload)}. Body: {_safe_body(response)}"
    )
    return payload


def assert_json_code_in(response: requests.Response, expected: Iterable[int]) -> dict[str, Any]:
    expected_set = set(expected)
    payload = response.json()
    assert payload.get("code") in expected_set, (
        f"Expected business code in {sorted(expected_set)}, got "
        f"{redact_sensitive(payload)}. Body: {_safe_body(response)}"
    )
    return payload


def assert_table_response(response: requests.Response) -> dict[str, Any]:
    payload = response.json()
    safe_body = _safe_body(response)
    assert payload.get("code") == 200, (
        f"Expected table code 200, got {redact_sensitive(payload)}. Body: {safe_body}"
    )
    assert "rows" in payload, f"Table response must contain rows. Body: {safe_body}"
    assert "total" in payload, f"Table response must contain total. Body: {safe_body}"
    assert isinstance(payload["rows"], list), f"rows must be a list. Body: {safe_body}"
    return payload


def assert_unauthorized_or_forbidden(response: requests.Response) -> dict[str, Any]:
    assert_http_status(response, {401, 403})
    payload = response.json()
    assert payload.get("code") in {401, 403}, (
        f"Expected business code 401/403, got {redact_sensitive(payload)}"
    )
    return payload
