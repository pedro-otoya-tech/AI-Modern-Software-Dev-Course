"""
Pico y Placa restriction logic for Bogotá, Colombia.

Rules (private vehicles):
- Active window: Monday–Friday, 6:00 AM – 9:00 PM (Bogotá time)
- Odd calendar day  → plates ending in 6, 7, 8, 9, 0 are RESTRICTED
- Even calendar day → plates ending in 1, 2, 3, 4, 5 are RESTRICTED
- Weekends & Colombian public holidays → no restriction
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import holidays

BOGOTA_TZ = ZoneInfo("America/Bogota")
RESTRICTION_START = 6   # 6 AM
RESTRICTION_END = 21    # 9 PM (exclusive — 21:00:00 means "just ended")

ODD_DAY_RESTRICTED = {6, 7, 8, 9, 0}
EVEN_DAY_RESTRICTED = {1, 2, 3, 4, 5}

_co_holidays = holidays.Colombia()


@dataclass
class PicoYPlacaResult:
    plate: str
    has_restriction: bool
    reason: str
    checked_at: datetime


def _would_be_restricted_today(last_digit: int, day: int) -> bool:
    """Return True if the plate digit is in the restricted set for this calendar day."""
    restricted = ODD_DAY_RESTRICTED if day % 2 == 1 else EVEN_DAY_RESTRICTED
    return last_digit in restricted


def check_pico_y_placa(plate: str, now: datetime | None = None) -> PicoYPlacaResult:
    """
    Check whether a plate has a Pico y Placa restriction right now.

    :param plate: License plate string (e.g. "ABC123"). Case-insensitive; no hyphens.
    :param now:   Optional datetime (tz-aware, Bogotá TZ) for testing. Defaults to current time.
    """
    plate = plate.upper()

    if now is None:
        now = datetime.now(tz=BOGOTA_TZ)
    else:
        # Ensure the datetime is expressed in Bogotá time
        now = now.astimezone(BOGOTA_TZ)

    last_digit = int(plate[-1])
    date = now.date()
    hour = now.hour
    minute = now.minute

    # --- Weekend ---
    if date.weekday() >= 5:  # 5=Saturday, 6=Sunday
        day_name = "Saturday" if date.weekday() == 5 else "Sunday"
        return PicoYPlacaResult(
            plate=plate,
            has_restriction=False,
            reason=f"No restriction on weekends ({day_name}).",
            checked_at=now,
        )

    # --- Colombian public holiday ---
    if date in _co_holidays:
        holiday_name = _co_holidays.get(date, "public holiday")
        return PicoYPlacaResult(
            plate=plate,
            has_restriction=False,
            reason=f"No restriction — today is a public holiday ({holiday_name}).",
            checked_at=now,
        )

    # --- Determine if this plate would be restricted on today's calendar day ---
    restricted_today = _would_be_restricted_today(last_digit, date.day)

    # --- After restriction window (>= 21:00) ---
    if hour >= RESTRICTION_END:
        if restricted_today:
            return PicoYPlacaResult(
                plate=plate,
                has_restriction=False,
                reason=f"Restriction has ended for today. Plate ending in {last_digit} was restricted today.",
                checked_at=now,
            )
        return PicoYPlacaResult(
            plate=plate,
            has_restriction=False,
            reason=f"No restriction. Plate ending in {last_digit} is not in today's restricted group.",
            checked_at=now,
        )

    # --- Before restriction window (< 6:00 AM) ---
    if hour < RESTRICTION_START:
        if restricted_today:
            # Countdown to 6:00 AM
            minutes_remaining = (RESTRICTION_START * 60) - (hour * 60 + minute)
            hours_left = minutes_remaining // 60
            mins_left = minutes_remaining % 60
            return PicoYPlacaResult(
                plate=plate,
                has_restriction=True,
                reason=(
                    f"Plate ending in {last_digit} is restricted today "
                    f"({'odd' if date.day % 2 == 1 else 'even'} day). "
                    f"Restriction starts at 6:00 AM. "
                    f"You have {hours_left}h {mins_left}m to reach your destination."
                ),
                checked_at=now,
            )
        return PicoYPlacaResult(
            plate=plate,
            has_restriction=False,
            reason=f"No restriction. Plate ending in {last_digit} is not in today's restricted group.",
            checked_at=now,
        )

    # --- During restriction window (6 AM ≤ hour < 9 PM) ---
    if restricted_today:
        day_type = "odd" if date.day % 2 == 1 else "even"
        return PicoYPlacaResult(
            plate=plate,
            has_restriction=True,
            reason=f"Plate ending in {last_digit} is restricted on {day_type} days (today is day {date.day}).",
            checked_at=now,
        )

    return PicoYPlacaResult(
        plate=plate,
        has_restriction=False,
        reason=f"No restriction. Plate ending in {last_digit} is not restricted today (day {date.day}).",
        checked_at=now,
    )
