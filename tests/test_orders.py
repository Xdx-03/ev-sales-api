from decimal import Decimal, InvalidOperation

import pytest

from ev_api.allure_compat import feature, step, title
from ev_api.apis import DeliveryApi, FinanceApi, InventoryApi, OrderApi
from ev_api.assertions import assert_json_code, assert_table_response

pytestmark = [pytest.mark.api, pytest.mark.regression]


@feature("客户订单")
@title("客户下单到管理员配车、收款与交付的完整业务闭环")
@pytest.mark.business
@pytest.mark.critical
@pytest.mark.destructive
def test_order_customer_to_delivery_lifecycle(
    customer_client,
    admin_client,
    api_config,
):
    sku_id = api_config.business_data.sku_id
    if sku_id is None:
        pytest.fail(
            "Configure a real business_data.sku_id before running this test.", pytrace=False
        )
    customer_orders = OrderApi(customer_client)
    admin_orders = OrderApi(admin_client)
    finance = FinanceApi(admin_client)

    with step("客户创建预购订单"):
        order = _require_mapping(
            assert_json_code(customer_orders.create_order(sku_id)).get("data"),
            "创建订单响应必须包含 data 对象",
        )
        order_id = _require_positive_id(order.get("id"), "创建订单必须返回有效 ID")
        _require(bool(order.get("orderNo")), "创建订单必须返回订单号")
        _require(order.get("status") == 10, "新建预购订单状态必须为待支付")

    with step("管理员确认定金并核对订单与支付流水"):
        assert_json_code(admin_orders.pay_order(order_id, "定金确认"))
        deposit_detail = _order_detail(admin_orders, order_id)
        _require(deposit_detail.get("status") == 20, "定金确认后订单必须进入待配车状态")
        total_amount = _money(deposit_detail.get("totalAmount"), "订单总金额必须有效")
        deposit = _payment_for_order(finance, order_id, "定金确认")
        _require_money(
            deposit.get("amount"),
            total_amount * Decimal("0.10"),
            "定金流水金额必须为订单总额的 10%",
        )

    with step("管理员查询匹配车辆并完成配车"):
        available = assert_json_code(admin_orders.list_available_cars(order_id)).get("data")
        if not isinstance(available, list) or not available:
            pytest.fail("隔离测试环境没有可分配车辆", pytrace=False)
        selected = next(
            (
                item
                for item in available
                if isinstance(item, dict)
                and item.get("skuId") == sku_id
                and _is_positive_id(item.get("id"))
            ),
            None,
        )
        if selected is None:
            pytest.fail("可分配车辆列表中没有与订单 SKU 匹配的有效车辆", pytrace=False)
        car_id = _require_positive_id(selected.get("id"), "可分配车辆必须包含有效 ID")
        _require(selected.get("warehouseStatus") == 10, "配车前车辆必须处于在库状态")
        assignment = _require_mapping(
            assert_json_code(admin_orders.assign_car(order_id, car_id)).get("data"),
            "配车响应必须包含 data 对象",
        )
        _require(assignment.get("status") == 40, "同仓配车后订单必须进入车辆准备状态")
        assigned_detail = _order_detail(admin_orders, order_id)
        _require(assigned_detail.get("carId") == car_id, "订单必须绑定选中的车辆")

    with step("管理员确认尾款并核对支付流水"):
        assert_json_code(admin_orders.pay_order(order_id, "尾款确认"))
        settled_detail = _order_detail(admin_orders, order_id)
        _require(settled_detail.get("status") == 60, "尾款确认后订单必须进入可交付状态")
        balance = _payment_for_order(finance, order_id, "尾款确认")
        _require_money(
            balance.get("amount"),
            total_amount * Decimal("0.90"),
            "尾款流水金额必须为订单总额的 90%",
        )

    with step("管理员交付并核对订单、库存、交付单和客户列表"):
        assert_json_code(admin_orders.deliver_order(order_id))
        delivered_detail = _order_detail(admin_orders, order_id)
        _require(delivered_detail.get("status") == 70, "交付后订单状态必须为已提车")

        inventory = _require_mapping(
            assert_json_code(InventoryApi(admin_client).get_inventory(car_id)).get("data"),
            "库存详情必须返回 data 对象",
        )
        _require(inventory.get("warehouseStatus") == 40, "交付后车辆必须标记为已售")
        _require(inventory.get("lockOrderId") is None, "交付后车辆必须释放订单锁定字段")

        delivery_rows = assert_table_response(
            DeliveryApi(admin_client).list_deliveries(order_id=order_id)
        )["rows"]
        delivery = _find_by_order(delivery_rows, order_id, "交付记录中未找到当前订单")
        _require(delivery.get("status") == 30, "交付单状态必须为已完成")

        customer_rows = assert_table_response(customer_orders.list_my_orders(page_size=50))["rows"]
        customer_order = _find_by_id(customer_rows, order_id, "客户订单列表缺少已交付订单")
        _require(customer_order.get("status") == 70, "客户列表中的订单状态必须同步为已提车")


@feature("客户订单")
@title("支付不存在订单应返回404业务码")
@pytest.mark.business
@pytest.mark.destructive
def test_pay_nonexistent_order_returns_404(customer_client, api_config):
    response = OrderApi(customer_client).pay_order(api_config.business_data.nonexistent_order_id)
    assert_json_code(response, expected=404)


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _is_positive_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _require_positive_id(value: object, message: str) -> int:
    if not _is_positive_id(value):
        pytest.fail(message, pytrace=False)
    return value


def _require_mapping(value: object, message: str) -> dict:
    if not isinstance(value, dict):
        pytest.fail(message, pytrace=False)
    return value


def _order_detail(api: OrderApi, order_id: int) -> dict:
    return _require_mapping(
        assert_json_code(api.get_order_detail(order_id)).get("data"),
        "订单详情必须返回 data 对象",
    )


def _payment_for_order(finance: FinanceApi, order_id: int, pay_method: str) -> dict:
    rows = assert_table_response(finance.list_payments(pay_method=pay_method, page_size=100))[
        "rows"
    ]
    return _find_by_order(rows, order_id, "支付流水中未找到当前订单")


def _find_by_order(rows: list, order_id: int, message: str) -> dict:
    for row in rows:
        if isinstance(row, dict) and row.get("orderId") == order_id:
            return row
    pytest.fail(message, pytrace=False)


def _find_by_id(rows: list, expected_id: int, message: str) -> dict:
    for row in rows:
        if isinstance(row, dict) and row.get("id") == expected_id:
            return row
    pytest.fail(message, pytrace=False)


def _money(value: object, message: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        pytest.fail(message, pytrace=False)
    if amount <= 0:
        pytest.fail(message, pytrace=False)
    return amount.quantize(Decimal("0.01"))


def _require_money(value: object, expected: Decimal, message: str) -> None:
    actual = _money(value, message)
    if actual != expected.quantize(Decimal("0.01")):
        pytest.fail(message, pytrace=False)
