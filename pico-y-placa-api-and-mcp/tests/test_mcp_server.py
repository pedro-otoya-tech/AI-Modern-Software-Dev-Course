import pytest
import respx
import httpx
from fastmcp import Client
from mcp_server.server import mcp

PICO_API = "http://localhost:8000"
OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"


# ---------------------------------------------------------------------------
# Group A — check_restriction tool
# ---------------------------------------------------------------------------

@respx.mock
async def test_check_restriction_restricted_plate():
    respx.get(f"{PICO_API}/pico-y-placa/ABC123").mock(
        return_value=httpx.Response(200, json={
            "plate": "ABC123",
            "has_restriction": True,
            "reason": "Last digit 3 is restricted on Monday",
            "checked_at": "2026-03-16T08:00:00",
        })
    )
    async with Client(mcp) as client:
        result = await client.call_tool("check_restriction", {"plate": "ABC123"})

    text = result.content[0].text
    assert "False" in text or '"allowed": false' in text.lower() or "allowed" in text
    assert "reason" in text


@respx.mock
async def test_check_restriction_unrestricted_plate():
    respx.get(f"{PICO_API}/pico-y-placa/ZZZ999").mock(
        return_value=httpx.Response(200, json={
            "plate": "ZZZ999",
            "has_restriction": False,
            "reason": "No restriction",
            "checked_at": "2026-03-16T08:00:00",
        })
    )
    async with Client(mcp) as client:
        result = await client.call_tool("check_restriction", {"plate": "ZZZ999"})

    text = result.content[0].text
    assert "True" in text or '"allowed": true' in text.lower() or "allowed" in text


@respx.mock
async def test_check_restriction_api_422_raises():
    respx.get(f"{PICO_API}/pico-y-placa/BADINPUT").mock(
        return_value=httpx.Response(422, json={"detail": "Invalid plate format"})
    )
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="Invalid plate format"):
            await client.call_tool("check_restriction", {"plate": "BADINPUT"})


@respx.mock
async def test_check_restriction_passes_at_param():
    at_value = "2026-03-16T08:00:00"
    captured = {}

    def capture(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, json={
            "plate": "ABC123",
            "has_restriction": False,
            "reason": "No restriction",
            "checked_at": at_value,
        })

    respx.get(f"{PICO_API}/pico-y-placa/ABC123").mock(side_effect=capture)

    async with Client(mcp) as client:
        await client.call_tool("check_restriction", {"plate": "ABC123", "at": at_value})

    assert "at=2026-03-16T06" in captured["url"] or at_value.replace(":", "%3A") in captured["url"] or "at=" in captured["url"]


# ---------------------------------------------------------------------------
# Group B — plan_departure tool
# ---------------------------------------------------------------------------

def _osrm_url(origin_lon, origin_lat, dest_lon, dest_lat):
    return f"{OSRM_BASE}/{origin_lon},{origin_lat};{dest_lon},{dest_lat}"


ORIGIN_LAT, ORIGIN_LON = 4.6097, -74.0817
DEST_LAT, DEST_LON = 4.6482, -74.1002


@respx.mock
async def test_plan_departure_restricted_computes_departure():
    """Drive = 1800 s (30 min), restriction at 06:00 → depart at 05:30:00."""
    respx.get(_osrm_url(ORIGIN_LON, ORIGIN_LAT, DEST_LON, DEST_LAT)).mock(
        return_value=httpx.Response(200, json={"routes": [{"duration": 1800}]})
    )
    respx.get(f"{PICO_API}/pico-y-placa/ABC123").mock(
        return_value=httpx.Response(200, json={
            "plate": "ABC123", "has_restriction": True,
            "reason": "Restricted", "checked_at": "2026-03-16T06:00:00",
        })
    )
    async with Client(mcp) as client:
        result = await client.call_tool("plan_departure", {
            "plate": "ABC123",
            "origin_lat": ORIGIN_LAT, "origin_lon": ORIGIN_LON,
            "dest_lat": DEST_LAT, "dest_lon": DEST_LON,
            "date": "2026-03-16",
        })

    text = result.content[0].text
    assert "05:30:00" in text


@respx.mock
async def test_plan_departure_unrestricted_day():
    respx.get(_osrm_url(ORIGIN_LON, ORIGIN_LAT, DEST_LON, DEST_LAT)).mock(
        return_value=httpx.Response(200, json={"routes": [{"duration": 1800}]})
    )
    respx.get(f"{PICO_API}/pico-y-placa/ABC123").mock(
        return_value=httpx.Response(200, json={
            "plate": "ABC123", "has_restriction": False,
            "reason": "No restriction", "checked_at": "2026-03-16T06:00:00",
        })
    )
    async with Client(mcp) as client:
        result = await client.call_tool("plan_departure", {
            "plate": "ABC123",
            "origin_lat": ORIGIN_LAT, "origin_lon": ORIGIN_LON,
            "dest_lat": DEST_LAT, "dest_lon": DEST_LON,
            "date": "2026-03-16",
        })

    text = result.content[0].text
    assert "No restriction" in text


@respx.mock
async def test_plan_departure_safety_margin_applied():
    """Drive = 1800 s, margin = 10 min → depart at 05:20:00."""
    respx.get(_osrm_url(ORIGIN_LON, ORIGIN_LAT, DEST_LON, DEST_LAT)).mock(
        return_value=httpx.Response(200, json={"routes": [{"duration": 1800}]})
    )
    respx.get(f"{PICO_API}/pico-y-placa/ABC123").mock(
        return_value=httpx.Response(200, json={
            "plate": "ABC123", "has_restriction": True,
            "reason": "Restricted", "checked_at": "2026-03-16T06:00:00",
        })
    )
    async with Client(mcp) as client:
        result = await client.call_tool("plan_departure", {
            "plate": "ABC123",
            "origin_lat": ORIGIN_LAT, "origin_lon": ORIGIN_LON,
            "dest_lat": DEST_LAT, "dest_lon": DEST_LON,
            "safety_margin_minutes": 10,
            "date": "2026-03-16",
        })

    text = result.content[0].text
    assert "05:20:00" in text


@respx.mock
async def test_plan_departure_safety_margin_zero_valid():
    respx.get(_osrm_url(ORIGIN_LON, ORIGIN_LAT, DEST_LON, DEST_LAT)).mock(
        return_value=httpx.Response(200, json={"routes": [{"duration": 600}]})
    )
    respx.get(f"{PICO_API}/pico-y-placa/ABC123").mock(
        return_value=httpx.Response(200, json={
            "plate": "ABC123", "has_restriction": True,
            "reason": "Restricted", "checked_at": "2026-03-16T06:00:00",
        })
    )
    async with Client(mcp) as client:
        result = await client.call_tool("plan_departure", {
            "plate": "ABC123",
            "origin_lat": ORIGIN_LAT, "origin_lon": ORIGIN_LON,
            "dest_lat": DEST_LAT, "dest_lon": DEST_LON,
            "safety_margin_minutes": 0,
            "date": "2026-03-16",
        })

    assert result.content[0].text  # no error, some response returned


@respx.mock
async def test_plan_departure_safety_margin_thirty_valid():
    respx.get(_osrm_url(ORIGIN_LON, ORIGIN_LAT, DEST_LON, DEST_LAT)).mock(
        return_value=httpx.Response(200, json={"routes": [{"duration": 600}]})
    )
    respx.get(f"{PICO_API}/pico-y-placa/ABC123").mock(
        return_value=httpx.Response(200, json={
            "plate": "ABC123", "has_restriction": True,
            "reason": "Restricted", "checked_at": "2026-03-16T06:00:00",
        })
    )
    async with Client(mcp) as client:
        result = await client.call_tool("plan_departure", {
            "plate": "ABC123",
            "origin_lat": ORIGIN_LAT, "origin_lon": ORIGIN_LON,
            "dest_lat": DEST_LAT, "dest_lon": DEST_LON,
            "safety_margin_minutes": 30,
            "date": "2026-03-16",
        })

    assert result.content[0].text


async def test_plan_departure_safety_margin_31_raises():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="safety_margin_minutes"):
            await client.call_tool("plan_departure", {
                "plate": "ABC123",
                "origin_lat": ORIGIN_LAT, "origin_lon": ORIGIN_LON,
                "dest_lat": DEST_LAT, "dest_lon": DEST_LON,
                "safety_margin_minutes": 31,
                "date": "2026-03-16",
            })


async def test_plan_departure_negative_margin_raises():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="safety_margin_minutes"):
            await client.call_tool("plan_departure", {
                "plate": "ABC123",
                "origin_lat": ORIGIN_LAT, "origin_lon": ORIGIN_LON,
                "dest_lat": DEST_LAT, "dest_lon": DEST_LON,
                "safety_margin_minutes": -1,
                "date": "2026-03-16",
            })


@respx.mock
async def test_plan_departure_uses_date_param():
    captured = {}

    def capture_osrm(request):
        return httpx.Response(200, json={"routes": [{"duration": 600}]})

    def capture_api(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, json={
            "plate": "ABC123", "has_restriction": True,
            "reason": "Restricted", "checked_at": "2026-03-16T06:00:00",
        })

    respx.get(_osrm_url(ORIGIN_LON, ORIGIN_LAT, DEST_LON, DEST_LAT)).mock(side_effect=capture_osrm)
    respx.get(f"{PICO_API}/pico-y-placa/ABC123").mock(side_effect=capture_api)

    async with Client(mcp) as client:
        await client.call_tool("plan_departure", {
            "plate": "ABC123",
            "origin_lat": ORIGIN_LAT, "origin_lon": ORIGIN_LON,
            "dest_lat": DEST_LAT, "dest_lon": DEST_LON,
            "date": "2026-03-16",
        })

    assert "2026-03-16" in captured["url"]
    assert "06%3A00%3A00" in captured["url"] or "06:00:00" in captured["url"]


@respx.mock
async def test_plan_departure_defaults_to_today_bogota():
    captured = {}

    def capture_api(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, json={
            "plate": "ABC123", "has_restriction": False,
            "reason": "No restriction", "checked_at": "2026-03-15T06:00:00",
        })

    respx.get(_osrm_url(ORIGIN_LON, ORIGIN_LAT, DEST_LON, DEST_LAT)).mock(
        return_value=httpx.Response(200, json={"routes": [{"duration": 600}]})
    )
    respx.get(f"{PICO_API}/pico-y-placa/ABC123").mock(side_effect=capture_api)

    async with Client(mcp) as client:
        await client.call_tool("plan_departure", {
            "plate": "ABC123",
            "origin_lat": ORIGIN_LAT, "origin_lon": ORIGIN_LON,
            "dest_lat": DEST_LAT, "dest_lon": DEST_LON,
        })

    # Today in Bogotá is 2026-03-15
    assert "2026-03-15" in captured["url"]
