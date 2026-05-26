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


# ── List / Get / Create tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_crops_returns_computed_fields(
    client: AsyncClient, owner_token: str, corn: Crop
):
    """GET /api/v1/crops/ exercises CropRead.seeding_days / growing_days / sub_phases."""
    response = await client.get("/api/v1/crops/", headers=auth_headers(owner_token))
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    crop = next((c for c in data if c["name"] == "corn"), None)
    assert crop is not None
    assert crop["seeding_days"] == 10
    assert crop["growing_days"] == 132
    assert isinstance(crop["sub_phases"], list)
    assert len(crop["sub_phases"]) > 0


@pytest.mark.asyncio
async def test_list_crop_cycles_returns_cycles(
    client: AsyncClient, owner_token: str, active_corn_cycle: CropCycle
):
    response = await client.get("/api/v1/crops/cycles", headers=auth_headers(owner_token))
    assert response.status_code == 200
    ids = [c["id"] for c in response.json()]
    assert str(active_corn_cycle.id) in ids


@pytest.mark.asyncio
async def test_list_crop_cycles_filter_by_growing_area(
    client: AsyncClient, owner_token: str, active_corn_cycle: CropCycle, open_field: GrowingArea
):
    response = await client.get(
        f"/api/v1/crops/cycles?growing_area_id={open_field.id}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert all(c["growing_area_id"] == str(open_field.id) for c in response.json())


@pytest.mark.asyncio
async def test_list_crop_cycles_filter_by_status(
    client: AsyncClient, owner_token: str, active_corn_cycle: CropCycle, fallow_cycle: CropCycle
):
    response = await client.get(
        "/api/v1/crops/cycles?status=fallow",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert all(c["status"] == "fallow" for c in response.json())
    assert str(fallow_cycle.id) in [c["id"] for c in response.json()]


@pytest.mark.asyncio
async def test_list_crop_cycles_filter_by_season_year(
    client: AsyncClient, owner_token: str, active_corn_cycle: CropCycle
):
    response = await client.get(
        "/api/v1/crops/cycles?season_year=2026",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert all(c["season_year"] == 2026 for c in response.json())


@pytest.mark.asyncio
async def test_get_crop_cycle_returns_crop_name(
    client: AsyncClient, owner_token: str, active_corn_cycle: CropCycle
):
    response = await client.get(
        f"/api/v1/crops/cycles/{active_corn_cycle.id}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(active_corn_cycle.id)
    assert data["crop_name"] == "corn"


@pytest.mark.asyncio
async def test_get_crop_cycle_not_found(client: AsyncClient, owner_token: str):
    import uuid
    response = await client.get(
        f"/api/v1/crops/cycles/{uuid.uuid4()}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_crop_cycle_success(
    client: AsyncClient, owner_token: str, open_field: GrowingArea, corn: Crop
):
    response = await client.post(
        "/api/v1/crops/cycles",
        headers=auth_headers(owner_token),
        json={
            "growing_area_id": str(open_field.id),
            "crop_id": str(corn.id),
            "season_year": 2026,
            "cycle_number": 99,
            "planted_at": "2026-04-01",
            "yield_unit": "bushels",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["crop_name"] == "corn"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_create_cycle_greenhouse_incompatible_crop_rejected(
    client: AsyncClient, owner_token: str, greenhouse: GrowingArea, corn: Crop
):
    response = await client.post(
        "/api/v1/crops/cycles",
        headers=auth_headers(owner_token),
        json={
            "growing_area_id": str(greenhouse.id),
            "crop_id": str(corn.id),
            "season_year": 2026,
            "cycle_number": 99,
            "planted_at": "2026-04-01",
            "yield_unit": "bushels",
        },
    )
    assert response.status_code == 422
    assert "greenhouse" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_current_phase_seeding(
    client: AsyncClient, owner_token: str, open_field: GrowingArea, corn: Crop
):
    from datetime import date, timedelta
    # corn seeding = 10 days; 5 days in → seeding
    planted = (date.today() - timedelta(days=5)).isoformat()
    response = await client.post(
        "/api/v1/crops/cycles",
        headers=auth_headers(owner_token),
        json={
            "growing_area_id": str(open_field.id),
            "crop_id": str(corn.id),
            "season_year": 2026,
            "cycle_number": 98,
            "planted_at": planted,
            "yield_unit": "bushels",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["current_phase"] == "seeding"
    assert data["current_sub_phase"] is not None


@pytest.mark.asyncio
async def test_current_phase_harvest(
    client: AsyncClient, owner_token: str, open_field: GrowingArea, corn: Crop
):
    from datetime import date, timedelta
    # corn harvest threshold = day 142; 150 days in → harvest
    planted = (date.today() - timedelta(days=150)).isoformat()
    response = await client.post(
        "/api/v1/crops/cycles",
        headers=auth_headers(owner_token),
        json={
            "growing_area_id": str(open_field.id),
            "crop_id": str(corn.id),
            "season_year": 2025,
            "cycle_number": 1,
            "planted_at": planted,
            "yield_unit": "bushels",
        },
    )
    assert response.status_code == 201
    assert response.json()["current_phase"] == "harvest"


@pytest.mark.asyncio
async def test_current_phase_none_for_fallow(
    client: AsyncClient, owner_token: str, fallow_cycle: CropCycle
):
    response = await client.get(
        f"/api/v1/crops/cycles/{fallow_cycle.id}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_phase"] is None
    assert data["current_sub_phase"] is None


@pytest.mark.asyncio
async def test_create_crop_cycle_area_not_found(
    client: AsyncClient, owner_token: str, corn: Crop
):
    import uuid
    response = await client.post(
        "/api/v1/crops/cycles",
        headers=auth_headers(owner_token),
        json={
            "growing_area_id": str(uuid.uuid4()),
            "crop_id": str(corn.id),
            "season_year": 2026,
            "cycle_number": 50,
            "planted_at": "2026-04-01",
            "yield_unit": "bushels",
        },
    )
    assert response.status_code == 404
    assert "growing area" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_crop_cycle_crop_not_found(
    client: AsyncClient, owner_token: str, open_field: GrowingArea
):
    import uuid
    response = await client.post(
        "/api/v1/crops/cycles",
        headers=auth_headers(owner_token),
        json={
            "growing_area_id": str(open_field.id),
            "crop_id": str(uuid.uuid4()),
            "season_year": 2026,
            "cycle_number": 51,
            "planted_at": "2026-04-01",
            "yield_unit": "bushels",
        },
    )
    assert response.status_code == 404
    assert "crop" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_cycle_fields(
    client: AsyncClient, owner_token: str, active_corn_cycle: CropCycle
):
    from datetime import date
    response = await client.patch(
        f"/api/v1/crops/cycles/{active_corn_cycle.id}",
        headers=auth_headers(owner_token),
        json={
            "target_yield": 6000.0,
            "forecasted_end_date": "2026-10-01",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_yield"] == 6000.0
    assert data["forecasted_end_date"] == "2026-10-01"


@pytest.mark.asyncio
async def test_update_cycle_not_found(client: AsyncClient, owner_token: str):
    import uuid
    response = await client.patch(
        f"/api/v1/crops/cycles/{uuid.uuid4()}",
        headers=auth_headers(owner_token),
        json={"target_yield": 1000.0},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_planned_crop_id(
    client: AsyncClient, owner_token: str, fallow_cycle_no_plan: CropCycle, corn: Crop
):
    """PATCH planned_crop_id on a fallow cycle prepares it for activation."""
    response = await client.patch(
        f"/api/v1/crops/cycles/{fallow_cycle_no_plan.id}",
        headers=auth_headers(owner_token),
        json={"planned_crop_id": str(corn.id)},
    )
    assert response.status_code == 200
    assert response.json()["planned_crop_id"] == str(corn.id)


@pytest.mark.asyncio
async def test_fallow_to_active_greenhouse_incompatible_crop_rejected(
    client: AsyncClient,
    owner_token: str,
    db: AsyncSession,
    greenhouse: GrowingArea,
    corn: Crop,
):
    """Activating a fallow greenhouse cycle with a non-greenhouse-compatible crop is rejected."""
    fallow_gh = CropCycle(
        growing_area_id=greenhouse.id,
        crop_id=None,
        planned_crop_id=corn.id,
        season_year=2026,
        cycle_number=10,
        planted_at=date(2026, 5, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.fallow,
    )
    db.add(fallow_gh)
    await db.flush()

    response = await client.patch(
        f"/api/v1/crops/cycles/{fallow_gh.id}",
        headers=auth_headers(owner_token),
        json={"status": "active"},
    )
    assert response.status_code == 422
    assert "greenhouse" in response.json()["detail"].lower()
