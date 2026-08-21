import pytest

from ev_api.allure_compat import feature, step, title
from ev_api.apis import AuthApi
from ev_api.assertions import assert_http_status, assert_json_code

pytestmark = [pytest.mark.api, pytest.mark.regression, pytest.mark.critical]


@feature("登录鉴权")
@title("无效登录凭据应返回401")
@pytest.mark.auth
def test_login_with_invalid_credentials_returns_401(anonymous_client):
    response = AuthApi(anonymous_client).login(
        "not_exists_user_for_api_test",
        "wrong_password",
    )
    assert_http_status(response, 401)
    assert_json_code(response, expected=401)


@feature("登录鉴权")
@title("正确客户账号登录应返回token")
@pytest.mark.auth
def test_customer_login_returns_token(anonymous_client, api_config):
    if not api_config.customer.username or not api_config.customer.password:
        pytest.fail("未配置客户测试账号，无法验证登录链路。", pytrace=False)

    with step("使用客户账号调用登录接口"):
        response = AuthApi(anonymous_client).login(
            api_config.customer.username,
            api_config.customer.password,
        )

    with step("断言返回业务成功和token"):
        payload = assert_json_code(response)
        assert payload.get("data", {}).get("token"), "登录响应未返回 token"
        assert payload.get("data", {}).get("username") == api_config.customer.username
