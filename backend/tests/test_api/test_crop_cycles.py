"""
Tests for crop cycle state machine via PATCH /api/v1/crops/cycles/{cycle_id}.

Covers:
  - active → harvested (valid)
  - active → transplanted (valid, greenhouse crop only)
  - active → transplanted rejected for open field crop
  - active → abandoned (valid)
  - fallow → active auto-promotes planned_crop_id → crop_id
  - fallow → active rejected when no planned_crop_id set
  - terminal states: harvested, transplanted, abandoned cannot transition further
  - invalid transition returns 422 with clear message
  - hired_hand cannot update a cycle
"""

from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit
from app.models.field import GrowingArea, GrowingAreaType
from app.models.user import User
from tests.conftest import auth_headers


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def open_field(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="North Field",
        area_type=GrowingAreaType.open_field,
        latitude=41.8781,
        longitude=-93.0977,
        area_acres=40.0,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def greenhouse(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Greenhouse 1",
        area_type=GrowingAreaType.dwc_greenhouse,
        latitude=41.8781,
        longitude=-93.0977,
        area_sqft=1200.0,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def corn(db: AsyncSession) -> Crop:
    crop = Crop(name="corn", greenhouse_compatible=False, typical_cycle_days=120)
    db.add(crop)
    await db.flush()
    return crop


@pytest_asyncio.fixture
async def tomatoes(db: AsyncSession) -> Crop:
    crop = Crop(name="tomatoes", greenhouse_compatible=True, typical_cycle_days=90)
    db.add(crop)
    await db.flush()
    return crop


@pytest_asyncio.fixture
async def active_corn_cycle(db: AsyncSession, open_field: GrowingArea, corn: Crop) -> CropCycle:
    cycle = CropCycle(
        growing_area_id=open_field.id,
        crop_id=corn.id,
        season_year=2026,
        cycle_number=1,
        planted_at=date(2026, 4, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()
    return cycle


@pytest_asyncio.fixture
async def active_tomato_cycle(db: AsyncSession, greenhouse: GrowingArea, tomatoes: Crop) -> CropCycle:
    cycle = CropCycle(
        growing_area_id=greenhouse.id,
        crop_id=tomatoes.id,
        season_year=2026,
        cycle_number=1,
        planted_at=date(2026, 4, 1),
        yield_unit=YieldUnit.lbs,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()
    return cycle


@pytest_asyncio.fixture
async def fallow_cycle(db: AsyncSession, open_field: GrowingArea, corn: Crop) -> CropCycle:
    cycle = CropCycle(
        growing_area_id=open_field.id,
        crop_id=None,
        planned_crop_id=corn.id,
        season_year=2026,
        cycle_number=2,
        planted_at=date(2026, 5, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.fallow,
    )
    db.add(cycle)
    await db.flush()
    return cycle


@pytest_asyncio.fixture
async def fallow_cycle_no_plan(db: AsyncSession, open_field: GrowingArea) -> CropCycle:
    cycle = CropCycle(
        growing_area_id=open_field.id,
        crop_id=None,
        planned_crop_id=None,
        season_year=2026,
        cycle_number=3,
        planted_at=date(2026, 6, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.fallow,
    )
    db.add(cycle)
    await db.flush()
    return cycle


# ── State machine tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_active_to_harvested(
    client: AsyncClient, owner_token: str, active_corn_cycle: CropCycle
):
    response = await client.patch(
        f"/api/v1/crops/cycles/{active_corn_cycle.id}",
        json={"status": "harvested", "actual_yield": 5200.0, "harvested_at": "2026-08-01"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "harvested"


@pytest.mark.asyncio
async def test_active_to_abandoned(
    client: AsyncClient, owner_token: str, active_corn_cycle: CropCycle
):
    response = await client.patch(
        f"/api/v1/crops/cycles/{active_corn_cycle.id}",
        json={"status": "abandoned"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "abandoned"


@pytest.mark.asyncio
async def test_active_to_transplanted_greenhouse_crop(
    client: AsyncClient, owner_token: str, active_tomato_cycle: CropCycle
):
    response = await client.patch(
        f"/api/v1/crops/cycles/{active_tomato_cycle.id}",
        json={"status": "transplanted", "actual_yield": 800.0},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "transplanted"


@pytest.mark.asyncio
async def test_active_to_transplanted_rejected_for_open_field_crop(
    client: AsyncClient, owner_token: str, active_corn_cycle: CropCycle
):
    response = await client.patch(
        f"/api/v1/crops/cycles/{active_corn_cycle.id}",
        json={"status": "transplanted"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422
    assert "greenhouse" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_fallow_to_active_promotes_planned_crop(
    client: AsyncClient, owner_token: str, fallow_cycle: CropCycle, corn: Crop
):
    response = await client.patch(
        f"/api/v1/crops/cycles/{fallow_cycle.id}",
        json={"status": "active"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert data["crop_id"] == str(corn.id)
    assert data["planned_crop_id"] is None


@pytest.mark.asyncio
async def test_fallow_to_active_rejected_without_planned_crop(
    client: AsyncClient, owner_token: str, fallow_cycle_no_plan: CropCycle
):
    response = await client.patch(
        f"/api/v1/crops/cycles/{fallow_cycle_no_plan.id}",
        json={"status": "active"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422
    assert "planned_crop_id" in response.json()["detail"]


@pytest.mark.asyncio
async def test_harvested_is_terminal(
    client: AsyncClient, owner_token: str, active_corn_cycle: CropCycle
):
    await client.patch(
        f"/api/v1/crops/cycles/{active_corn_cycle.id}",
        json={"status": "harvested", "actual_yield": 5000.0},
        headers=auth_headers(owner_token),
    )
    response = await client.patch(
        f"/api/v1/crops/cycles/{active_corn_cycle.id}",
        json={"status": "active"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422
    assert "terminal" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_transplanted_is_terminal(
    client: AsyncClient, owner_token: str, active_tomato_cycle: CropCycle
):
    await client.patch(
        f"/api/v1/crops/cycles/{active_tomato_cycle.id}",
        json={"status": "transplanted", "actual_yield": 500.0},
        headers=auth_headers(owner_token),
    )
    response = await client.patch(
        f"/api/v1/crops/cycles/{active_tomato_cycle.id}",
        json={"status": "active"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422
    assert "terminal" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_abandoned_is_terminal(
    client: AsyncClient, owner_token: str, active_corn_cycle: CropCycle
):
    await client.patch(
        f"/api/v1/crops/cycles/{active_corn_cycle.id}",
        json={"status": "abandoned"},
        headers=auth_headers(owner_token),
    )
    response = await client.patch(
        f"/api/v1/crops/cycles/{active_corn_cycle.id}",
        json={"status": "active"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422
    assert "terminal" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_hired_hand_cannot_update_cycle(
    client: AsyncClient, hired_hand_token: str, active_corn_cycle: CropCycle
):
    response = await client.patch(
        f"/api/v1/crops/cycles/{active_corn_cycle.id}",
        json={"status": "abandoned"},
        headers=auth_headers(hired_hand_token),
    )
    assert response.status_code == 403
