"""
Phase alert service — daily check for crop cycles that have entered harvest phase.

Runs once on startup (catch-up for any days the server was down) and then daily
via the phase check loop in main.py. Idempotent: skips cycles that already have
an active harvest_ready alert.

Harvest_ready alerts are auto-resolved in the crop cycle update endpoint when
the cycle transitions to any terminal state (harvested, abandoned, transplanted).
"""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crop_phases import get_phase_days
from app.db.session import AsyncSessionLocal
from app.models.alert import Alert, AlertStatus, AlertType
from app.models.crop import Crop, CropCycle, CropCycleStatus
from app.models.field import GrowingArea

logger = logging.getLogger(__name__)


async def run_phase_check() -> None:
    async with AsyncSessionLocal() as db:
        await _check_all_cycles(db)


async def _check_all_cycles(db: AsyncSession) -> None:
    result = await db.execute(
        select(CropCycle, Crop.name.label("crop_name"), GrowingArea.name.label("area_name"))
        .join(GrowingArea, CropCycle.growing_area_id == GrowingArea.id)
        .join(Crop, CropCycle.crop_id == Crop.id)
        .where(CropCycle.status == CropCycleStatus.active)
    )
    rows = result.all()

    today = date.today()
    alerted = 0

    for row in rows:
        cycle: CropCycle = row.CropCycle
        crop_name: str = row.crop_name
        area_name: str = row.area_name

        days_in = (today - cycle.planted_at).days
        pd = get_phase_days(crop_name, cycle.planted_at, cycle.forecasted_end_date)

        if days_in < pd.seeding_days + pd.growing_days:
            continue

        existing = await db.execute(
            select(Alert).where(
                Alert.crop_cycle_id == cycle.id,
                Alert.alert_type == AlertType.harvest_ready,
                Alert.status == AlertStatus.active,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        days_in_harvest = days_in - (pd.seeding_days + pd.growing_days)
        db.add(Alert(
            growing_area_id=cycle.growing_area_id,
            crop_cycle_id=cycle.id,
            triggering_reading_id=None,
            alert_type=AlertType.harvest_ready,
            status=AlertStatus.active,
            assessment_summary=(
                f"{crop_name} in {area_name} entered harvest phase "
                f"{days_in_harvest} day(s) ago (day {days_in} of cycle)."
            ),
        ))
        alerted += 1

    if alerted:
        await db.commit()

    logger.info(
        "Phase check complete: %d active cycle(s) checked, %d harvest_ready alert(s) created.",
        len(rows),
        alerted,
    )
