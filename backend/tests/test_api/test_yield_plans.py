"""
Tests for /api/v1/yield-plans/ endpoints.

Covers:
  - POST creates a yield plan via mocked agent (success)
  - POST returns 404 for unknown crop cycle
  - POST returns 422 for non-active cycle
  - POST returns 422 for cycle with no crop assigned
  - hired_hand cannot create a yield plan
  - Unauthenticated returns 401
  - GET / returns only owner's plans
  - GET /{plan_id} returns 404 for unknown plan
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit
from app.models.field import GrowingArea, GrowingAreaPlot, GrowingAreaType, PlotType
from app.models.user import User
from app.models.yield_plan import ConfidenceLevel, YieldPlan
from tests.conftest import auth_headers


@pytest_asyncio.fixture
async def growing_area(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Test Field",
        area_type=GrowingAreaType.open_field,
        latitude=41.8781,
        longitude=-93.0977,
        area_acres=40.0,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def plot(db: AsyncSession, growing_area: GrowingArea) -> GrowingAreaPlot:
    p = GrowingAreaPlot(
        growing_area_id=growing_area.id,
        owner_id=growing_area.owner_id,
        plot_index=0,
        plot_type=PlotType.trial_strip,
        is_active=True,
    )
    db.add(p)
    await db.flush()
    return p


@pytest_asyncio.fixture
async def crop(db: AsyncSession) -> Crop:
    c = Crop(
        name="corn",
        greenhouse_compatible=False,
        typical_cycle_days=120,
    )
    db.add(c)
    await db.flush()
    return c


@pytest_asyncio.fixture
async def active_cycle(db: AsyncSession, growing_area: GrowingArea, plot: GrowingAreaPlot, crop: Crop) -> CropCycle:
    cycle = CropCycle(
        growing_area_id=growing_area.id,
        growing_area_plot_id=plot.id,
        crop_id=crop.id,
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
async def harvested_cycle(db: AsyncSession, growing_area: GrowingArea, plot: GrowingAreaPlot, crop: Crop) -> CropCycle:
    cycle = CropCycle(
        growing_area_id=growing_area.id,
        growing_area_plot_id=plot.id,
        crop_id=crop.id,
        season_year=2025,
        cycle_number=1,
        planted_at=date(2025, 4, 1),
        harvested_at=date(2025, 8, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.harvested,
    )
    db.add(cycle)
    await db.flush()
    return cycle


async def make_mock_plan(cycle: CropCycle, db: AsyncSession) -> YieldPlan:
    plan = YieldPlan(
        growing_area_id=cycle.growing_area_id,
        crop_cycle_id=cycle.id,
        recommended_plant_quantity=28000.0,
        target_yield=7000.0,
        confidence_level=ConfidenceLevel.medium,
        reasoning="Based on historical data, recommend 28,000 seeds.",
    )
    db.add(plan)
    await db.flush()
    return plan


@pytest.mark.asyncio
async def test_create_yield_plan_success(
    client: AsyncClient,
    owner_token: str,
    active_cycle: CropCycle,
    db: AsyncSession,
):
    mock_plan = await make_mock_plan(active_cycle, db)
    with patch(
        "app.api.v1.yield_plans.generate_yield_plan",
        new=AsyncMock(return_value=mock_plan),
    ):
        response = await client.post(
            "/api/v1/yield-plans/",
            json={"crop_cycle_id": str(active_cycle.id), "target_yield": 7000.0},
            headers=auth_headers(owner_token),
        )
    assert response.status_code == 201
    data = response.json()
    assert data["recommended_plant_quantity"] == 28000.0
    assert data["confidence_level"] == "medium"
    assert data["crop_cycle_id"] == str(active_cycle.id)


@pytest.mark.asyncio
async def test_create_yield_plan_cycle_not_found(
    client: AsyncClient,
    owner_token: str,
):
    response = await client.post(
        "/api/v1/yield-plans/",
        json={"crop_cycle_id": str(uuid.uuid4()), "target_yield": 5000.0},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_yield_plan_non_active_cycle(
    client: AsyncClient,
    owner_token: str,
    harvested_cycle: CropCycle,
):
    response = await client.post(
        "/api/v1/yield-plans/",
        json={"crop_cycle_id": str(harvested_cycle.id), "target_yield": 5000.0},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_yield_plan_no_crop_assigned(
    client: AsyncClient,
    owner_token: str,
    db: AsyncSession,
    growing_area: GrowingArea,
    plot: GrowingAreaPlot,
):
    fallow = CropCycle(
        growing_area_id=growing_area.id,
        growing_area_plot_id=plot.id,
        crop_id=None,
        season_year=2026,
        cycle_number=2,
        planted_at=date(2026, 5, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.fallow,
    )
    db.add(fallow)
    await db.flush()

    response = await client.post(
        "/api/v1/yield-plans/",
        json={"crop_cycle_id": str(fallow.id), "target_yield": 5000.0},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_hired_hand_cannot_create_yield_plan(
    client: AsyncClient,
    hired_hand_token: str,
    active_cycle: CropCycle,
):
    response = await client.post(
        "/api/v1/yield-plans/",
        json={"crop_cycle_id": str(active_cycle.id), "target_yield": 5000.0},
        headers=auth_headers(hired_hand_token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_yield_plan_unauthenticated(
    client: AsyncClient,
    active_cycle: CropCycle,
):
    response = await client.post(
        "/api/v1/yield-plans/",
        json={"crop_cycle_id": str(active_cycle.id), "target_yield": 5000.0},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_yield_plans_returns_only_own(
    client: AsyncClient,
    owner_token: str,
    farmer_token: str,
    active_cycle: CropCycle,
    db: AsyncSession,
):
    mock_plan = await make_mock_plan(active_cycle, db)
    with patch(
        "app.api.v1.yield_plans.generate_yield_plan",
        new=AsyncMock(return_value=mock_plan),
    ):
        await client.post(
            "/api/v1/yield-plans/",
            json={"crop_cycle_id": str(active_cycle.id), "target_yield": 7000.0},
            headers=auth_headers(owner_token),
        )

    response = await client.get("/api/v1/yield-plans/", headers=auth_headers(farmer_token))
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_yield_plan_not_found(client: AsyncClient, owner_token: str):
    response = await client.get(
        f"/api/v1/yield-plans/{uuid.uuid4()}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_yield_plan_success(
    client: AsyncClient,
    owner_token: str,
    active_cycle: CropCycle,
    db: AsyncSession,
):
    plan = await make_mock_plan(active_cycle, db)

    response = await client.get(
        f"/api/v1/yield-plans/{plan.id}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(plan.id)


@pytest.mark.asyncio
async def test_list_yield_plans_filtered_by_crop_cycle_id(
    client: AsyncClient,
    owner_token: str,
    active_cycle: CropCycle,
    db: AsyncSession,
    growing_area: GrowingArea,
    plot: GrowingAreaPlot,
    crop: Crop,
):
    plan = await make_mock_plan(active_cycle, db)

    other_cycle = CropCycle(
        growing_area_id=growing_area.id,
        growing_area_plot_id=plot.id,
        crop_id=crop.id,
        season_year=2026,
        cycle_number=3,
        planted_at=date(2026, 5, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.active,
    )
    db.add(other_cycle)
    await db.flush()

    response = await client.get(
        f"/api/v1/yield-plans/?crop_cycle_id={active_cycle.id}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(plan.id)


@pytest.mark.asyncio
async def test_create_yield_plan_agent_returns_none(
    client: AsyncClient,
    owner_token: str,
    active_cycle: CropCycle,
):
    """When the agent loop returns None the endpoint responds 500."""
    with patch(
        "app.api.v1.yield_plans.generate_yield_plan",
        new=AsyncMock(return_value=None),
    ):
        response = await client.post(
            "/api/v1/yield-plans/",
            json={"crop_cycle_id": str(active_cycle.id), "target_yield": 7000.0},
            headers=auth_headers(owner_token),
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_create_yield_plan_active_cycle_no_crop(
    client: AsyncClient,
    owner_token: str,
    db: AsyncSession,
    growing_area: GrowingArea,
    plot: GrowingAreaPlot,
):
    """Active cycle with no crop_id assigned returns 422."""
    no_crop_cycle = CropCycle(
        growing_area_id=growing_area.id,
        growing_area_plot_id=plot.id,
        crop_id=None,
        season_year=2026,
        cycle_number=5,
        planted_at=date(2026, 5, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.active,
    )
    db.add(no_crop_cycle)
    await db.flush()

    response = await client.post(
        "/api/v1/yield-plans/",
        json={"crop_cycle_id": str(no_crop_cycle.id), "target_yield": 5000.0},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422
