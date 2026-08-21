from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "env.yaml"
EXAMPLE_CONFIG_PATH = ROOT_DIR / "config" / "env.example.yaml"


@dataclass(frozen=True)
class Account:
    """Credentials for one dedicated test account."""

    username: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class FeishuConfig:
    """Optional notification settings supplied outside source control."""

    webhook: str = field(repr=False)
    report_url: str = field(repr=False)


@dataclass(frozen=True)
class DatabaseConfig:
    """Optional read-only database connection for explicit consistency checks."""

    host: str
    port: int
    name: str
    username: str
    password: str = field(repr=False)
    ssl_ca: str = field(repr=False)

    @property
    def configured(self) -> bool:
        return all((self.host, self.name, self.username, self.password))


@dataclass(frozen=True)
class BusinessData:
    """Typed synthetic data references used by black-box business scenarios."""

    nonexistent_order_id: int
    model_id: int
    sku_id: int | None
    completed_test_drive_id_rating_0: int | None
    completed_test_drive_id_rating_6: int | None
    vin: str
    ai_question: str
    ai_min_reply_length: int


@dataclass(frozen=True)
class ApiConfig:
    """Resolved runtime configuration for an API test environment."""

    env_name: str
    base_url: str
    timeout: int
    customer: Account
    admin: Account
    database: DatabaseConfig
    business_data: BusinessData
    feishu: FeishuConfig


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a mapping: {path}")
    return data


def _env(name: str, default: Any) -> Any:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Config field '{field_name}' must be a mapping.")
    return value


def _positive_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Config field '{field_name}' must be a positive integer.") from exc
    if parsed <= 0:
        raise ValueError(f"Config field '{field_name}' must be a positive integer.")
    return parsed


def _optional_positive_int(value: Any, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    return _positive_int(value, field_name)


def _nonempty_text(value: Any, field_name: str) -> str:
    parsed = str(value).strip()
    if not parsed:
        raise ValueError(f"Config field '{field_name}' must not be empty.")
    return parsed


def load_config(env_name: str = "default", config_path: str | None = None) -> ApiConfig:
    if config_path:
        path = Path(config_path)
    elif DEFAULT_CONFIG_PATH.exists():
        path = DEFAULT_CONFIG_PATH
    else:
        path = EXAMPLE_CONFIG_PATH
    raw = _load_yaml(path)
    section = raw.get(env_name)
    if not isinstance(section, dict):
        raise KeyError(f"Environment '{env_name}' not found in {path}")

    accounts = _mapping(section.get("accounts"), "accounts")
    customer = _mapping(accounts.get("customer"), "accounts.customer")
    admin = _mapping(accounts.get("admin"), "accounts.admin")
    database = _mapping(section.get("database"), "database")
    business = _mapping(section.get("business_data"), "business_data")
    feishu = _mapping(section.get("feishu"), "feishu")

    completed_test_drive_id_rating_0 = _optional_positive_int(
        _env(
            "EV_COMPLETED_TEST_DRIVE_ID_RATING_0",
            business.get("completed_test_drive_id_rating_0"),
        ),
        "business_data.completed_test_drive_id_rating_0",
    )
    completed_test_drive_id_rating_6 = _optional_positive_int(
        _env(
            "EV_COMPLETED_TEST_DRIVE_ID_RATING_6",
            business.get("completed_test_drive_id_rating_6"),
        ),
        "business_data.completed_test_drive_id_rating_6",
    )
    if (
        completed_test_drive_id_rating_0 is not None
        and completed_test_drive_id_rating_0 == completed_test_drive_id_rating_6
    ):
        raise ValueError("Rating boundary tests require two different completed appointments.")

    return ApiConfig(
        env_name=env_name,
        base_url=str(
            _env("EV_API_BASE_URL", section.get("base_url", "http://localhost:8080"))
        ).rstrip("/"),
        timeout=_positive_int(
            _env("EV_API_TIMEOUT", section.get("timeout", 10)),
            "timeout",
        ),
        customer=Account(
            username=str(_env("EV_CUSTOMER_USERNAME", customer.get("username", ""))),
            password=str(_env("EV_CUSTOMER_PASSWORD", customer.get("password", ""))),
        ),
        admin=Account(
            username=str(_env("EV_ADMIN_USERNAME", admin.get("username", ""))),
            password=str(_env("EV_ADMIN_PASSWORD", admin.get("password", ""))),
        ),
        database=DatabaseConfig(
            host=str(_env("EV_DB_HOST", database.get("host", ""))).strip(),
            port=_positive_int(
                _env("EV_DB_PORT", database.get("port", 3306)),
                "database.port",
            ),
            name=str(_env("EV_DB_NAME", database.get("name", ""))).strip(),
            username=str(_env("EV_DB_USERNAME", database.get("username", ""))).strip(),
            password=str(_env("EV_DB_PASSWORD", database.get("password", ""))),
            ssl_ca=str(_env("EV_DB_SSL_CA", database.get("ssl_ca", ""))).strip(),
        ),
        business_data=BusinessData(
            nonexistent_order_id=_positive_int(
                _env(
                    "EV_NONEXISTENT_ORDER_ID",
                    business.get("nonexistent_order_id", 999999999),
                ),
                "business_data.nonexistent_order_id",
            ),
            model_id=_positive_int(
                _env("EV_MODEL_ID", business.get("model_id", 1)),
                "business_data.model_id",
            ),
            sku_id=_optional_positive_int(
                _env("EV_SKU_ID", business.get("sku_id")),
                "business_data.sku_id",
            ),
            completed_test_drive_id_rating_0=completed_test_drive_id_rating_0,
            completed_test_drive_id_rating_6=completed_test_drive_id_rating_6,
            vin=str(_env("EV_TEST_VIN", business.get("vin", ""))).strip(),
            ai_question=_nonempty_text(
                _env(
                    "EV_AI_QUESTION",
                    business.get(
                        "ai_question",
                        "预算25万，推荐一款续航较高、适合家用的新能源车",
                    ),
                ),
                "business_data.ai_question",
            ),
            ai_min_reply_length=_positive_int(
                _env(
                    "EV_AI_MIN_REPLY_LENGTH",
                    business.get("ai_min_reply_length", 8),
                ),
                "business_data.ai_min_reply_length",
            ),
        ),
        feishu=FeishuConfig(
            webhook=str(_env("EV_FEISHU_WEBHOOK", feishu.get("webhook", ""))),
            report_url=str(_env("EV_ALLURE_REPORT_URL", feishu.get("report_url", ""))),
        ),
    )
