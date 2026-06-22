"""
NWS catch-up backfill triggered on user login.

Fills sensor_reading gaps for open-field GrowingAreas since the last ingested
observation. Greenhouse areas are skipped — simulated fIoT readings cannot be
reconstructed for past timestamps.

Catch-up readings are marked `normal` (no agent loop) because anomaly detection
on hours-old historical data produces no actionable alerts.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.field import GrowingArea, GrowingAreaPlot, GrowingAreaType
from app.models.sensor_reading import AssessmentStatus, ReadingSource, SensorReading
from app.services import nws_service

logger = logging.getLogger(__name__)

_MIN_GAP_HOURS = 1   # don't bother catching up if last reading is within 1 hour
_MAX_SILENT_GAP_DAYS = 7  # gaps beyond this log a warning; v1.1 modal handles approval


async def run_system_backfill() -> None:
    """
    Called once at server startup. Fills NWS observation gaps for all active
    open-field areas across all owners.

    Gaps ≤ 7 days are filled silently and marked normal (no anomaly check).
    Gaps > 7 days log a warning — only the last 7 days will be recovered.
    The v1.1 gap-notification modal will surface large gaps to the farmer
    for manual approval and CDO historical fill.

    Greenhouse areas are skipped — the fIoT simulation covers current readings
    and historical greenhouse reconstruction is part of the v1.1 gap modal.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GrowingArea).where(
                GrowingArea.is_active.is_(True),
                GrowingArea.area_type == GrowingAreaType.open_field,
                GrowingArea.nws_station_id.isnot(None),
            )
        )
        areas = result.scalars().all()

    results = await asyncio.gather(
        *(_backfill_area(area, summary="Startup backfill — pre-assessed normal.") for area in areas),
        return_exceptions=True,
    )
    for area, exc in zip(areas, results):
        if isinstance(exc, BaseException):
            logger.exception("Startup backfill failed for area %s (%s)", area.name, area.id, exc_info=exc)


async def run_nws_catchup(owner_id: uuid.UUID) -> None:
    """
    Called as a BackgroundTask after a successful login.
    Fetches any NWS observations missed since the last stored reading
    for each active open-field area owned by the user.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GrowingArea).where(
                GrowingArea.owner_id == owner_id,
                GrowingArea.is_active.is_(True),
                GrowingArea.area_type == GrowingAreaType.open_field,
                GrowingArea.nws_station_id.isnot(None),
            )
        )
        areas = result.scalars().all()

    results = await asyncio.gather(
        *(_catchup_area(area) for area in areas),
        return_exceptions=True,
    )
    for area, exc in zip(areas, results):
        if isinstance(exc, BaseException):
            logger.exception("NWS catch-up failed for area %s (%s)", area.name, area.id, exc_info=exc)


async def _backfill_area(area: GrowingArea, summary: str) -> None:
    """Shared backfill logic for a single open-field area."""
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SensorReading.read_at)
            .where(SensorReading.growing_area_id == area.id)
            .order_by(SensorReading.read_at.desc())
            .limit(1)
        )
        last_read_at = result.scalar_one_or_none()

    if last_read_at is None:
        since = now - timedelta(days=7)
    else:
        if last_read_at.tzinfo is None:
            last_read_at = last_read_at.replace(tzinfo=timezone.utc)
        gap_hours = (now - last_read_at).total_seconds() / 3600
        if gap_hours < _MIN_GAP_HOURS:
            return
        gap_days = gap_hours / 24
        if gap_days > _MAX_SILENT_GAP_DAYS:
            logger.warning(
                "Data gap of %.1f days for %s (%s) — only last 7 days recovered. "
                "Manual approval required for older data (v1.1).",
                gap_days, area.name, area.id,
            )
        since = last_read_at

    observations = await nws_service.fetch_observations_since(area.nws_station_id, since)
    if not observations:
        return

    logger.info(
        "NWS backfill: inserting %d observations for %s (since %s)",
        len(observations), area.name, since.isoformat(),
    )

    async with AsyncSessionLocal() as db:
        sentinel_result = await db.execute(
            select(GrowingAreaPlot).where(
                GrowingAreaPlot.growing_area_id == area.id,
                GrowingAreaPlot.plot_index == 0,
            )
        )
        sentinel = sentinel_result.scalar_one_or_none()
        if sentinel is None:
            logger.warning("No sentinel plot (index=0) for area %s (%s) — skipping backfill", area.name, area.id)
            return

        existing_result = await db.execute(
            select(SensorReading.read_at).where(
                SensorReading.growing_area_id == area.id,
                SensorReading.read_at > since,
            )
        )
        existing_timestamps = {row[0] for row in existing_result.fetchall()}

        for obs in observations:
            obs_ts = obs["observed_at"]
            if obs_ts.tzinfo is None:
                obs_ts = obs_ts.replace(tzinfo=timezone.utc)
            if obs_ts in existing_timestamps:
                continue

            db.add(SensorReading(
                growing_area_id=area.id,
                growing_area_plot_id=sentinel.id,
                temperature=obs.get("temp_f"),
                humidity=obs.get("humidity"),
                wind_speed=obs.get("wind_speed"),
                wind_direction=obs.get("wind_direction"),
                reading_source=ReadingSource.nws,
                read_at=obs_ts,
                received_at=now,
                assessment_status=AssessmentStatus.normal,
                assessment_summary=summary,
            ))

        await db.commit()


async def _catchup_area(area: GrowingArea) -> None:
    await _backfill_area(area, summary="Catch-up backfill on login.")
