"""
Tests for phase_alert_service._check_all_cycles.

Phase detection still runs daily; it now logs instead of creating alerts.
Covers:
  - Does NOT create any alert for a cycle in harvest phase
  - Skips cycle that has not yet reached harvest phase
  - Skips inactive (fallow) cycles entirely
"""

from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit
from app.models.field import GrowingArea, GrowingAreaType
from app.models.user import User
from app.services.phase_alert_service import _check_all_cycles

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def area(db: AsyncSession, owner_user: User) -> GrowingArea:
    a = GrowingArea(
        owner_id=owner_user.id,
        name="Phase Test Field",
        area_type=GrowingAreaType.open_field,
        latitude=41.0,
        longitude=-90.0,
        area_acres=10.0,
    )
    db.add(a)
    await db.flush()
    return a


@pytest_asyncio.fixture
async def corn_crop(db: AsyncSession) -> Crop:
    # corn: seeding=10, growing=132 → harvest threshold at day 142
    crop = Crop(name="corn", greenhouse_compatible=False, typical_cycle_days=167)
    db.add(crop)
    await db.flush()
    return crop


async def test_no_alert_created_for_harvest_phase_cycle(
    db: AsyncSession, area: GrowingArea, corn_crop: Crop
):
    planted = date.today() - timedelta(days=150)
    cycle = CropCycle(
        growing_area_id=area.id,
        crop_id=corn_crop.id,
        season_year=2026,
        cycle_number=1,
        planted_at=planted,
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()

    await _check_all_cycles(db)

    result = await db.execute(select(Alert).where(Alert.crop_cycle_id == cycle.id))
    assert result.scalar_one_or_none() is None


async def test_skips_cycle_not_in_harvest_phase(
    db: AsyncSession, area: GrowingArea, corn_crop: Crop
):
    # 5 days in → seeding phase (threshold is day 142)
    planted = date.today() - timedelta(days=5)
    cycle = CropCycle(
        growing_area_id=area.id,
        crop_id=corn_crop.id,
        season_year=2026,
        cycle_number=2,
        planted_at=planted,
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()

    await _check_all_cycles(db)

    result = await db.execute(select(Alert).where(Alert.crop_cycle_id == cycle.id))
    assert result.scalar_one_or_none() is None


async def test_skips_fallow_cycle(
    db: AsyncSession, area: GrowingArea, corn_crop: Crop
):
    planted = date.today() - timedelta(days=150)
    cycle = CropCycle(
        growing_area_id=area.id,
        crop_id=corn_crop.id,
        season_year=2026,
        cycle_number=3,
        planted_at=planted,
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.fallow,
    )
    db.add(cycle)
    await db.flush()

    await _check_all_cycles(db)

    result = await db.execute(select(Alert).where(Alert.crop_cycle_id == cycle.id))
    assert result.scalar_one_or_none() is None
