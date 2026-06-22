import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit
from app.models.field import GrowingArea, GrowingAreaPlot, PlotType
from app.services.plot_service import is_harvest_day
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def greenhouse_area(db: AsyncSession, owner_user) -> GrowingArea:
    from app.models.field import GrowingAreaType
    area = GrowingArea(
        owner_id=owner_user.id,
        name="GH Test",
        area_type=GrowingAreaType.dwc_greenhouse,
        latitude=36.2,
        longitude=-83.2,
        area_sqft=5000.0,
        nws_station_id="KMOR",
    )
    db.add(area)
    await db.flush()
    return area


@pytest.fixture
async def plot(db: AsyncSession, greenhouse_area: GrowingArea, owner_user) -> GrowingAreaPlot:
    p = GrowingAreaPlot(
        growing_area_id=greenhouse_area.id,
        owner_id=owner_user.id,
        plot_index=1,
        name="Bay A",
        plot_type=PlotType.dwc_row,
        area_sqft=500.0,
    )
    db.add(p)
    await db.flush()
    return p


async def test_create_plot_success(client: AsyncClient, owner_token: str, greenhouse_area: GrowingArea):
    r = await client.post(
        f"/api/v1/fields/{greenhouse_area.id}/plots/",
        headers=auth_headers(owner_token),
        json={"plot_index": 1, "name": "Row 1", "plot_type": "dwc_row", "area_sqft": 250.0},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Row 1"
    assert data["plot_type"] == "dwc_row"


async def test_create_plot_area_not_found(client: AsyncClient, owner_token: str):
    r = await client.post(
        f"/api/v1/fields/{uuid.uuid4()}/plots/",
        headers=auth_headers(owner_token),
        json={"plot_index": 1, "name": "Row 1", "plot_type": "dwc_row"},
    )
    assert r.status_code == 404


async def test_create_plot_hired_hand_forbidden(
    client: AsyncClient, hired_hand_token: str, greenhouse_area: GrowingArea
):
    r = await client.post(
        f"/api/v1/fields/{greenhouse_area.id}/plots/",
        headers=auth_headers(hired_hand_token),
        json={"name": "Row 1", "plot_type": "dwc_row"},
    )
    assert r.status_code == 403


async def test_list_plots_empty(client: AsyncClient, owner_token: str, greenhouse_area: GrowingArea):
    r = await client.get(
        f"/api/v1/fields/{greenhouse_area.id}/plots/",
        headers=auth_headers(owner_token),
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_list_plots_returns_plots(
    client: AsyncClient, owner_token: str, greenhouse_area: GrowingArea, plot: GrowingAreaPlot
):
    r = await client.get(
        f"/api/v1/fields/{greenhouse_area.id}/plots/",
        headers=auth_headers(owner_token),
    )
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Bay A"


async def test_list_plots_area_not_found(client: AsyncClient, owner_token: str):
    r = await client.get(
        f"/api/v1/fields/{uuid.uuid4()}/plots/",
        headers=auth_headers(owner_token),
    )
    assert r.status_code == 404


async def test_get_plot(
    client: AsyncClient, owner_token: str, greenhouse_area: GrowingArea, plot: GrowingAreaPlot
):
    r = await client.get(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{plot.id}",
        headers=auth_headers(owner_token),
    )
    assert r.status_code == 200
    assert r.json()["id"] == str(plot.id)


async def test_get_plot_not_found(
    client: AsyncClient, owner_token: str, greenhouse_area: GrowingArea
):
    r = await client.get(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{uuid.uuid4()}",
        headers=auth_headers(owner_token),
    )
    assert r.status_code == 404


async def test_update_plot(
    client: AsyncClient, owner_token: str, greenhouse_area: GrowingArea, plot: GrowingAreaPlot
):
    r = await client.patch(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{plot.id}",
        headers=auth_headers(owner_token),
        json={"name": "Bay A Updated", "area_sqft": 600.0},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Bay A Updated"
    assert data["area_sqft"] == 600.0


async def test_update_plot_not_found(
    client: AsyncClient, owner_token: str, greenhouse_area: GrowingArea
):
    r = await client.patch(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{uuid.uuid4()}",
        headers=auth_headers(owner_token),
        json={"name": "Ghost"},
    )
    assert r.status_code == 404


async def test_update_plot_deactivate(
    client: AsyncClient, owner_token: str, greenhouse_area: GrowingArea, plot: GrowingAreaPlot
):
    r = await client.patch(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{plot.id}",
        headers=auth_headers(owner_token),
        json={"is_active": False},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


# ── Stagger / weekday overlap ──────────────────────────────────────────────────

async def test_create_plot_weekday_conflict(
    client: AsyncClient, owner_token: str, greenhouse_area: GrowingArea
):
    await client.post(
        f"/api/v1/fields/{greenhouse_area.id}/plots/",
        headers=auth_headers(owner_token),
        json={"plot_index": 1, "name": "Row 1", "plot_type": "dwc_row", "harvest_weekdays": [1, 2]},
    )
    r = await client.post(
        f"/api/v1/fields/{greenhouse_area.id}/plots/",
        headers=auth_headers(owner_token),
        json={"plot_index": 2, "name": "Row 2", "plot_type": "dwc_row", "harvest_weekdays": [2, 3]},
    )
    assert r.status_code == 422
    assert "conflict" in r.json()["detail"].lower()


async def test_update_plot_weekday_conflict(
    client: AsyncClient, owner_token: str, greenhouse_area: GrowingArea, plot: GrowingAreaPlot
):
    r2 = await client.post(
        f"/api/v1/fields/{greenhouse_area.id}/plots/",
        headers=auth_headers(owner_token),
        json={"plot_index": 2, "name": "Row 2", "plot_type": "dwc_row", "harvest_weekdays": [3, 4]},
    )
    assert r2.status_code == 201

    # Try to give plot (Bay A) a weekday that Row 2 already owns
    r = await client.patch(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{plot.id}",
        headers=auth_headers(owner_token),
        json={"harvest_weekdays": [4, 5]},
    )
    assert r.status_code == 422


# ── is_harvest_day ─────────────────────────────────────────────────────────────

def test_is_harvest_day_matches():
    p = SimpleNamespace(harvest_weekdays=[1, 4])  # Mon + Thu
    monday = date(2026, 6, 22)   # known Monday
    assert is_harvest_day(p, monday) is True


def test_is_harvest_day_no_match():
    p = SimpleNamespace(harvest_weekdays=[1, 4])
    wednesday = date(2026, 6, 24)
    assert is_harvest_day(p, wednesday) is False


def test_is_harvest_day_none_weekdays():
    p = SimpleNamespace(harvest_weekdays=None)
    assert is_harvest_day(p, date.today()) is False


# ── log-pick endpoint ──────────────────────────────────────────────────────────

@pytest.fixture
async def tomato_crop(db: AsyncSession) -> Crop:
    c = Crop(name="tomatoes", greenhouse_compatible=True, typical_cycle_days=141)
    db.add(c)
    await db.flush()
    return c


@pytest.fixture
async def plot_with_active_cycle(
    db: AsyncSession, greenhouse_area: GrowingArea, owner_user, tomato_crop: Crop
) -> GrowingAreaPlot:
    p = GrowingAreaPlot(
        growing_area_id=greenhouse_area.id,
        owner_id=owner_user.id,
        plot_index=3,
        name="Tomato Row",
        plot_type=PlotType.dwc_row,
        harvest_weekdays=[1, 4],
        is_active=True,
    )
    db.add(p)
    await db.flush()

    cycle = CropCycle(
        growing_area_id=greenhouse_area.id,
        growing_area_plot_id=p.id,
        crop_id=tomato_crop.id,
        season_year=2026,
        cycle_number=1,
        planted_at=date(2026, 1, 1),
        yield_unit=YieldUnit.lbs,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()
    return p


async def test_log_pick_success(
    client: AsyncClient, owner_token: str,
    greenhouse_area: GrowingArea, plot_with_active_cycle: GrowingAreaPlot
):
    r = await client.post(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{plot_with_active_cycle.id}/log-pick",
        headers=auth_headers(owner_token),
        json={"pick_date": "2026-06-20"},
    )
    assert r.status_code == 200
    assert r.json()["last_harvest_date"] == "2026-06-20"


async def test_log_pick_too_soon(
    client: AsyncClient, owner_token: str,
    greenhouse_area: GrowingArea, plot_with_active_cycle: GrowingAreaPlot
):
    await client.post(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{plot_with_active_cycle.id}/log-pick",
        headers=auth_headers(owner_token),
        json={"pick_date": "2026-06-20"},
    )
    r = await client.post(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{plot_with_active_cycle.id}/log-pick",
        headers=auth_headers(owner_token),
        json={"pick_date": "2026-06-23"},  # only 3 days later, tomatoes need 6
    )
    assert r.status_code == 422
    assert "days between picks" in r.json()["detail"]


async def test_log_pick_after_interval(
    client: AsyncClient, owner_token: str,
    greenhouse_area: GrowingArea, plot_with_active_cycle: GrowingAreaPlot
):
    await client.post(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{plot_with_active_cycle.id}/log-pick",
        headers=auth_headers(owner_token),
        json={"pick_date": "2026-06-20"},
    )
    r = await client.post(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{plot_with_active_cycle.id}/log-pick",
        headers=auth_headers(owner_token),
        json={"pick_date": "2026-06-26"},  # 6 days later — exactly meets interval
    )
    assert r.status_code == 200
    assert r.json()["last_harvest_date"] == "2026-06-26"


async def test_schedule_endpoint(
    client: AsyncClient, owner_token: str,
    greenhouse_area: GrowingArea, plot_with_active_cycle: GrowingAreaPlot
):
    # plot_with_active_cycle has harvest_weekdays=[1,4]; June 22, 2026 is a Monday
    r = await client.get(
        f"/api/v1/fields/{greenhouse_area.id}/plots/schedule?on_date=2026-06-22",
        headers=auth_headers(owner_token),
    )
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert str(plot_with_active_cycle.id) in ids


async def test_log_pick_no_active_cycle(
    client: AsyncClient, owner_token: str,
    greenhouse_area: GrowingArea, plot: GrowingAreaPlot
):
    r = await client.post(
        f"/api/v1/fields/{greenhouse_area.id}/plots/{plot.id}/log-pick",
        headers=auth_headers(owner_token),
        json={},
    )
    assert r.status_code == 422
