from __future__ import annotations

import ipaddress
import os
from types import TracebackType
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests

from ev_api.allure_compat import attach_text
from ev_api.redaction import redact_sensitive, redact_text


class ApiRequestError(requests.RequestException):
    """A request failure whose user-facing message is safe for reports and CI logs."""


class ApiClient:
    """Shared HTTP session with transport safety, authentication, and safe evidence."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 10,
        token: str | None = None,
        test_run_id: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self._validate_transport()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        if test_run_id:
            self.session.headers.update({"X-Test-Run-Id": test_run_id})
        if token:
            self.set_token(token)

    def set_token(self, token: str) -> None:
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def close(self) -> None:
        """Release the HTTP connection pool owned by this client."""
        self.session.close()

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _validate_transport(self) -> None:
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("EV_API_BASE_URL must be an absolute HTTP(S) URL.")
        if parsed.scheme == "https":
            return

        hostname = parsed.hostname.lower()
        is_loopback = hostname == "localhost"
        try:
            is_loopback = is_loopback or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass
        if is_loopback or os.getenv("EV_ALLOW_INSECURE_HTTP", "").lower() == "true":
            return
        raise ValueError(
            "Refusing plain HTTP for a non-loopback API because login credentials and JWTs "
            "could be exposed. Use HTTPS, or set EV_ALLOW_INSECURE_HTTP=true only for an "
            "explicitly isolated test network."
        )

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = urljoin(self.base_url, path.lstrip("/"))
        kwargs.setdefault("timeout", self.timeout)
        try:
            response = self.session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            attach_text("request", redact_sensitive(self._request_info(method, url, kwargs)))
            safe_error = redact_text(str(exc))
            attach_text("request_error", safe_error)
            raise ApiRequestError(safe_error) from None
        self._attach_debug(method, url, kwargs, response)
        return response

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

    @staticmethod
    def _request_info(method: str, url: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        return {
            "method": method,
            "url": url,
            "headers": kwargs.get("headers"),
            "params": kwargs.get("params"),
            "json": kwargs.get("json"),
            "data": kwargs.get("data"),
            "cookies": kwargs.get("cookies"),
            "auth": kwargs.get("auth"),
        }

    @staticmethod
    def _attach_debug(
        method: str, url: str, kwargs: dict[str, Any], response: requests.Response
    ) -> None:
        attach_text("request", redact_sensitive(ApiClient._request_info(method, url, kwargs)))
        attach_text("response_status", response.status_code)
        response_headers = dict(getattr(response, "headers", {}) or {})
        attach_text("response_headers", redact_sensitive(response_headers))
        attach_text("response_body", redact_text(response.text)[:5000])
