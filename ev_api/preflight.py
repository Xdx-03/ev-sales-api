from __future__ import annotations

from typing import Protocol

import requests

DEFAULT_HEALTH_PATH = "/car/model/public/list"


class BackendUnavailableError(RuntimeError):
    """Raised when the target API cannot pass the preflight check."""


class _ApiClient(Protocol):
    def get(self, path: str) -> requests.Response: ...


def verify_backend(client: _ApiClient, path: str = DEFAULT_HEALTH_PATH) -> requests.Response:
    """Verify transport, HTTP status, and the application's response envelope."""
    try:
        response = client.get(path)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise BackendUnavailableError(f"Backend preflight request failed at {path}: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise BackendUnavailableError(
            f"Backend preflight returned a non-JSON response at {path} (HTTP {response.status_code})"
        ) from exc

    if not isinstance(payload, dict) or payload.get("code") != 200:
        business_code = payload.get("code") if isinstance(payload, dict) else None
        raise BackendUnavailableError(
            f"Backend preflight failed at {path}: HTTP {response.status_code}, business code {business_code!r}"
        )

    return response
