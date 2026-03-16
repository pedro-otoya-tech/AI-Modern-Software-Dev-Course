"""
FastAPI application for the Pico y Placa checker.
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.pico_y_placa import check_pico_y_placa

app = FastAPI(title="Pico y Placa API", description="Check vehicle restriction in Bogotá, Colombia.")

PLATE_REGEX = re.compile(r'^[A-Za-z]{3}\d{3}$')  # Strictly 3 letters + 3 digits, no hyphens
BOGOTA_TZ = ZoneInfo("America/Bogota")


class PicoYPlacaResponse(BaseModel):
    plate: str
    has_restriction: bool
    reason: str
    checked_at: datetime


@app.get("/pico-y-placa/{plate}", response_model=PicoYPlacaResponse)
def get_pico_y_placa(plate: str, at: datetime | None = None):
    """
    Check whether a license plate has a Pico y Placa restriction.

    - **plate**: License plate in format `ABC123` (3 letters + 3 digits, no hyphens).
    - **at**: Optional ISO 8601 datetime to check (defaults to now). Naive datetimes are treated as Bogotá time.
    """
    if not PLATE_REGEX.match(plate):
        raise HTTPException(status_code=422, detail="Invalid plate format. Expected: ABC123 (3 letters + 3 digits, no hyphens).")
    if at is not None and at.tzinfo is None:
        at = at.replace(tzinfo=BOGOTA_TZ)
    result = check_pico_y_placa(plate, now=at)
    return PicoYPlacaResponse(
        plate=result.plate,
        has_restriction=result.has_restriction,
        reason=result.reason,
        checked_at=result.checked_at,
    )
