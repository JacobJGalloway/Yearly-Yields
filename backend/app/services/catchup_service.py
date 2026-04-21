"""
NWS catch-up backfill triggered on user login.

Fills sensor_reading gaps for open-field GrowingAreas since the last ingested
observation. Greenhouse areas are skipped — simulated fIoT readings cannot be
reconstructed for past timestamps.

Catch-up readings are marked `normal` (no agent loop) because anomaly detection
on hours-old historical data produces no actionable alerts.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.field import GrowingArea, GrowingAreaType
from app.models.sensor_reading import AssessmentStatus, ReadingSource, SensorReading
from app.services import nws_service

logger = logging.getLogger(__name__)

_MIN_GAP_HOURS = 1  # don't bother catching up if last reading is within 1 hour


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

    for area in areas:
        try:
            await _catchup_area(area)
        except Exception:
            logger.exception("NWS catch-up failed for area %s (%s)", area.name, area.id)


async def _catchup_area(area: GrowingArea) -> None:
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
        # No readings at all — seed from the NWS 7-day window
        since = now - timedelta(days=7)
    else:
        if last_read_at.tzinfo is None:
            last_read_at = last_read_at.replace(tzinfo=timezone.utc)
        gap_hours = (now - last_read_at).total_seconds() / 3600
        if gap_hours < _MIN_GAP_HOURS:
            return
        since = last_read_at

    observations = await nws_service.fetch_observations_since(area.nws_station_id, since)
    if not observations:
        return

    logger.info(
        "NWS catch-up: inserting %d observations for %s (since %s)",
        len(observations),
        area.name,
        since.isoformat(),
    )

    async with AsyncSessionLocal() as db:
        # Fetch existing read_at values in this window to avoid duplicates
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
                temperature=obs.get("temp_f"),
                humidity=obs.get("humidity"),
                wind_speed=obs.get("wind_speed"),
                wind_direction=obs.get("wind_direction"),
                reading_source=ReadingSource.nws,
                read_at=obs_ts,
                received_at=now,
                assessment_status=AssessmentStatus.normal,
                assessment_summary="Catch-up backfill on login.",
            ))

        await db.commit()
