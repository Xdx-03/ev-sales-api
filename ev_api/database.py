from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from ev_api.config import DatabaseConfig


class DatabaseConfigurationError(ValueError):
    """Raised when an unsafe or incomplete database configuration is supplied."""


class DatabaseClient:
    """Read-only adapter for the small set of approved consistency queries."""

    def __init__(self, config: DatabaseConfig) -> None:
        if not config.configured:
            raise DatabaseConfigurationError(
                "Database checks require EV_DB_HOST, EV_DB_NAME, EV_DB_USERNAME and EV_DB_PASSWORD."
            )
        if config.username.casefold() == "root":
            raise DatabaseConfigurationError(
                "Database checks must use a dedicated SELECT-only account, not root."
            )
        tls_options = self._tls_options(config)
        self._connection = pymysql.connect(
            host=config.host,
            port=config.port,
            user=config.username,
            password=config.password,
            database=config.name,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
            connect_timeout=5,
            read_timeout=5,
            write_timeout=5,
            **tls_options,
        )
        try:
            self._verify_read_only_grants()
        except Exception:
            self._connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    def get_customer_profile_state(self, profile_id: int) -> dict[str, Any] | None:
        """Return only non-sensitive fields needed for API-DB state comparison."""

        query = """
            SELECT id, deleted, stage, intent_level AS intentLevel
            FROM cust_info
            WHERE id = %s
        """
        with self._connection.cursor() as cursor:
            cursor.execute(query, (profile_id,))
            return cursor.fetchone()

    def _verify_read_only_grants(self) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute("SHOW GRANTS FOR CURRENT_USER")
            grants = cursor.fetchall()

        allowed_privileges = {"SELECT", "USAGE"}
        for row in grants:
            statement = str(next(iter(row.values())))
            normalized_statement = statement.upper()
            if (
                "WITH GRANT OPTION" in normalized_statement
                or "WITH ADMIN OPTION" in normalized_statement
            ):
                raise DatabaseConfigurationError(
                    "Database account can delegate privileges; use a strict SELECT-only account."
                )
            grant_clause = statement.split(" ON ", maxsplit=1)[0]
            privileges = {
                privilege.strip().upper()
                for privilege in grant_clause.removeprefix("GRANT ").split(",")
            }
            if not privileges or not privileges.issubset(allowed_privileges):
                raise DatabaseConfigurationError(
                    "Database account has non-read-only privileges; use a SELECT-only account."
                )

    @staticmethod
    def _tls_options(config: DatabaseConfig) -> dict[str, object]:
        """Require certificate verification whenever the database is not loopback-only."""

        hostname = config.host.casefold()
        is_loopback = hostname == "localhost"
        try:
            is_loopback = is_loopback or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass

        if not config.ssl_ca:
            if is_loopback:
                return {}
            raise DatabaseConfigurationError(
                "Remote database checks require EV_DB_SSL_CA for certificate verification."
            )

        ca_path = Path(config.ssl_ca).expanduser()
        if not ca_path.is_file():
            raise DatabaseConfigurationError(
                "EV_DB_SSL_CA must point to an existing CA certificate file."
            )
        return {
            "ssl_ca": str(ca_path.resolve()),
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        }
