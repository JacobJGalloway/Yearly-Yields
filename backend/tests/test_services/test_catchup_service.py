"""
Tests for catchup_service — run_system_backfill, run_nws_catchup, _backfill_area.

catchup_service manages its own DB sessions via AsyncSessionLocal, so it is
mocked throughout. nws_service.fetch_observations_since is mocked to avoid HTTP.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.field import GrowingAreaType
from app.services.catchup_service import (
    _backfill_area,
    _catchup_area,
    run_nws_catchup,
    run_system_backfill,
)

pytestmark = pytest.mark.asyncio


def _make_area(nws_station_id: str = "KMTO") -> SimpleNamespace:
    """Lightweight stand-in for GrowingArea — only the fields catchup_service reads."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="Catchup Test Field",
        area_type=GrowingAreaType.open_field,
        nws_station_id=nws_station_id,
        is_active=True,
    )


def _make_session_cm(session: AsyncMock) -> MagicMock:
    """Wrap an AsyncMock session in an async context manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _scalars_result(rows: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows
    return r


def _scalar_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _fetchall_result(rows: list) -> MagicMock:
    r = MagicMock()
    r.fetchall.return_value = rows
    return r


# ── run_system_backfill ───────────────────────────────────────────────────────

async def test_run_system_backfill_no_areas():
    """With no active open-field areas, backfill completes silently."""
    session = AsyncMock()
    session.execute.return_value = _scalars_result([])

    mock_factory = MagicMock(return_value=_make_session_cm(session))

    with patch("app.services.catchup_service.AsyncSessionLocal", mock_factory):
        await run_system_backfill()

    session.execute.assert_awaited_once()


async def test_run_system_backfill_exception_logged():
    """Exception from _backfill_area is caught and logged, not re-raised."""
    area = _make_area()
    session = AsyncMock()
    session.execute.return_value = _scalars_result([area])

    mock_factory = MagicMock(return_value=_make_session_cm(session))

    with patch("app.services.catchup_service.AsyncSessionLocal", mock_factory):
        with patch(
            "app.services.catchup_service._backfill_area",
            new=AsyncMock(side_effect=RuntimeError("NWS timeout")),
        ):
            with patch("app.services.catchup_service.logger") as mock_logger:
                await run_system_backfill()

    mock_logger.exception.assert_called_once()


# ── run_nws_catchup ───────────────────────────────────────────────────────────

async def test_run_nws_catchup_no_areas():
    """With no areas for the owner, catch-up completes silently."""
    session = AsyncMock()
    session.execute.return_value = _scalars_result([])

    mock_factory = MagicMock(return_value=_make_session_cm(session))

    with patch("app.services.catchup_service.AsyncSessionLocal", mock_factory):
        await run_nws_catchup(uuid.uuid4())

    session.execute.assert_awaited_once()


async def test_run_nws_catchup_exception_logged():
    """Exception from _backfill_area (catch-up path) is caught and logged."""
    area = _make_area()
    session = AsyncMock()
    session.execute.return_value = _scalars_result([area])

    mock_factory = MagicMock(return_value=_make_session_cm(session))

    with patch("app.services.catchup_service.AsyncSessionLocal", mock_factory):
        with patch(
            "app.services.catchup_service._backfill_area",
            new=AsyncMock(side_effect=RuntimeError("connection refused")),
        ):
            with patch("app.services.catchup_service.logger") as mock_logger:
                await run_nws_catchup(uuid.uuid4())

    mock_logger.exception.assert_called_once()


# ── _backfill_area ────────────────────────────────────────────────────────────

async def test_backfill_area_recent_reading_skipped():
    """Gap < 1 hour → early return without fetching observations."""
    area = _make_area()
    recent = datetime.now(timezone.utc) - timedelta(minutes=30)

    session = AsyncMock()
    session.execute.return_value = _scalar_result(recent)

    mock_factory = MagicMock(return_value=_make_session_cm(session))

    with patch("app.services.catchup_service.AsyncSessionLocal", mock_factory):
        with patch(
            "app.services.catchup_service.nws_service.fetch_observations_since"
        ) as mock_fetch:
            await _backfill_area(area, "test summary")

    mock_fetch.assert_not_called()


async def test_backfill_area_no_prior_readings_no_observations():
    """No prior readings → uses 7-day window. No observations → exits without inserting."""
    area = _make_area()

    session = AsyncMock()
    session.execute.return_value = _scalar_result(None)

    mock_factory = MagicMock(return_value=_make_session_cm(session))

    with patch("app.services.catchup_service.AsyncSessionLocal", mock_factory):
        with patch(
            "app.services.catchup_service.nws_service.fetch_observations_since",
            new=AsyncMock(return_value=[]),
        ):
            await _backfill_area(area, "test summary")

    # Only one session opened — no second session needed since no observations
    assert mock_factory.call_count == 1


async def test_backfill_area_with_observations_inserts_readings():
    """Observations returned → deduplicated and inserted as AssessmentStatus.normal readings."""
    area = _make_area()
    obs_ts = datetime.now(timezone.utc) - timedelta(hours=3)
    observations = [
        {
            "observed_at": obs_ts,
            "temp_f": 72.0,
            "humidity": 65.0,
            "wind_speed": 8.0,
            "wind_direction": "NW",
        }
    ]

    session_1 = AsyncMock()
    session_1.execute.return_value = _scalar_result(None)  # no last reading

    session_2 = AsyncMock()
    session_2.execute.return_value = _fetchall_result([])  # no existing timestamps
    session_2.add = MagicMock()
    session_2.commit = AsyncMock()

    mock_factory = MagicMock(
        side_effect=[_make_session_cm(session_1), _make_session_cm(session_2)]
    )

    with patch("app.services.catchup_service.AsyncSessionLocal", mock_factory):
        with patch(
            "app.services.catchup_service.nws_service.fetch_observations_since",
            new=AsyncMock(return_value=observations),
        ):
            await _backfill_area(area, "Startup backfill — pre-assessed normal.")

    session_2.add.assert_called_once()
    session_2.commit.assert_awaited_once()


async def test_backfill_area_skips_duplicate_timestamp():
    """Observation whose timestamp already exists in DB is not re-inserted."""
    area = _make_area()
    obs_ts = datetime.now(timezone.utc) - timedelta(hours=3)
    observations = [{"observed_at": obs_ts, "temp_f": 72.0, "humidity": 65.0}]

    session_1 = AsyncMock()
    session_1.execute.return_value = _scalar_result(None)

    session_2 = AsyncMock()
    session_2.execute.return_value = _fetchall_result([(obs_ts,)])  # already exists
    session_2.add = MagicMock()
    session_2.commit = AsyncMock()

    mock_factory = MagicMock(
        side_effect=[_make_session_cm(session_1), _make_session_cm(session_2)]
    )

    with patch("app.services.catchup_service.AsyncSessionLocal", mock_factory):
        with patch(
            "app.services.catchup_service.nws_service.fetch_observations_since",
            new=AsyncMock(return_value=observations),
        ):
            await _backfill_area(area, "test")

    session_2.add.assert_not_called()


async def test_backfill_area_large_gap_logs_warning():
    """Gap > 7 days triggers a logger.warning about needing manual approval."""
    area = _make_area()
    old_reading = datetime.now(timezone.utc) - timedelta(days=10)

    session = AsyncMock()
    session.execute.return_value = _scalar_result(old_reading)

    mock_factory = MagicMock(return_value=_make_session_cm(session))

    with patch("app.services.catchup_service.AsyncSessionLocal", mock_factory):
        with patch(
            "app.services.catchup_service.nws_service.fetch_observations_since",
            new=AsyncMock(return_value=[]),
        ):
            with patch("app.services.catchup_service.logger") as mock_logger:
                await _backfill_area(area, "test")

    mock_logger.warning.assert_called_once()
    warning_msg = mock_logger.warning.call_args.args[0]
    assert "7 days" in warning_msg or "Manual approval" in warning_msg


async def test_backfill_area_naive_datetime_gets_utc():
    """A naive last_read_at timestamp is given UTC tzinfo before gap calculation."""
    area = _make_area()
    # Naive timestamp 3 hours ago — gap >= 1 hour so fetch should be called
    naive_ts = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(tzinfo=None)

    session = AsyncMock()
    session.execute.return_value = _scalar_result(naive_ts)

    mock_factory = MagicMock(return_value=_make_session_cm(session))

    with patch("app.services.catchup_service.AsyncSessionLocal", mock_factory):
        with patch(
            "app.services.catchup_service.nws_service.fetch_observations_since",
            new=AsyncMock(return_value=[]),
        ) as mock_fetch:
            await _backfill_area(area, "test")

    # Gap of 3 hours >= 1 hour minimum → fetch was attempted
    mock_fetch.assert_called_once()


# ── _catchup_area ─────────────────────────────────────────────────────────────

async def test_catchup_area_delegates_to_backfill():
    """_catchup_area is a thin wrapper — it calls _backfill_area with the login summary."""
    area = _make_area()

    with patch(
        "app.services.catchup_service._backfill_area",
        new=AsyncMock(),
    ) as mock_backfill:
        await _catchup_area(area)

    mock_backfill.assert_awaited_once_with(area, summary="Catch-up backfill on login.")
