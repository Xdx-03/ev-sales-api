from __future__ import annotations

import requests

from ev_api.client import ApiClient


class FinanceApi:
    """Administrator-facing payment record queries."""

    _BASE_PATH = "/finance/payment"

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def list_payments(
        self,
        *,
        pay_method: str | None = None,
        page_number: int = 1,
        page_size: int = 50,
    ) -> requests.Response:
        params: dict[str, int | str] = {
            "pageNum": page_number,
            "pageSize": page_size,
        }
        if pay_method:
            params["payMethod"] = pay_method
        return self.client.get(f"{self._BASE_PATH}/list", params=params)
