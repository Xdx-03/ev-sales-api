import pytest

from ev_api.allure_compat import feature, title
from ev_api.apis import AfterSalesApi, CustomerApi, OrderApi, TestDriveApi
from ev_api.assertions import assert_json_code, assert_table_response

pytestmark = [pytest.mark.api, pytest.mark.regression]


@feature("客户业务列表")
@title("客户可查询自己的订单列表")
@pytest.mark.business
def test_customer_order_list_returns_table_structure(customer_client):
    response = OrderApi(customer_client).list_my_orders()
    assert_table_response(response)


@feature("客户业务列表")
@title("客户可查询自己的试驾预约列表")
@pytest.mark.business
def test_customer_test_drive_list_returns_table_structure(customer_client):
    response = TestDriveApi(customer_client).list_my_appointments()
    assert_table_response(response)


@feature("客户业务列表")
@title("客户可查询自己的售后工单列表")
@pytest.mark.business
def test_customer_ticket_list_returns_table_structure(customer_client):
    response = AfterSalesApi(customer_client).list_my_tickets()
    assert_table_response(response)


@feature("客户业务列表")
@title("客户可查询个人资料")
@pytest.mark.business
def test_customer_profile_returns_current_user(customer_client):
    response = CustomerApi(customer_client).get_my_profile()
    assert_json_code(response)
