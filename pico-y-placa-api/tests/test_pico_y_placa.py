"""
TDD tests for Pico y Placa API.
Tests are written FIRST — they should be RED before implementation exists.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

BOGOTA = ZoneInfo("America/Bogota")


def dt(year: int, month: int, day: int, hour: int = 12, minute: int = 0, second: int = 0) -> datetime:
    """Helper: create a timezone-aware datetime in Bogotá time."""
    return datetime(year, month, day, hour, minute, second, tzinfo=BOGOTA)


# ---------------------------------------------------------------------------
# Import after helpers so failures surface cleanly
# ---------------------------------------------------------------------------
from app.pico_y_placa import check_pico_y_placa
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Weekend / holiday — no restriction regardless of plate
# ---------------------------------------------------------------------------

def test_saturday_no_restriction():
    # 2026-03-14 is a Saturday
    result = check_pico_y_placa("ABC123", now=dt(2026, 3, 14, 10, 0))
    assert result.has_restriction is False
    assert "weekend" in result.reason.lower() or "saturday" in result.reason.lower()


def test_sunday_no_restriction():
    # 2026-03-15 is a Sunday
    result = check_pico_y_placa("ABC123", now=dt(2026, 3, 15, 10, 0))
    assert result.has_restriction is False
    assert "weekend" in result.reason.lower() or "sunday" in result.reason.lower()


def test_holiday_no_restriction():
    # 2026-03-23 is San José (Colombian public holiday)
    result = check_pico_y_placa("ABC123", now=dt(2026, 3, 23, 10, 0))
    assert result.has_restriction is False
    assert "holiday" in result.reason.lower()


# ---------------------------------------------------------------------------
# Before restriction hours (before 6 AM)
# ---------------------------------------------------------------------------

def test_before_hours_restricted_plate_returns_true_with_countdown():
    # day=16 (even), plate ending 1 → restricted on even days, time=05:30
    result = check_pico_y_placa("ABC121", now=dt(2026, 3, 16, 5, 30))
    assert result.has_restriction is True
    assert "6:00 am" in result.reason.lower() or "6:00am" in result.reason.lower()
    # Remaining: 30 minutes → "0h 30m"
    assert "30m" in result.reason or "30 m" in result.reason


def test_before_hours_unrestricted_plate_returns_false():
    # day=16 (even), plate ending 7 → NOT restricted on even days, time=05:30
    result = check_pico_y_placa("ABC127", now=dt(2026, 3, 16, 5, 30))
    assert result.has_restriction is False


# ---------------------------------------------------------------------------
# Day change edge cases
# ---------------------------------------------------------------------------

def test_day_change_plate_allowed_just_before_midnight():
    # plate ending 7, day=16 (even), 23:59 → outside restriction window, not restricted on even days
    result = check_pico_y_placa("ABC127", now=dt(2026, 3, 16, 23, 59))
    assert result.has_restriction is False


def test_day_change_plate_restricted_just_after_midnight():
    # plate ending 7, day=17 (odd) at 00:01 → plate IS restricted on odd days
    # Before 6 AM on an odd day → has_restriction=True with countdown
    result = check_pico_y_placa("ABC127", now=dt(2026, 3, 17, 0, 1))
    assert result.has_restriction is True
    assert "6:00 am" in result.reason.lower() or "6:00am" in result.reason.lower()


def test_day_change_plate_restricted_to_allowed_after_midnight():
    # plate ending 3, day=16 (even), 23:59 → outside hours, no restriction
    result_before = check_pico_y_placa("ABC123", now=dt(2026, 3, 16, 23, 59))
    assert result_before.has_restriction is False

    # plate ending 3, day=17 (odd), 00:01 → plate ending 3 NOT in odd restricted set → false
    result_after = check_pico_y_placa("ABC123", now=dt(2026, 3, 17, 0, 1))
    assert result_after.has_restriction is False


# ---------------------------------------------------------------------------
# During restriction window (6 AM – 9 PM)
# ---------------------------------------------------------------------------

def test_during_hours_restricted_plate_8am():
    # day=16 (even), plate ending 3, 08:00 → true
    result = check_pico_y_placa("ABC123", now=dt(2026, 3, 16, 8, 0))
    assert result.has_restriction is True


def test_during_hours_unrestricted_plate_8am():
    # day=16 (even), plate ending 7, 08:00 → false
    result = check_pico_y_placa("ABC127", now=dt(2026, 3, 16, 8, 0))
    assert result.has_restriction is False


def test_during_hours_restricted_plate_2pm():
    # day=16 (even), plate ending 3, 14:00 → true
    result = check_pico_y_placa("ABC123", now=dt(2026, 3, 16, 14, 0))
    assert result.has_restriction is True


def test_during_hours_unrestricted_plate_2pm():
    # day=16 (even), plate ending 7, 14:00 → false
    result = check_pico_y_placa("ABC127", now=dt(2026, 3, 16, 14, 0))
    assert result.has_restriction is False


# ---------------------------------------------------------------------------
# Edge case: exactly 9:00 PM — restriction has just ended
# ---------------------------------------------------------------------------

def test_exactly_9pm_was_restricted_returns_false():
    # day=16 (even), plate ending 3, 21:00:00 exactly → false, "ended"
    result = check_pico_y_placa("ABC123", now=dt(2026, 3, 16, 21, 0, 0))
    assert result.has_restriction is False
    assert "ended" in result.reason.lower()


def test_exactly_9pm_was_unrestricted_returns_false():
    # day=16 (even), plate ending 7, 21:00:00 → false
    result = check_pico_y_placa("ABC127", now=dt(2026, 3, 16, 21, 0, 0))
    assert result.has_restriction is False


# ---------------------------------------------------------------------------
# After restriction (past 9 PM)
# ---------------------------------------------------------------------------

def test_after_hours_was_restricted_returns_false():
    # day=16 (even), plate ending 3, 21:01 → false, reason mentions ended
    result = check_pico_y_placa("ABC123", now=dt(2026, 3, 16, 21, 1))
    assert result.has_restriction is False
    assert "ended" in result.reason.lower()


def test_after_hours_was_unrestricted_returns_false():
    # day=16 (even), plate ending 7, 21:01 → false
    result = check_pico_y_placa("ABC127", now=dt(2026, 3, 16, 21, 1))
    assert result.has_restriction is False


# ---------------------------------------------------------------------------
# Even day coverage — day 16 and day 2
# ---------------------------------------------------------------------------

def test_even_day_march_16_plates_1_to_5_restricted():
    for digit in [1, 2, 3, 4, 5]:
        plate = f"ABC12{digit}"
        result = check_pico_y_placa(plate, now=dt(2026, 3, 16, 10, 0))
        assert result.has_restriction is True, f"Expected restriction for plate ending {digit} on even day"


def test_even_day_march_16_plates_6_to_0_allowed():
    for digit in [6, 7, 8, 9, 0]:
        plate = f"ABC12{digit}"
        result = check_pico_y_placa(plate, now=dt(2026, 3, 16, 10, 0))
        assert result.has_restriction is False, f"Expected no restriction for plate ending {digit} on even day"


def test_even_day_march_2_plates_1_to_5_restricted():
    for digit in [1, 2, 3, 4, 5]:
        plate = f"ABC12{digit}"
        result = check_pico_y_placa(plate, now=dt(2026, 3, 2, 10, 0))
        assert result.has_restriction is True, f"Expected restriction for plate ending {digit} on even day (day=2)"


def test_even_day_march_2_plates_6_to_0_allowed():
    for digit in [6, 7, 8, 9, 0]:
        plate = f"ABC12{digit}"
        result = check_pico_y_placa(plate, now=dt(2026, 3, 2, 10, 0))
        assert result.has_restriction is False, f"Expected no restriction for plate ending {digit} on even day (day=2)"


# ---------------------------------------------------------------------------
# Odd day coverage — day 17 and day 3
# ---------------------------------------------------------------------------

def test_odd_day_march_17_plates_6_to_0_restricted():
    for digit in [6, 7, 8, 9, 0]:
        plate = f"ABC12{digit}"
        result = check_pico_y_placa(plate, now=dt(2026, 3, 17, 10, 0))
        assert result.has_restriction is True, f"Expected restriction for plate ending {digit} on odd day"


def test_odd_day_march_17_plates_1_to_5_allowed():
    for digit in [1, 2, 3, 4, 5]:
        plate = f"ABC12{digit}"
        result = check_pico_y_placa(plate, now=dt(2026, 3, 17, 10, 0))
        assert result.has_restriction is False, f"Expected no restriction for plate ending {digit} on odd day"


def test_odd_day_march_3_plates_6_to_0_restricted():
    for digit in [6, 7, 8, 9, 0]:
        plate = f"ABC12{digit}"
        result = check_pico_y_placa(plate, now=dt(2026, 3, 3, 10, 0))
        assert result.has_restriction is True, f"Expected restriction for plate ending {digit} on odd day (day=3)"


def test_odd_day_march_3_plates_1_to_5_allowed():
    for digit in [1, 2, 3, 4, 5]:
        plate = f"ABC12{digit}"
        result = check_pico_y_placa(plate, now=dt(2026, 3, 3, 10, 0))
        assert result.has_restriction is False, f"Expected no restriction for plate ending {digit} on odd day (day=3)"


# ---------------------------------------------------------------------------
# Plate format validation
# ---------------------------------------------------------------------------

def test_plate_case_insensitive():
    result_lower = check_pico_y_placa("abc123", now=dt(2026, 3, 16, 10, 0))
    result_upper = check_pico_y_placa("ABC123", now=dt(2026, 3, 16, 10, 0))
    assert result_lower.has_restriction == result_upper.has_restriction
    assert result_lower.plate == "ABC123"


def test_plate_with_hyphen_rejected():
    response = client.get("/pico-y-placa/ABC-123")
    assert response.status_code == 422


def test_plate_too_short_rejected():
    response = client.get("/pico-y-placa/AB123")
    assert response.status_code == 422


def test_plate_too_long_rejected():
    response = client.get("/pico-y-placa/ABCD123")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

def test_valid_plate_returns_200():
    response = client.get("/pico-y-placa/ABC123")
    assert response.status_code == 200


def test_invalid_plate_returns_422():
    response = client.get("/pico-y-placa/INVALID")
    assert response.status_code == 422


def test_response_has_required_fields():
    response = client.get("/pico-y-placa/ABC123")
    assert response.status_code == 200
    data = response.json()
    assert "plate" in data
    assert "has_restriction" in data
    assert "reason" in data
    assert "checked_at" in data


# ---------------------------------------------------------------------------
# `at` query parameter tests
# ---------------------------------------------------------------------------

def test_at_naive_datetime_restricted():
    # 2026-03-16 is an even day; plate ending 1 is restricted on even days during hours
    response = client.get("/pico-y-placa/ABC121?at=2026-03-16T08:00:00")
    assert response.status_code == 200
    assert response.json()["has_restriction"] is True


def test_at_aware_datetime_restricted():
    # Same scenario but with explicit Bogotá UTC-5 offset
    response = client.get("/pico-y-placa/ABC121?at=2026-03-16T08:00:00-05:00")
    assert response.status_code == 200
    assert response.json()["has_restriction"] is True


def test_at_weekend_no_restriction():
    # 2026-03-14 is a Saturday — no restriction for any plate
    response = client.get("/pico-y-placa/ABC121?at=2026-03-14T10:00:00")
    assert response.status_code == 200
    assert response.json()["has_restriction"] is False


def test_at_invalid_value_returns_422():
    response = client.get("/pico-y-placa/ABC123?at=not-a-date")
    assert response.status_code == 422
