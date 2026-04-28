"""
Tests for nws_service — pure helpers, poll_latest, fetch_observations_since,
simulate_greenhouse_reading, and backfill (token-missing + HTTP-error paths only).

httpx.AsyncClient is mocked throughout to avoid real HTTP calls.

NOTE: backfill() success path is not tested here because _deg_to_compass is
referenced on line 190 of nws_service.py but is not defined or imported —
calling backfill() with a WDF2 observation would raise NameError at runtime.
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.nws_service import (
    _c_to_f,
    _ms_to_mph,
    backfill,
    fetch_observations_since,
    poll_latest,
    simulate_greenhouse_reading,
)

pytestmark = pytest.mark.asyncio


def _make_httpx_cm(response: MagicMock) -> MagicMock:
    """Wrap a mock response in the async context manager returned by httpx.AsyncClient()."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _nws_props_response(
    temp_c=20.0,
    humidity=60.0,
    timestamp="2026-04-28T12:00:00+00:00",
    wind_ms=5.0,
    wind_deg=270.0,
) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "properties": {
            "temperature": {"value": temp_c},
            "relativeHumidity": {"value": humidity},
            "timestamp": timestamp,
            "windSpeed": {"value": wind_ms},
            "windDirection": {"value": wind_deg},
        }
    }
    return resp


# ── Pure helpers ──────────────────────────────────────────────────────────────

def test_c_to_f_freezing():
    assert _c_to_f(0.0) == 32.0


def test_c_to_f_boiling():
    assert abs(_c_to_f(100.0) - 212.0) < 0.001


def test_c_to_f_body_temp():
    assert abs(_c_to_f(37.0) - 98.6) < 0.01


def test_ms_to_mph_zero():
    assert _ms_to_mph(0.0) == 0.0


def test_ms_to_mph_one():
    assert abs(_ms_to_mph(1.0) - 2.23694) < 0.001


# ── poll_latest ───────────────────────────────────────────────────────────────

async def test_poll_latest_returns_observation():
    resp = _nws_props_response(temp_c=20.0, humidity=65.0)
    with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
        result = await poll_latest("KMTO")

    assert result is not None
    assert abs(result["temp_f"] - 68.0) < 0.2
    assert result["humidity"] == 65.0
    assert isinstance(result["observed_at"], datetime)
    assert result["wind_speed"] is not None
    assert result["wind_direction"] is not None


async def test_poll_latest_null_temp_and_humidity():
    """None sensor values from NWS are preserved as None in the result."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "properties": {
            "temperature": {"value": None},
            "relativeHumidity": {"value": None},
            "timestamp": "2026-04-28T12:00:00+00:00",
            "windSpeed": None,
            "windDirection": None,
        }
    }
    with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
        result = await poll_latest("KMTO")

    assert result is not None
    assert result["temp_f"] is None
    assert result["humidity"] is None
    assert result["wind_speed"] is None
    assert result["wind_direction"] is None


async def test_poll_latest_returns_none_when_timestamp_missing():
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "properties": {
            "temperature": {"value": 20.0},
            "relativeHumidity": {"value": 60.0},
            "timestamp": None,
            "windSpeed": None,
            "windDirection": None,
        }
    }
    with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
        result = await poll_latest("KMTO")

    assert result is None


async def test_poll_latest_returns_none_on_http_error():
    """HTTPError is caught inside poll_latest — returns None, no retry triggered."""
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPError("NWS unavailable")
    with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
        result = await poll_latest("KMTO")

    assert result is None


# ── fetch_observations_since ──────────────────────────────────────────────────

async def test_fetch_observations_since_returns_results():
    since = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    after = datetime(2026, 4, 28, 0, 0, 0, tzinfo=timezone.utc)

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "features": [
            {
                "properties": {
                    "timestamp": after.isoformat(),
                    "temperature": {"value": 18.0},
                    "relativeHumidity": {"value": 70.0},
                    "windSpeed": {"value": 3.0},
                    "windDirection": {"value": 180.0},
                }
            }
        ]
    }
    with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
        result = await fetch_observations_since("KMTO", since)

    assert len(result) == 1
    assert abs(result[0]["temp_f"] - 64.4) < 0.2
    assert result[0]["humidity"] == 70.0
    assert result[0]["observed_at"] == after


async def test_fetch_observations_skips_old_timestamps():
    """Observations at or before `since` are excluded."""
    since = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "features": [
            {
                "properties": {
                    "timestamp": since.isoformat(),  # exactly at `since`, not after
                    "temperature": {"value": 18.0},
                    "relativeHumidity": {"value": 60.0},
                    "windSpeed": None,
                    "windDirection": None,
                }
            }
        ]
    }
    with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
        result = await fetch_observations_since("KMTO", since)

    assert result == []


async def test_fetch_observations_skips_missing_timestamp():
    """Features with no timestamp property are skipped."""
    since = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "features": [
            {"properties": {"timestamp": None, "temperature": {"value": 18.0}}}
        ]
    }
    with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
        result = await fetch_observations_since("KMTO", since)

    assert result == []


async def test_fetch_observations_returns_empty_on_http_error():
    since = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)

    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPError("timeout")
    with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
        result = await fetch_observations_since("KMTO", since)

    assert result == []


async def test_fetch_observations_null_wind_values():
    """None wind values from NWS are preserved as None."""
    since = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    after = datetime(2026, 4, 28, 0, 0, 0, tzinfo=timezone.utc)

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "features": [
            {
                "properties": {
                    "timestamp": after.isoformat(),
                    "temperature": {"value": 20.0},
                    "relativeHumidity": {"value": 65.0},
                    "windSpeed": None,
                    "windDirection": None,
                }
            }
        ]
    }
    with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
        result = await fetch_observations_since("KMTO", since)

    assert len(result) == 1
    assert result[0]["wind_speed"] is None
    assert result[0]["wind_direction"] is None


# ── backfill (CDO) ────────────────────────────────────────────────────────────

async def test_backfill_no_cdo_token_returns_empty():
    """Without NOAA_CDO_TOKEN, backfill exits at the guard and returns []."""
    with patch("app.services.nws_service.settings") as mock_settings:
        mock_settings.NOAA_CDO_TOKEN = None
        result = await backfill("USC00406271", date(2026, 1, 1), date(2026, 3, 31))

    assert result == []


async def test_backfill_http_error_returns_empty():
    """CDO HTTP failure is caught — returns empty list, no exception raised."""
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPError("CDO unavailable")

    with patch("app.services.nws_service.settings") as mock_settings:
        mock_settings.NOAA_CDO_TOKEN = "test-token"
        with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
            result = await backfill("USC00406271", date(2026, 1, 1), date(2026, 3, 31))

    assert result == []


async def test_backfill_skips_dates_without_temp():
    """CDO rows with no TAVG/TMAX/TMIN are excluded from results."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "results": [
            {"date": "2026-01-15T00:00:00", "datatype": "RHAV", "value": 65.0},
            # No temperature datatype — this date should be skipped
        ]
    }
    with patch("app.services.nws_service.settings") as mock_settings:
        mock_settings.NOAA_CDO_TOKEN = "test-token"
        with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
            result = await backfill("USC00406271", date(2026, 1, 1), date(2026, 3, 31))

    assert result == []


async def test_backfill_uses_tavg_when_available():
    """TAVG takes precedence over TMAX/TMIN average; WDF2 absent avoids _deg_to_compass."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "results": [
            {"date": "2026-01-15T00:00:00", "datatype": "TAVG", "value": 100},  # 10.0 °C
            {"date": "2026-01-15T00:00:00", "datatype": "RHAV", "value": 65.0},
            # AWND present, WDF2 absent → wind_direction=None (no _deg_to_compass call)
            {"date": "2026-01-15T00:00:00", "datatype": "AWND", "value": 30},
        ]
    }
    with patch("app.services.nws_service.settings") as mock_settings:
        mock_settings.NOAA_CDO_TOKEN = "test-token"
        with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
            result = await backfill("USC00406271", date(2026, 1, 1), date(2026, 3, 31))

    assert len(result) == 1
    assert abs(result[0]["temp_f"] - 50.0) < 0.1   # 10°C = 50°F
    assert result[0]["humidity"] == 65.0
    assert result[0]["wind_direction"] is None       # WDF2 absent


async def test_backfill_uses_tmax_tmin_when_no_tavg():
    """Falls back to (TMAX + TMIN) / 2 when TAVG is absent."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "results": [
            {"date": "2026-01-15T00:00:00", "datatype": "TMAX", "value": 200},  # 20°C in tenths
            {"date": "2026-01-15T00:00:00", "datatype": "TMIN", "value": 100},  # 10°C in tenths
        ]
    }
    with patch("app.services.nws_service.settings") as mock_settings:
        mock_settings.NOAA_CDO_TOKEN = "test-token"
        with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
            result = await backfill("USC00406271", date(2026, 1, 1), date(2026, 3, 31))

    assert len(result) == 1
    assert abs(result[0]["temp_f"] - 59.0) < 0.2   # (200+100)/20 = 15°C = 59°F
    assert result[0]["humidity"] == 50.0             # RHAV absent → neutral 50.0


# ── simulate_greenhouse_reading ───────────────────────────────────────────────

async def test_simulate_greenhouse_active_mode_with_target():
    """Active mode: tight HVAC control — temp and humidity near setpoint."""
    area = SimpleNamespace(
        target_temp_f=72.0,
        target_humidity_pct=65.0,
        nws_station_id=None,
    )

    result = await simulate_greenhouse_reading(area)

    assert result is not None
    assert abs(result["temp_f"] - 72.0) < 4.0      # ±1.5°F noise, 4°F margin
    assert 0 < result["humidity"] <= 100.0
    assert isinstance(result["observed_at"], datetime)


async def test_simulate_greenhouse_active_mode_no_humidity_target():
    """Active mode without target_humidity_pct falls back to config default."""
    area = SimpleNamespace(
        target_temp_f=68.0,
        target_humidity_pct=None,
        nws_station_id=None,
    )

    result = await simulate_greenhouse_reading(area)

    assert result is not None
    assert abs(result["temp_f"] - 68.0) < 4.0


async def test_simulate_greenhouse_passive_no_station_returns_none():
    """Passive mode with no NWS station ID → cannot fetch ambient → None."""
    area = SimpleNamespace(
        target_temp_f=None,
        nws_station_id=None,
    )

    result = await simulate_greenhouse_reading(area)

    assert result is None


async def test_simulate_greenhouse_passive_applies_offset():
    """Passive mode: ambient NWS reading + static temp and humidity offsets."""
    area = SimpleNamespace(
        target_temp_f=None,
        nws_station_id="KMTO",
        temp_offset_f=5.0,
        humidity_offset_pct=10.0,
    )

    resp = _nws_props_response(temp_c=20.0, humidity=60.0)  # 20°C = 68°F
    with patch("app.services.nws_service.httpx.AsyncClient", return_value=_make_httpx_cm(resp)):
        result = await simulate_greenhouse_reading(area)

    assert result is not None
    assert abs(result["temp_f"] - 73.0) < 0.2    # 68 + 5 offset
    assert result["humidity"] == 70.0              # 60 + 10 offset


async def test_simulate_greenhouse_passive_poll_fails_returns_none():
    """Passive mode: if poll_latest returns None (NWS down), result is None."""
    area = SimpleNamespace(
        target_temp_f=None,
        nws_station_id="KMTO",
        temp_offset_f=0.0,
        humidity_offset_pct=0.0,
    )

    with patch("app.services.nws_service.poll_latest", new=AsyncMock(return_value=None)):
        result = await simulate_greenhouse_reading(area)

    assert result is None
