from __future__ import annotations

import requests

from ev_api.client import ApiClient


class CustomerApi:
    """Customer account and profile operations."""

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def get_my_profile(self) -> requests.Response:
        return self.client.get("/info/my-profile")
