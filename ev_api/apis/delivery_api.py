from __future__ import annotations

import requests

from ev_api.client import ApiClient


class DeliveryApi:
    """Administrator-facing delivery record queries."""

    _BASE_PATH = "/delivery"

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def list_deliveries(
        self,
        *,
        order_id: int | None = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> requests.Response:
        params: dict[str, int] = {
            "pageNum": page_number,
            "pageSize": page_size,
        }
        if order_id is not None:
            params["orderId"] = order_id
        return self.client.get(f"{self._BASE_PATH}/list", params=params)
