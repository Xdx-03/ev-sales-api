import pytest

from ev_api.allure_compat import feature, step, title
from ev_api.apis import CustomerApi
from ev_api.assertions import assert_json_code

pytestmark = [pytest.mark.api, pytest.mark.regression, pytest.mark.database]


@feature("数据库一致性")
@title("客户资料 API 状态应与数据库记录一致")
def test_customer_profile_state_matches_database(customer_client, database_client):
    with step("通过客户资料 API 获取当前记录"):
        profile = assert_json_code(CustomerApi(customer_client).get_my_profile())["data"]

    with step("使用只读账号查询相同客户记录"):
        database_state = database_client.get_customer_profile_state(profile["id"])

    with step("比较非敏感状态字段"):
        if database_state is None:
            pytest.fail("数据库中未找到 API 返回的客户资料记录", pytrace=False)

        comparisons = (
            ("record identity", database_state.get("id"), profile.get("id")),
            ("deleted", database_state.get("deleted"), profile.get("deleted")),
            ("stage", database_state.get("stage"), profile.get("stage")),
            (
                "intent level",
                database_state.get("intentLevel"),
                profile.get("intentLevel"),
            ),
        )
        for field_name, database_value, api_value in comparisons:
            if database_value != api_value:
                pytest.fail(
                    f"API 与数据库的客户状态字段不一致：{field_name}",
                    pytrace=False,
                )
