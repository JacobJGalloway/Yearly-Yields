"""
Phase check — daily scan for crop cycles that have entered harvest phase.

Runs once on startup and then daily via the phase check loop in main.py.
Logs only. Phase transition notifications are a future feature; this service
is intentionally not the alert system.
"""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crop_phases import get_phase_days
from app.db.session import AsyncSessionLocal
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
    harvest_ready_count = 0

    for row in rows:
        cycle: CropCycle = row.CropCycle
        crop_name: str = row.crop_name
        area_name: str = row.area_name

        days_in = (today - cycle.planted_at).days
        pd = get_phase_days(crop_name, cycle.planted_at, cycle.forecasted_end_date)

        if days_in < pd.seeding_days + pd.growing_days:
            continue

        days_in_harvest = days_in - (pd.seeding_days + pd.growing_days)
        logger.info(
            "Harvest-ready: %s in %s — day %d of cycle (%d day(s) in harvest phase). "
            "No alert raised — harvest readiness is a human judgment call.",
            crop_name, area_name, days_in, days_in_harvest,
        )
        harvest_ready_count += 1

    logger.info(
        "Phase check complete: %d active cycle(s) checked, %d in harvest phase.",
        len(rows),
        harvest_ready_count,
    )
