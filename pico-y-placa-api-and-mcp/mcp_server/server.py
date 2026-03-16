import os
import httpx
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastmcp import FastMCP

BOGOTA_TZ = ZoneInfo("America/Bogota")
PICO_Y_PLACA_API_URL = os.getenv("PICO_Y_PLACA_API_URL", "http://localhost:8000")
OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"

mcp = FastMCP("pico-y-placa")


@mcp.tool()
async def check_restriction(plate: str, at: str | None = None) -> dict:
    """Check Pico y Placa restriction in Bogotá for a car plate."""
    params = {"at": at} if at else {}
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PICO_Y_PLACA_API_URL}/pico-y-placa/{plate}", params=params)
    if resp.status_code == 422:
        raise ValueError(resp.json().get("detail", "Invalid request"))
    resp.raise_for_status()
    data = resp.json()
    return {
        "plate": data["plate"],
        "allowed": not data["has_restriction"],
        "reason": data["reason"],
        "checked_at": data["checked_at"],
    }


@mcp.tool()
async def plan_departure(
    plate: str,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    safety_margin_minutes: int = 0,
    date: str | None = None,
) -> dict:
    """Calculate latest departure time from origin to reach destination before Pico y Placa restriction starts."""
    if not (0 <= safety_margin_minutes <= 30):
        raise ValueError("safety_margin_minutes must be between 0 and 30")

    if date is None:
        date = datetime.now(tz=BOGOTA_TZ).date().isoformat()

    # OSRM: coordinates are lon,lat order
    osrm_url = f"{OSRM_BASE}/{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    async with httpx.AsyncClient() as client:
        osrm_resp = await client.get(osrm_url)
    osrm_resp.raise_for_status()
    drive_seconds = osrm_resp.json()["routes"][0]["duration"]

    # Check restriction at 6 AM on the target date
    check_at = f"{date}T06:00:00"
    async with httpx.AsyncClient() as client:
        api_resp = await client.get(
            f"{PICO_Y_PLACA_API_URL}/pico-y-placa/{plate}", params={"at": check_at}
        )
    api_resp.raise_for_status()
    api_data = api_resp.json()

    if not api_data["has_restriction"]:
        return {
            "plate": plate,
            "date": date,
            "has_restriction": False,
            "message": "No restriction on this date, you can leave any time",
        }

    restriction_start = datetime.fromisoformat(f"{date}T06:00:00")
    departure_dt = (
        restriction_start
        - timedelta(seconds=drive_seconds)
        - timedelta(minutes=safety_margin_minutes)
    )
    drive_min = round(drive_seconds / 60, 1)
    return {
        "plate": plate,
        "date": date,
        "has_restriction": True,
        "departure_time": departure_dt.strftime("%H:%M:%S"),
        "drive_duration_minutes": drive_min,
        "safety_margin_minutes": safety_margin_minutes,
        "restriction_starts_at": "06:00:00",
        "message": (
            f"Leave by {departure_dt.strftime('%H:%M')} — "
            f"drive time: {drive_min} min, safety margin: {safety_margin_minutes} min"
        ),
    }


if __name__ == "__main__":
    mcp.run()  # stdio transport for Claude Desktop
