from __future__ import annotations

import requests

from ev_api.client import ApiClient


class AiApi:
    """Customer-facing AI shopping-guide conversation operations."""

    _BASE_PATH = "/api/ai"

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def send_message(
        self,
        message: str,
        session_id: str | None = None,
    ) -> requests.Response:
        body = {"message": message}
        if session_id:
            body["sessionId"] = session_id
        return self.client.post(f"{self._BASE_PATH}/chat", json=body)

    def get_history(self, session_id: str) -> requests.Response:
        return self.client.get(
            f"{self._BASE_PATH}/history",
            params={"sessionId": session_id},
        )

    def submit_feedback(
        self,
        session_id: str,
        satisfied: bool,
        suggestion: str = "",
    ) -> requests.Response:
        body = {
            "sessionId": session_id,
            "satisfied": str(satisfied).lower(),
            "suggestion": suggestion,
        }
        return self.client.post(f"{self._BASE_PATH}/feedback", json=body)
