from __future__ import annotations

import requests

from ev_api.assertions import assert_json_code
from ev_api.client import ApiClient


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
        payload = assert_json_code(response)
        data = payload.get("data")
        assert isinstance(data, dict), "Login data must be an object."
        token = data.get("token")
        assert isinstance(token, str) and token.strip(), "Login token must be a non-empty string."
        self.client.set_token(token)
        return token
