"""
NWS / NOAA weather data service.

Two data sources:
  poll_latest()  — api.weather.gov observations endpoint (7-day rolling window).
                   Used for ongoing polling every NWS_POLL_INTERVAL_HOURS.
  backfill()     — NOAA Climate Data Online (CDO) API (decades of history).
                   Used once per station for historical seed data.

fIoT simulation:
  simulate_greenhouse_reading() — applies per-GrowingArea offsets or setpoints
  to NWS ambient data to produce realistic greenhouse sensor readings.
"""

import logging
import random
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

if TYPE_CHECKING:
    from app.models.field import GrowingArea

logger = logging.getLogger(__name__)

_NWS_BASE = settings.NOAA_BASE_URL
_CDO_BASE = "https://www.ncei.noaa.gov/cdo-web/api/v2"
_HEADERS = {"User-Agent": settings.NOAA_USER_AGENT, "Accept": "application/geo+json"}


def _c_to_f(celsius: float) -> float:
    return (celsius * 9 / 5) + 32


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def poll_latest(station_id: str) -> dict | None:
    """
    Fetch the latest observation from api.weather.gov.
    Returns {temp_f, humidity, observed_at} or None if unavailable.
    """
    url = f"{_NWS_BASE}/stations/{station_id}/observations/latest"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=_HEADERS)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("NWS poll failed for %s: %s", station_id, exc)
        return None

    props = resp.json().get("properties", {})
    temp_c = (props.get("temperature") or {}).get("value")
    humidity = (props.get("relativeHumidity") or {}).get("value")
    timestamp = props.get("timestamp")

    if temp_c is None or humidity is None or timestamp is None:
        logger.warning("NWS response missing fields for %s", station_id)
        return None

    return {
        "temp_f": _c_to_f(temp_c),
        "humidity": float(humidity),
        "observed_at": datetime.fromisoformat(timestamp),
    }


async def backfill(
    station_id: str,
    start: date,
    end: date,
) -> list[dict]:
    """
    Fetch daily summary data from NOAA CDO for historical seeding.
    Requires NOAA_CDO_TOKEN in config (free at ncei.noaa.gov/cdo-web/token).
    Returns list of {temp_f, humidity, observed_at}.
    """
    if not settings.NOAA_CDO_TOKEN:
        logger.warning("NOAA_CDO_TOKEN not set — skipping CDO backfill for %s", station_id)
        return []

    params = {
        "datasetid": "GHCND",
        "stationid": f"GHCND:{station_id}",
        "datatypeid": "TAVG,RHUM",
        "startdate": start.isoformat(),
        "enddate": end.isoformat(),
        "units": "metric",
        "limit": 1000,
    }
    headers = {"token": settings.NOAA_CDO_TOKEN}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{_CDO_BASE}/data", params=params, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("CDO backfill failed for %s: %s", station_id, exc)
        return []

    results: list[dict] = []
    by_date: dict[str, dict] = {}

    for item in resp.json().get("results", []):
        dt = item.get("date", "")[:10]
        by_date.setdefault(dt, {})[item["datatype"]] = item["value"]

    for dt_str, values in by_date.items():
        tavg = values.get("TAVG")
        rhum = values.get("RHUM")
        if tavg is None or rhum is None:
            continue
        results.append({
            "temp_f": _c_to_f(tavg / 10),  # CDO TAVG is tenths of °C
            "humidity": float(rhum),
            "observed_at": datetime.fromisoformat(f"{dt_str}T12:00:00+00:00"),
        })

    return results


async def simulate_greenhouse_reading(area: "GrowingArea") -> dict | None:
    """
    Produce a fIoT reading for a DWC greenhouse GrowingArea.

    Active mode (target_temp_f set): HVAC / portable equipment holding a setpoint.
      Simulates tight climate control with ±1.5°F / ±3% noise.
      GH1 (portable equipment) and GH2 (commercial HVAC) use the same model;
      GH1's real-world variance is wider but acceptable for demo fidelity.

    Passive mode (no target): ambient NWS + static offset.
      Used for GH1 when portable equipment is packed away for the season.
      Temperature tracks outdoor conditions with a fixed bump.
    """
    if area.target_temp_f is not None:
        return {
            "temp_f": area.target_temp_f + random.gauss(0, 1.5),
            "humidity": min(100.0, (area.target_humidity_pct or 65.0) + random.gauss(0, 3.0)),
            "observed_at": datetime.now(timezone.utc),
        }

    if not area.nws_station_id:
        return None

    ambient = await poll_latest(area.nws_station_id)
    if ambient is None:
        return None

    return {
        "temp_f": ambient["temp_f"] + (area.temp_offset_f or 0.0),
        "humidity": min(100.0, ambient["humidity"] + (area.humidity_offset_pct or 0.0)),
        "observed_at": ambient["observed_at"],
    }
