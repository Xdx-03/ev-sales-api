import pytest

from ev_api.allure_compat import feature, step, title
from ev_api.apis import AiApi
from ev_api.assertions import (
    assert_ai_history,
    assert_ai_reply,
    assert_json_code,
    assert_unauthorized_or_forbidden,
)

pytestmark = [pytest.mark.api, pytest.mark.regression]


@feature("AI导购")
@title("未登录用户不能访问AI导购")
@pytest.mark.ai
@pytest.mark.permission
def test_ai_chat_rejects_anonymous_user(anonymous_client):
    response = AiApi(anonymous_client).send_message("推荐一款家用新能源车")
    assert_unauthorized_or_forbidden(response)


@feature("AI导购")
@title("AI导购应拒绝空问题")
@pytest.mark.ai
@pytest.mark.boundary
def test_ai_chat_rejects_blank_message(customer_client):
    response = AiApi(customer_client).send_message("   ")
    payload = assert_json_code(response, expected=400)
    assert "请输入" in (payload.get("message") or payload.get("msg") or "")


@feature("AI导购")
@title("客户咨询后应返回回答并保存会话历史")
@pytest.mark.ai
@pytest.mark.business
@pytest.mark.destructive
@pytest.mark.slow
def test_ai_chat_reply_and_history(
    customer_client,
    api_config,
    test_run,
):
    question = test_run.tag(api_config.business_data.ai_question)
    min_reply_length = api_config.business_data.ai_min_reply_length
    api = AiApi(customer_client)

    with step("发送AI购车咨询"):
        chat_payload = assert_json_code(api.send_message(question))
        chat_data = chat_payload.get("data")

    with step("校验会话标识和非空回复"):
        session_id, reply = assert_ai_reply(chat_data, min_reply_length)

    with step("根据sessionId查询当前用户的会话历史"):
        history_payload = assert_json_code(api.get_history(session_id))
        records = history_payload.get("data")

    with step("校验问题与回复已写入会话历史"):
        assert_ai_history(records, session_id, question, reply)


@feature("AI导购")
@title("查询历史时sessionId不能为空")
@pytest.mark.ai
@pytest.mark.boundary
def test_ai_history_requires_session_id(customer_client):
    response = AiApi(customer_client).get_history("")
    payload = assert_json_code(response, expected=400)
    assert "sessionId" in (payload.get("message") or payload.get("msg") or "")
