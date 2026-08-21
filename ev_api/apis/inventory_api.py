from __future__ import annotations

import requests

from ev_api.client import ApiClient


class InventoryApi:
    """Administrator-facing vehicle inventory queries."""

    _BASE_PATH = "/car/inventory"

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def get_inventory(self, inventory_id: int) -> requests.Response:
        return self.client.get(f"{self._BASE_PATH}/{inventory_id}")
