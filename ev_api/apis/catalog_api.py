from __future__ import annotations

import requests

from ev_api.client import ApiClient


class CatalogApi:
    """Public vehicle catalog, content, and available-inventory queries."""

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def list_brands(self) -> requests.Response:
        return self.client.get("/brand/public/list")

    def list_models(self) -> requests.Response:
        return self.client.get("/car/model/public/list")

    def list_skus(self) -> requests.Response:
        return self.client.get("/car/sku/public/list")

    def list_articles(self) -> requests.Response:
        return self.client.get("/cms/article/public/list")

    def list_available_inventory(self, model_id: int) -> requests.Response:
        return self.client.get(
            "/car/inventory/public/available",
            params={"modelId": model_id},
        )
