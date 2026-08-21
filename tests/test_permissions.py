import pytest

from ev_api.allure_compat import feature, title
from ev_api.assertions import assert_unauthorized_or_forbidden

pytestmark = [pytest.mark.api, pytest.mark.regression, pytest.mark.critical]


@feature("权限拦截")
@pytest.mark.permission
@pytest.mark.parametrize(
    ("name", "method", "path"),
    [
        ("未登录查询我的订单", "GET", "/sale/order/my-list"),
        ("未登录查询我的试驾", "GET", "/cust/test-drive/my-list"),
        ("未登录查询我的售后工单", "GET", "/after-sales/ticket/my-list"),
        ("未登录访问后台用户", "GET", "/sys/user/list"),
    ],
)
def test_protected_apis_reject_anonymous_user(anonymous_client, name, method, path):
    response = anonymous_client.request(method, path)
    assert_unauthorized_or_forbidden(response)


@feature("权限拦截")
@title("客户账号访问后台用户列表应被拒绝")
@pytest.mark.permission
def test_customer_access_to_system_user_list_is_forbidden(customer_client):
    response = customer_client.get("/sys/user/list")
    assert_unauthorized_or_forbidden(response)
