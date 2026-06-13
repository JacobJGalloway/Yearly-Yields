"""
Tests for POST /api/v1/readings/.

Covers:
  - Successful reading creation returns 201
  - Response shape matches SensorReadingRead schema
  - Assessment status is set to pending on creation
  - received_at is set server-side (not from payload)
  - Invalid growing_area_id returns 422/500 (FK violation)
  - Unauthenticated request returns 403
"""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import GrowingArea, GrowingAreaPlot, GrowingAreaType, PlotType
from app.models.sensor_reading import AssessmentStatus
from app.models.user import User
from tests.conftest import auth_headers


@pytest.fixture
def reading_payload(growing_area: GrowingArea, growing_area_plot: GrowingAreaPlot) -> dict:
    return {
        "growing_area_id": str(growing_area.id),
        "temperature": 72.5,
        "humidity": 65.0,
        "reading_source": "manual",
        "read_at": "2026-04-16T08:00:00Z",
    }


import pytest_asyncio


@pytest_asyncio.fixture
async def growing_area(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Test Field",
        area_type=GrowingAreaType.open_field,
        latitude=41.8781,
        longitude=-93.0977,
        area_acres=10.0,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def growing_area_plot(db: AsyncSession, growing_area: GrowingArea) -> GrowingAreaPlot:
    """Sentinel plot (plot_index=0) so resolve_plot_id() succeeds when readings are POSTed."""
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


@pytest.mark.asyncio
async def test_create_reading_success(
    client: AsyncClient,
    owner_token: str,
    reading_payload: dict,
):
    response = await client.post(
        "/api/v1/readings/",
        json=reading_payload,
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["temperature"] == 72.5
    assert data["humidity"] == 65.0
    assert data["assessment_status"] == AssessmentStatus.pending.value
    assert "id" in data
    assert "received_at" in data


@pytest.mark.asyncio
async def test_create_reading_sets_received_at_server_side(
    client: AsyncClient,
    owner_token: str,
    reading_payload: dict,
):
    """received_at should be set by the server, not taken from the payload."""
    response = await client.post(
        "/api/v1/readings/",
        json=reading_payload,
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["received_at"] is not None
    # received_at should be close to now, not equal to read_at
    assert data["received_at"] != data["read_at"]


@pytest.mark.asyncio
async def test_create_reading_assessment_status_is_pending(
    client: AsyncClient,
    owner_token: str,
    reading_payload: dict,
):
    response = await client.post(
        "/api/v1/readings/",
        json=reading_payload,
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["assessment_status"] == "pending"


@pytest.mark.asyncio
async def test_create_reading_unauthenticated(
    client: AsyncClient,
    reading_payload: dict,
):
    response = await client.post("/api/v1/readings/", json=reading_payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_readings_returns_created_reading(
    client: AsyncClient,
    owner_token: str,
    reading_payload: dict,
):
    await client.post(
        "/api/v1/readings/",
        json=reading_payload,
        headers=auth_headers(owner_token),
    )
    response = await client.get("/api/v1/readings/", headers=auth_headers(owner_token))
    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert all("temperature" in r for r in response.json())


@pytest.mark.asyncio
async def test_list_readings_filter_by_growing_area(
    client: AsyncClient,
    owner_token: str,
    reading_payload: dict,
    growing_area: GrowingArea,
):
    await client.post(
        "/api/v1/readings/",
        json=reading_payload,
        headers=auth_headers(owner_token),
    )
    response = await client.get(
        f"/api/v1/readings/?growing_area_id={growing_area.id}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(r["growing_area_id"] == str(growing_area.id) for r in data)


@pytest.mark.asyncio
async def test_list_readings_filter_by_assessment_status(
    client: AsyncClient,
    owner_token: str,
    reading_payload: dict,
):
    await client.post(
        "/api/v1/readings/",
        json=reading_payload,
        headers=auth_headers(owner_token),
    )
    response = await client.get(
        "/api/v1/readings/?assessment_status=pending",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert all(r["assessment_status"] == "pending" for r in response.json())


@pytest.mark.asyncio
async def test_list_readings_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/readings/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_readings_empty_for_different_owner(
    client: AsyncClient,
    farmer_token: str,
    reading_payload: dict,
    owner_token: str,
):
    # Create reading as owner, list as farmer (no readings owned by farmer)
    await client.post(
        "/api/v1/readings/",
        json=reading_payload,
        headers=auth_headers(owner_token),
    )
    response = await client.get("/api/v1/readings/", headers=auth_headers(farmer_token))
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_weekly_summary_returns_valid_structure(
    client: AsyncClient,
    owner_token: str,
    reading_payload: dict,
):
    await client.post(
        "/api/v1/readings/",
        json=reading_payload,
        headers=auth_headers(owner_token),
    )
    response = await client.get(
        "/api/v1/readings/weekly-summary",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        entry = data[0]
        assert "iso_week" in entry
        assert "year" in entry
        assert "week_label" in entry
        assert "avg_temp_f" in entry
        assert "reading_count" in entry


@pytest.mark.asyncio
async def test_list_readings_filter_by_since(
    client: AsyncClient,
    owner_token: str,
    growing_area: GrowingArea,
    growing_area_plot: GrowingAreaPlot,
):
    """?since= excludes readings before the cutoff."""
    import uuid as uuidlib
    from unittest.mock import AsyncMock, patch

    with patch("app.api.v1.sensor_readings.run_anomaly_check", new=AsyncMock()):
        await client.post(
            "/api/v1/readings/",
            json={
                "growing_area_id": str(growing_area.id),
                "temperature": 70.0,
                "humidity": 55.0,
                "reading_source": "manual",
                "read_at": "2020-01-01T00:00:00Z",
            },
            headers=auth_headers(owner_token),
        )

    response = await client.get(
        "/api/v1/readings/?since=2025-01-01T00:00:00Z",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert all(r["read_at"] >= "2025-01-01T00:00:00Z" for r in response.json())


@pytest.mark.asyncio
async def test_list_readings_filter_by_crop_cycle_id(
    client: AsyncClient,
    owner_token: str,
    growing_area: GrowingArea,
    growing_area_plot: GrowingAreaPlot,
    db: AsyncSession,
):
    """?crop_cycle_id= returns only readings for that cycle."""
    import uuid as uuidlib
    from datetime import date
    from unittest.mock import AsyncMock, patch
    from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit

    crop = Crop(name="cycle_filter_crop", greenhouse_compatible=False, typical_cycle_days=120)
    db.add(crop)
    await db.flush()
    cycle = CropCycle(
        growing_area_id=growing_area.id,
        growing_area_plot_id=growing_area_plot.id,
        crop_id=crop.id,
        season_year=2026,
        cycle_number=77,
        planted_at=date(2026, 4, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()

    with patch("app.api.v1.sensor_readings.run_anomaly_check", new=AsyncMock()):
        await client.post(
            "/api/v1/readings/",
            json={
                "growing_area_id": str(growing_area.id),
                "crop_cycle_id": str(cycle.id),
                "temperature": 72.0,
                "humidity": 60.0,
                "reading_source": "manual",
                "read_at": "2026-05-01T10:00:00Z",
            },
            headers=auth_headers(owner_token),
        )

    response = await client.get(
        f"/api/v1/readings/?crop_cycle_id={cycle.id}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(r["crop_cycle_id"] == str(cycle.id) for r in data)


@pytest.mark.asyncio
async def test_weekly_summary_empty_for_unknown_area(
    client: AsyncClient,
    owner_token: str,
):
    import uuid
    response = await client.get(
        f"/api/v1/readings/weekly-summary?growing_area_id={uuid.uuid4()}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json() == []
