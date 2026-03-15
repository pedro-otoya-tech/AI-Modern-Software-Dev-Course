"""
FastAPI application for the Pico y Placa checker.
"""
import re
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.pico_y_placa import check_pico_y_placa

app = FastAPI(title="Pico y Placa API", description="Check vehicle restriction in Bogotá, Colombia.")

PLATE_REGEX = re.compile(r'^[A-Za-z]{3}\d{3}$')  # Strictly 3 letters + 3 digits, no hyphens


class PicoYPlacaResponse(BaseModel):
    plate: str
    has_restriction: bool
    reason: str
    checked_at: datetime


@app.get("/pico-y-placa/{plate}", response_model=PicoYPlacaResponse)
def get_pico_y_placa(plate: str):
    """
    Check whether a license plate has a Pico y Placa restriction right now.

    - **plate**: License plate in format `ABC123` (3 letters + 3 digits, no hyphens).
    """
    if not PLATE_REGEX.match(plate):
        raise HTTPException(status_code=422, detail="Invalid plate format. Expected: ABC123 (3 letters + 3 digits, no hyphens).")
    result = check_pico_y_placa(plate)
    return PicoYPlacaResponse(
        plate=result.plate,
        has_restriction=result.has_restriction,
        reason=result.reason,
        checked_at=result.checked_at,
    )
