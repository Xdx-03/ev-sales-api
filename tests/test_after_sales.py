import pytest

from ev_api.allure_compat import feature, title
from ev_api.apis import AfterSalesApi
from ev_api.assertions import assert_json_code, assert_table_response

pytestmark = [pytest.mark.api, pytest.mark.regression]


@feature("售后工单")
@title("客户创建售后工单后应可在列表回查")
@pytest.mark.business
@pytest.mark.destructive
def test_after_sales_ticket_create_and_query(customer_client, api_config, test_run):
    api = AfterSalesApi(customer_client)
    response = api.create_ticket(
        "维修",
        test_run.tag("售后工单"),
        api_config.business_data.vin,
    )
    created = assert_json_code(response)["data"]
    assert created.get("id") and created.get("ticketNo")
    assert created.get("status") == 10
    rows = assert_table_response(api.list_my_tickets(page_size=50))["rows"]
    assert any(item.get("id") == created["id"] for item in rows)
