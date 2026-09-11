from __future__ import annotations

from collections.abc import Generator

import pytest

from ev_api.apis import AuthApi
from ev_api.client import ApiClient
from ev_api.config import ApiConfig, load_config
from ev_api.database import DatabaseClient
from ev_api.preflight import BackendUnavailableError, verify_backend
from ev_api.run_context import TestRunContext, create_test_run_context


def pytest_addoption(parser):
    parser.addoption("--env", action="store", default="default")
    parser.addoption("--config", action="store", default=None)
    parser.addoption(
        "--run-destructive",
        action="store_true",
        help="Run tests that create or modify business data.",
    )
    parser.addoption(
        "--run-database-checks",
        action="store_true",
        help="Run explicit read-only API-to-database consistency checks.",
    )


def _destructive_tests_enabled(config) -> bool:
    return config.getoption("--run-destructive")


def pytest_collection_modifyitems(config, items):
    """Block state-changing and database tests unless explicitly enabled."""
    destructive_blocked = pytest.mark.skip(
        reason="Write tests are disabled; pass --run-destructive to enable them."
    )
    database_blocked = pytest.mark.skip(
        reason="Database checks are disabled; pass --run-database-checks to enable them."
    )
    for item in items:
        if item.get_closest_marker("destructive") and not _destructive_tests_enabled(config):
            item.add_marker(destructive_blocked)
        if item.get_closest_marker("database") and not config.getoption("--run-database-checks"):
            item.add_marker(database_blocked)


@pytest.fixture(scope="session")
def api_config(pytestconfig) -> ApiConfig:
    return load_config(pytestconfig.getoption("--env"), pytestconfig.getoption("--config"))


@pytest.fixture(scope="session")
def test_run() -> TestRunContext:
    return create_test_run_context()


@pytest.fixture(scope="session")
def anonymous_client(
    api_config: ApiConfig, test_run: TestRunContext
) -> Generator[ApiClient, None, None]:
    client = ApiClient(
        api_config.base_url,
        timeout=api_config.timeout,
        test_run_id=test_run.run_id,
    )
    try:
        try:
            verify_backend(client)
        except BackendUnavailableError:
            pytest.exit(
                "API preflight failed; start or fix the configured backend before running API tests.",
                returncode=2,
            )
        yield client
    finally:
        client.close()


@pytest.fixture
def customer_client(
    api_config: ApiConfig,
    anonymous_client: ApiClient,
    test_run: TestRunContext,
) -> Generator[ApiClient, None, None]:
    if not api_config.customer.username or not api_config.customer.password:
        pytest.exit(
            "Customer test credentials are required for the selected API tests.", returncode=2
        )
    client = ApiClient(
        api_config.base_url,
        timeout=api_config.timeout,
        test_run_id=test_run.run_id,
    )
    try:
        AuthApi(client).authenticate(api_config.customer.username, api_config.customer.password)
        yield client
    finally:
        client.close()


@pytest.fixture
def admin_client(
    api_config: ApiConfig,
    anonymous_client: ApiClient,
    test_run: TestRunContext,
) -> Generator[ApiClient, None, None]:
    if not api_config.admin.username or not api_config.admin.password:
        pytest.exit(
            "Administrator test credentials are required for the selected API tests.", returncode=2
        )
    client = ApiClient(
        api_config.base_url,
        timeout=api_config.timeout,
        test_run_id=test_run.run_id,
    )
    try:
        AuthApi(client).authenticate(api_config.admin.username, api_config.admin.password)
        yield client
    finally:
        client.close()


@pytest.fixture
def database_client(api_config: ApiConfig) -> Generator[DatabaseClient, None, None]:
    client = DatabaseClient(api_config.database)
    try:
        yield client
    finally:
        client.close()
