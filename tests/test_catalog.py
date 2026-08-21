import pytest

from ev_api.allure_compat import feature, step, title
from ev_api.apis import CatalogApi
from ev_api.assertions import assert_json_code, assert_table_response

pytestmark = [pytest.mark.api, pytest.mark.regression, pytest.mark.critical]


@feature("公开接口冒烟")
@pytest.mark.smoke
@pytest.mark.parametrize(
    ("name", "operation"),
    [
        ("公开品牌列表", CatalogApi.list_brands),
        ("公开车型列表", CatalogApi.list_models),
        ("公开SKU列表", CatalogApi.list_skus),
        ("公开文章列表", CatalogApi.list_articles),
    ],
)
def test_public_list_endpoints_return_table_structure(anonymous_client, name, operation):
    catalog_api = CatalogApi(anonymous_client)
    with step(f"请求{name}"):
        response = operation(catalog_api)

    with step("断言公开列表接口返回成功"):
        assert_table_response(response)


@feature("库存公开接口")
@title("公开库存可用查询应返回统一响应结构")
@pytest.mark.smoke
def test_public_available_inventory_structure(anonymous_client, api_config):
    response = CatalogApi(anonymous_client).list_available_inventory(
        api_config.business_data.model_id
    )
    data = assert_json_code(response).get("data")
    assert isinstance(data, dict), "库存汇总 data 必须是对象"
    count = data.get("count")
    has_inventory = data.get("hasInventory")
    assert isinstance(count, int) and not isinstance(count, bool) and count >= 0, (
        "库存 count 必须是非负整数"
    )
    assert isinstance(has_inventory, bool), "库存 hasInventory 必须是布尔值"
    assert has_inventory == (count > 0), "库存标志必须与 count 保持一致"
