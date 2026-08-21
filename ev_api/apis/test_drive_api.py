from __future__ import annotations

import requests

from ev_api.client import ApiClient


class TestDriveApi:
    """Customer-facing test-drive appointment and feedback operations."""

    __test__ = False
    _BASE_PATH = "/cust/test-drive"

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def check_conflict(self, model_id: int, booking_time: str) -> requests.Response:
        params = {"modelId": model_id, "bookTime": booking_time}
        return self.client.get(f"{self._BASE_PATH}/check-conflict", params=params)

    def create_appointment(
        self,
        model_id: int,
        booking_time: str,
        sku_id: int | None = None,
    ) -> requests.Response:
        body = {"modelId": model_id, "bookTime": booking_time}
        if sku_id is not None:
            body["skuId"] = sku_id
        return self.client.post(self._BASE_PATH, json=body)

    def list_my_appointments(
        self,
        *,
        page_number: int = 1,
        page_size: int = 10,
    ) -> requests.Response:
        params = {"pageNum": page_number, "pageSize": page_size}
        return self.client.get(f"{self._BASE_PATH}/my-list", params=params)

    def submit_feedback(
        self,
        appointment_id: int,
        rating: int,
        feedback: str,
    ) -> requests.Response:
        body = {"rating": rating, "feedback": feedback}
        return self.client.post(f"{self._BASE_PATH}/{appointment_id}/feedback", json=body)
