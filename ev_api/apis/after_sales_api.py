from __future__ import annotations

import requests

from ev_api.client import ApiClient


class AfterSalesApi:
    """Customer-facing after-sales ticket operations."""

    _BASE_PATH = "/after-sales/ticket"

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def create_ticket(
        self,
        service_type: str,
        description: str,
        vin: str = "",
    ) -> requests.Response:
        body = {
            "serviceType": service_type,
            "description": description,
            "vin": vin,
        }
        return self.client.post(self._BASE_PATH, json=body)

    def list_my_tickets(
        self,
        *,
        page_number: int = 1,
        page_size: int = 10,
    ) -> requests.Response:
        params = {"pageNum": page_number, "pageSize": page_size}
        return self.client.get(f"{self._BASE_PATH}/my-list", params=params)
