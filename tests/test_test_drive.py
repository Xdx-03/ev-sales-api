from datetime import datetime, timedelta

import pytest

from ev_api.allure_compat import feature, title
from ev_api.apis import TestDriveApi
from ev_api.assertions import assert_json_code, assert_table_response

pytestmark = [pytest.mark.api, pytest.mark.regression]


def _find_available_book_time(api: TestDriveApi, model_id: int) -> str:
    """Pick a free future day so repeated runs do not collide with old test data."""
    for days_ahead in range(7, 38):
        candidate = (
            (datetime.now() + timedelta(days=days_ahead))
            .replace(hour=10, minute=0, second=0, microsecond=0)
            .isoformat()
        )
        conflict = assert_json_code(api.check_conflict(model_id, candidate))["data"] or {}
        if conflict.get("available") is True:
            return candidate
    pytest.fail("No available test-drive day was found in the next 31 candidate days.")


@feature("试驾预约")
@title("创建试驾后重复提交应被拦截并可在列表回查")
@pytest.mark.business
@pytest.mark.destructive
def test_test_drive_create_and_duplicate_conflict(customer_client, api_config):
    model_id = api_config.business_data.model_id
    api = TestDriveApi(customer_client)
    book_time = _find_available_book_time(api, model_id)
    sku_id = api_config.business_data.sku_id
    created = assert_json_code(api.create_appointment(model_id, book_time, sku_id))["data"]
    assert created.get("id")
    assert_json_code(
        api.create_appointment(model_id, book_time, sku_id),
        expected=400,
    )
    duplicate = assert_json_code(api.check_conflict(model_id, book_time))["data"]
    assert duplicate["available"] is False
    assert duplicate["sameDayDuplicated"] is True
    rows = assert_table_response(api.list_my_appointments(page_size=50))["rows"]
    assert any(item.get("id") == created["id"] for item in rows)


@feature("试驾反馈")
@title("已完成试驾的非法评分应被拒绝")
@pytest.mark.business
@pytest.mark.boundary
@pytest.mark.parametrize(
    ("rating", "config_field"),
    (
        pytest.param(0, "completed_test_drive_id_rating_0", id="0"),
        pytest.param(6, "completed_test_drive_id_rating_6", id="6"),
    ),
)
@pytest.mark.destructive
def test_test_drive_feedback_rejects_invalid_rating(
    customer_client,
    api_config,
    test_run,
    rating,
    config_field,
):
    test_drive_id = getattr(api_config.business_data, config_field)
    if not test_drive_id:
        pytest.fail(
            f"Configure an independent completed appointment in business_data.{config_field}.",
            pytrace=False,
        )
    api = TestDriveApi(customer_client)
    _require_feedback_ready(api, int(test_drive_id))
    response = api.submit_feedback(
        int(test_drive_id),
        rating,
        test_run.tag("试驾评分边界验证"),
    )
    assert_json_code(response, expected=400)
    _require_feedback_ready(api, int(test_drive_id))


def _require_feedback_ready(api: TestDriveApi, test_drive_id: int) -> None:
    """Confirm ownership, completed state, and no prior feedback through the customer API."""

    page_size = 50
    for page_number in range(1, 21):
        payload = assert_table_response(
            api.list_my_appointments(page_number=page_number, page_size=page_size)
        )
        record = next(
            (
                item
                for item in payload["rows"]
                if isinstance(item, dict) and item.get("id") == test_drive_id
            ),
            None,
        )
        if record is not None:
            if record.get("status") != 30:
                pytest.fail("Configured appointment is not in completed status.", pytrace=False)
            if "rating" not in record or "feedback" not in record:
                pytest.fail(
                    "Appointment list contract must include rating and feedback fields.",
                    pytrace=False,
                )
            rating_value = record["rating"]
            feedback_value = record["feedback"]
            if rating_value is not None:
                pytest.fail("Configured appointment already contains feedback.", pytrace=False)
            if feedback_value is not None and not isinstance(feedback_value, str):
                pytest.fail("Appointment feedback field must be text or null.", pytrace=False)
            if isinstance(feedback_value, str) and feedback_value.strip():
                pytest.fail("Configured appointment already contains feedback.", pytrace=False)
            return

        total = payload.get("total")
        if not isinstance(total, int) or page_number * page_size >= total:
            break

    pytest.fail(
        "Configured appointment is not present in the current customer's appointment list.",
        pytrace=False,
    )
