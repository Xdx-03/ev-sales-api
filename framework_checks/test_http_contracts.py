"""Framework contracts exercised over loopback HTTP; no business service is contacted."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
import requests

from ev_api.apis.auth_api import AuthApi
from ev_api.assertions import (
    assert_ai_history,
    assert_ai_reply,
    assert_json_code,
    assert_json_code_in,
    assert_table_response,
    assert_unauthorized_or_forbidden,
)
from ev_api.client import ApiClient


@pytest.fixture
def http_endpoint() -> Iterator[tuple[str, dict[str, Any]]]:
    state: dict[str, Any] = {"status": 200, "body": {"code": 200}, "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state["requests"].append((self.path, self.headers.get("Authorization")))
            body = state["body"]
            raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        do_POST = do_GET

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("status", [201, 400, 500])
@pytest.mark.parametrize("contract", [assert_json_code, assert_table_response])
def test_success_requires_http_200(http_endpoint, status, contract):
    url, state = http_endpoint
    state.update(status=status, body={"code": 200, "rows": [], "total": 0})
    with ApiClient(url) as client, pytest.raises(AssertionError, match="Expected HTTP status"):
        contract(client.get("/reply"))


@pytest.mark.parametrize("body", ["not JSON secret-sentinel", [], None, 42, '"secret-sentinel"'])
@pytest.mark.parametrize(
    "contract,status",
    [
        (assert_json_code, 200),
        (assert_table_response, 200),
        (lambda response: assert_json_code_in(response, {200, 400}), 200),
        (assert_unauthorized_or_forbidden, 401),
    ],
)
def test_malformed_envelopes_fail_safely(http_endpoint, body, contract, status):
    url, state = http_endpoint
    state.update(status=status, body=body)
    with ApiClient(url) as client, pytest.raises(AssertionError, match="JSON") as error:
        contract(client.get("/reply"))
    assert "secret-sentinel" not in str(error.value)


@pytest.mark.parametrize("code", [400, 404])
def test_error_business_codes_do_not_imply_http_error(http_endpoint, code):
    url, state = http_endpoint
    state["body"] = {"code": code}
    with ApiClient(url) as client:
        response = client.get("/reply")
        assert assert_json_code(response, code)["code"] == code
        assert assert_json_code_in(response, {200, code})["code"] == code


def test_allowed_success_code_still_requires_http_200(http_endpoint):
    url, state = http_endpoint
    state.update(status=500, body={"code": 200})
    with ApiClient(url) as client, pytest.raises(AssertionError, match="HTTP"):
        assert_json_code_in(client.get("/reply"), {200, 400})


def test_table_contract_accepts_valid_empty_page(http_endpoint):
    url, state = http_endpoint
    state["body"] = {"code": 200, "rows": [], "total": 0}
    with ApiClient(url) as client:
        assert assert_table_response(client.get("/reply"))["rows"] == []


@pytest.mark.parametrize("code", [[], {}, "200"])
def test_allowed_codes_reject_invalid_code_types_safely(http_endpoint, code):
    url, state = http_endpoint
    state["body"] = {"code": code, "token": "secret-sentinel"}
    with ApiClient(url) as client, pytest.raises(AssertionError) as error:
        assert_json_code_in(client.get("/reply"), {200, 400})
    assert "secret-sentinel" not in str(error.value)


@pytest.mark.parametrize(
    "status,body",
    [
        (500, {"code": 200, "data": {"token": "synthetic-token"}}),
        (200, {"code": 401, "data": {"token": "synthetic-token"}}),
        (200, {"code": 200, "data": []}),
        *[(200, {"code": 200, "data": {"token": value}}) for value in (None, "", " ", 123, [])],
    ],
)
def test_authentication_rejects_invalid_success_and_token(http_endpoint, status, body):
    url, state = http_endpoint
    state.update(status=status, body=body)
    with ApiClient(url) as client:
        with pytest.raises(AssertionError) as error:
            AuthApi(client).authenticate("synthetic-user", "synthetic-password")
        assert "Authorization" not in client.session.headers
        assert "synthetic-token" not in str(error.value)
        assert "synthetic-password" not in str(error.value)


def test_authentication_attaches_string_token_on_followup_request(http_endpoint):
    url, state = http_endpoint
    state["body"] = {"code": 200, "data": {"token": "synthetic-token"}}
    with ApiClient(url) as client:
        assert (
            AuthApi(client).authenticate("synthetic-user", "synthetic-password")
            == "synthetic-token"
        )
        client.get("/authenticated")
    assert state["requests"][-1] == ("/authenticated", "Bearer synthetic-token")


@pytest.mark.parametrize("raise_in_body", [False, True])
def test_client_context_closes_session_on_success_and_exception(monkeypatch, raise_in_body):
    closed = []
    original = requests.Session.close

    def close(session):
        closed.append(session)
        original(session)

    monkeypatch.setattr(requests.Session, "close", close)
    try:
        with ApiClient("http://127.0.0.1") as client:
            if raise_in_body:
                raise RuntimeError("synthetic body failure")
    except RuntimeError:
        assert raise_in_body
    assert closed == [client.session]


@pytest.mark.parametrize("reply", [None, 123456, ["long reply"], {"text": "long reply"}, " "])
def test_ai_reply_rejects_nontext_and_empty_content(reply):
    with pytest.raises(AssertionError):
        assert_ai_reply({"sessionId": "a" * 32, "reply": reply}, 3)


def test_ai_reply_remains_nonempty_when_minimum_is_zero():
    with pytest.raises(AssertionError, match="empty"):
        assert_ai_reply({"sessionId": "a" * 32, "reply": "   "}, 0)


@pytest.mark.parametrize(
    "reply",
    [
        "抱歉，我暂时没有生成有效回复，请稍后再试。",
        "抱歉，本地 AI 服务暂时不可用，请确认 Ollama 已启动且模型 synthetic-model 可以正常运行。",
    ],
)
def test_ai_normal_conversation_rejects_confirmed_backend_fallbacks(reply):
    with pytest.raises(AssertionError, match="fallback"):
        assert_ai_reply({"sessionId": "a" * 32, "reply": reply}, 3)


@pytest.mark.parametrize("data", [None, [], {"sessionId": 123, "reply": "text"}])
def test_ai_reply_requires_object_and_session(data):
    with pytest.raises(AssertionError):
        assert_ai_reply(data, 3)


def test_ai_history_matches_text_reply_and_question():
    session, reply = assert_ai_reply({"sessionId": "a" * 32, "reply": " 正常车型说明 "}, 3)
    assert_ai_history(
        [{"sessionId": session, "question": "synthetic", "answer": reply}],
        session,
        "synthetic",
        reply,
    )


@pytest.mark.parametrize(
    "records",
    [
        None,
        [],
        {},
        [None],
        [{"sessionId": "b" * 32, "question": "synthetic", "answer": "12345"}],
        [{"sessionId": "a" * 32, "question": "different", "answer": "12345"}],
        [{"sessionId": "a" * 32, "question": "synthetic", "answer": 12345}],
        [{"sessionId": "a" * 32, "question": "synthetic", "answer": "different"}],
    ],
)
def test_ai_history_rejects_invalid_shape_and_mismatch(records):
    with pytest.raises(AssertionError):
        assert_ai_history(records, "a" * 32, "synthetic", "12345")
