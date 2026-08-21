from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

_RUN_ID_ENV = "EV_TEST_RUN_ID"
_UNSAFE_RUN_ID = re.compile(r"[^A-Za-z0-9_-]+")


@dataclass(frozen=True)
class TestRunContext:
    """Identity shared by requests and data created during one test run."""

    run_id: str

    def tag(self, text: str) -> str:
        """Prefix free-text test data so created records remain traceable."""
        return f"[AUTO:{self.run_id}] {text}"


def create_test_run_context() -> TestRunContext:
    """Resolve a CI-provided run ID or generate a short, filesystem-safe value."""
    configured = os.getenv(_RUN_ID_ENV, "").strip()
    if configured:
        sanitized = _UNSAFE_RUN_ID.sub("-", configured).strip("-_")[:48]
        if not sanitized:
            raise ValueError(f"{_RUN_ID_ENV} must contain letters, numbers, '-' or '_'.")
        return TestRunContext(sanitized)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return TestRunContext(f"{timestamp}-{uuid4().hex[:8]}")
