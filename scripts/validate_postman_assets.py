from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT_DIR = Path(__file__).resolve().parents[1]
COLLECTION_PATH = ROOT_DIR / "postman" / "EV-Sales-API.postman_collection.json"
ENVIRONMENT_PATH = ROOT_DIR / "postman" / "EV-Sales-API.postman_environment.example.json"
COLLECTION_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
EXPECTED_REQUEST_COUNT = 12
SENSITIVE_VARIABLES = {"customerUsername", "customerPassword", "accessToken"}
REQUIRED_VARIABLES = SENSITIVE_VARIABLES | {"baseUrl", "modelId"}


def _load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _event_script(document: dict[str, Any], listener: str) -> tuple[str, ...]:
    lines: list[str] = []
    events = document.get("event", [])
    if not isinstance(events, list):
        raise ValueError(f"Expected events to be a list: {document.get('name')}")
    for event in events:
        if not isinstance(event, dict) or event.get("listen") != listener:
            continue
        script = event.get("script")
        if not isinstance(script, dict) or not isinstance(script.get("exec"), list):
            raise ValueError(f"Invalid {listener} script: {document.get('name')}")
        script_lines = script["exec"]
        if not all(isinstance(line, str) for line in script_lines):
            raise ValueError(f"Non-string line in {listener} script: {document.get('name')}")
        lines.extend(script_lines)
    return tuple(lines)


def _iter_requests(
    items: list[dict[str, Any]], inherited_tests: tuple[str, ...] = ()
) -> Iterator[tuple[dict[str, Any], tuple[str, ...]]]:
    for item in items:
        effective_tests = inherited_tests + _event_script(item, "test")
        children = item.get("item")
        if isinstance(children, list):
            yield from _iter_requests(children, effective_tests)
            continue
        request = item.get("request")
        if not isinstance(request, dict):
            raise ValueError(f"Collection item has no request object: {item.get('name')}")
        yield request, effective_tests


def _raw_url(request: dict[str, Any]) -> str:
    url = request.get("url")
    if isinstance(url, str):
        return url
    if isinstance(url, dict) and isinstance(url.get("raw"), str):
        return url["raw"]
    raise ValueError("Every request must provide a string URL or url.raw.")


def _variables(document: dict[str, Any], key: str) -> dict[str, str]:
    variables = document.get(key)
    if not isinstance(variables, list):
        raise ValueError(f"Expected '{key}' to be a list.")
    values: dict[str, str] = {}
    for variable in variables:
        if not isinstance(variable, dict) or not isinstance(variable.get("key"), str):
            raise ValueError(f"Invalid variable entry in '{key}'.")
        values[variable["key"]] = str(variable.get("value", ""))
    return values


def _assert_bearer_auth(folder: dict[str, Any]) -> None:
    auth = folder.get("auth")
    if not isinstance(auth, dict) or auth.get("type") != "bearer":
        raise ValueError(f"Folder must use bearer authentication: {folder.get('name')}")
    bearer = auth.get("bearer")
    if not isinstance(bearer, list) or not any(
        isinstance(entry, dict)
        and entry.get("key") == "token"
        and entry.get("value") == "{{accessToken}}"
        for entry in bearer
    ):
        raise ValueError(f"Folder must use the accessToken variable: {folder.get('name')}")


def validate() -> int:
    collection = _load_object(COLLECTION_PATH)
    environment = _load_object(ENVIRONMENT_PATH)

    info = collection.get("info")
    if not isinstance(info, dict) or info.get("schema") != COLLECTION_SCHEMA:
        raise ValueError("Collection must declare the Postman v2.1 schema.")

    folders = {
        item.get("name"): item
        for item in collection.get("item", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    required_folders = {
        "01 Authentication",
        "02 Public catalog",
        "03 Customer read-only queries",
        "04 Permission boundary",
    }
    missing_folders = required_folders - folders.keys()
    if missing_folders:
        raise ValueError(f"Missing collection folders: {sorted(missing_folders)}")

    pre_request_script = "\n".join(_event_script(collection, "prerequest"))
    for required_fragment in (
        'pm.variables.replaceIn("{{baseUrl}}")',
        "Base URL uses HTTPS or loopback without credentials",
        'pm.variables.set("baseUrl", "http://127.0.0.1:1")',
        "pm.execution.skipRequest()",
    ):
        if required_fragment not in pre_request_script:
            raise ValueError(f"Missing Postman transport guard: {required_fragment}")

    _assert_bearer_auth(folders["03 Customer read-only queries"])
    _assert_bearer_auth(folders["04 Permission boundary"])

    request_entries = list(_iter_requests(collection.get("item", [])))
    if len(request_entries) != EXPECTED_REQUEST_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_REQUEST_COUNT} safe requests, found {len(request_entries)}. "
            "Update the collection, validator and README together."
        )
    for request, effective_tests in request_entries:
        method = request.get("method")
        if method not in {"GET", "POST"}:
            raise ValueError(f"Unexpected method in safe collection: {method}")
        url = _raw_url(request)
        if method != "GET" and "/auth/login" not in url:
            raise ValueError(f"Safe collection contains a non-login POST: {url}")
        if not any("pm.response.to.have.status(" in line for line in effective_tests):
            raise ValueError(f"Request has no effective HTTP status assertion: {url}")
        if not any("pm.expect(body.code).to.eql(" in line for line in effective_tests):
            raise ValueError(f"Request has no effective business-code assertion: {url}")
        if "/car/inventory/public/available" in url:
            required_contract_checks = (
                "Inventory summary contract is valid",
                "Number.isInteger(body.data.count)",
                "body.data.hasInventory",
                "body.data.count > 0",
            )
            missing_checks = [
                check
                for check in required_contract_checks
                if not any(check in line for line in effective_tests)
            ]
            if missing_checks:
                raise ValueError(
                    "Available-inventory request has an incomplete data contract assertion."
                )
        headers = request.get("header", [])
        if not isinstance(headers, list):
            raise ValueError(f"Request headers must be a list: {url}")
        if any(
            isinstance(header, dict) and str(header.get("key", "")).casefold() == "authorization"
            for header in headers
        ):
            raise ValueError(f"Authorization must use folder bearer auth, not a raw header: {url}")

    collection_variables = _variables(collection, "variable")
    environment_variables = _variables(environment, "values")
    for location, variables in (
        ("collection", collection_variables),
        ("environment", environment_variables),
    ):
        missing_variables = REQUIRED_VARIABLES - variables.keys()
        if missing_variables:
            raise ValueError(f"Missing {location} variables: {sorted(missing_variables)}")
        if any(variables[name] for name in SENSITIVE_VARIABLES):
            raise ValueError(f"Public Postman {location} must not contain account or token values.")

    parsed_base_url = urlsplit(environment_variables["baseUrl"])
    if parsed_base_url.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("The public environment template must default to loopback only.")

    environment_entries = {
        entry.get("key"): entry
        for entry in environment.get("values", [])
        if isinstance(entry, dict)
    }
    for variable_name in SENSITIVE_VARIABLES:
        if environment_entries[variable_name].get("type") != "secret":
            raise ValueError(
                f"Sensitive Postman environment variable must use secret type: {variable_name}"
            )

    return len(request_entries)


if __name__ == "__main__":
    request_count = validate()
    print(f"Postman assets valid: {request_count} safe requests")
