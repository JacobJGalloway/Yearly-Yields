import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import GrowingArea, GrowingAreaPlot, PlotType
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
