from __future__ import annotations

import requests

from ev_api.client import ApiClient


class OrderApi:
    """Customer and administrator order lifecycle operations."""

    _BASE_PATH = "/sale/order"

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def create_order(self, sku_id: int) -> requests.Response:
        return self.client.post(f"{self._BASE_PATH}/create", json={"skuId": sku_id})

    def list_my_orders(
        self,
        *,
        page_number: int = 1,
        page_size: int = 10,
    ) -> requests.Response:
        params = {"pageNum": page_number, "pageSize": page_size}
        return self.client.get(f"{self._BASE_PATH}/my-list", params=params)

    def pay_order(
        self,
        order_id: int,
        payment_type: str = "自动化测试",
    ) -> requests.Response:
        return self.client.post(
            f"{self._BASE_PATH}/pay/{order_id}",
            params={"payType": payment_type},
        )

    def get_order_detail(self, order_id: int) -> requests.Response:
        return self.client.get(f"{self._BASE_PATH}/detail/{order_id}")

    def list_available_cars(self, order_id: int) -> requests.Response:
        return self.client.get(f"{self._BASE_PATH}/available-cars/{order_id}")

    def assign_car(
        self,
        order_id: int,
        car_id: int,
        *,
        need_transfer: bool = False,
    ) -> requests.Response:
        return self.client.post(
            f"{self._BASE_PATH}/assign-car/{order_id}",
            json={"carId": car_id, "needTransfer": need_transfer},
        )

    def deliver_order(self, order_id: int) -> requests.Response:
        return self.client.post(f"{self._BASE_PATH}/deliver/{order_id}")

    def cancel_order(self, order_id: int) -> requests.Response:
        return self.client.post(f"{self._BASE_PATH}/cancel/{order_id}")
