from __future__ import annotations

import requests

from ev_api.client import ApiClient
from ev_api.redaction import redact_text


class AuthApi:
    """Authentication operations for dedicated test accounts."""

    _LOGIN_PATH = "/auth/login"

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def login(self, username: str, password: str) -> requests.Response:
        return self.client.post(
            self._LOGIN_PATH,
            params={"username": username, "password": password},
        )

    def authenticate(self, username: str, password: str) -> str:
        """Log in, attach the returned token to the client, and return it."""
        response = self.login(username, password)
        payload = response.json()
        token = (payload.get("data") or {}).get("token")
        if not token:
            safe_body = redact_text(response.text)[:5000]
            raise AssertionError(
                f"Login did not return token: status={response.status_code}, body={safe_body}"
            )
        self.client.set_token(token)
        return token
