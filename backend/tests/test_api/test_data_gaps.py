"""
Tests for GET /api/v1/data-gaps/ and POST /api/v1/data-gaps/{area_id}/acknowledge.

Covers:
  - No eligible areas → empty list
  - Greenhouse excluded (open_field filter)
  - Area without NWS station excluded
  - Area with no readings → gap returned
  - Area with recent reading (within threshold) → no gap
  - Area with stale reading (past threshold) → gap returned with correct gap_days
  - Area with gap acknowledged within threshold → skipped
  - Acknowledge: area found → 204
  - Acknowledge: area not found → 404
  - Acknowledge: other user's area → 404
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import GrowingArea, GrowingAreaPlot, GrowingAreaType, PlotType
from app.models.sensor_reading import AssessmentStatus, ReadingSource, SensorReading
from app.models.user import User

pytestmark = pytest.mark.asyncio

GAP_DAYS = 7  # matches settings.GAP_THRESHOLD_DAYS default


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def open_field(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Gap Test Field",
        area_type=GrowingAreaType.open_field,
        latitude=40.1,
        longitude=-90.2,
        area_acres=20.0,
        nws_station_id="KORD",
        is_active=True,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def greenhouse(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="GH1",
        area_type=GrowingAreaType.dwc_greenhouse,
        latitude=36.2,
        longitude=-83.3,
        area_sqft=5000.0,
        nws_station_id="KMOR",
        is_active=True,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def open_field_plot(db: AsyncSession, open_field: GrowingArea) -> GrowingAreaPlot:
    p = GrowingAreaPlot(
        growing_area_id=open_field.id,
        owner_id=open_field.owner_id,
        plot_index=0,
        plot_type=PlotType.trial_strip,
        is_active=True,
    )
    db.add(p)
    await db.flush()
    return p


def _reading(area_id: uuid.UUID, read_at: datetime, plot_id: uuid.UUID = None) -> SensorReading:
    return SensorReading(
        growing_area_id=area_id,
        growing_area_plot_id=plot_id,
        temperature=72.0,
        humidity=55.0,
        reading_source=ReadingSource.nws,
        read_at=read_at,
        received_at=read_at,
        assessment_status=AssessmentStatus.normal,
    )


# ── list endpoint ─────────────────────────────────────────────────────────────

async def test_list_data_gaps_empty_when_no_areas(
    client: AsyncClient, owner_user: User, owner_token: str
):
    response = await client.get("/api/v1/data-gaps/", headers=_auth(owner_token))
    assert response.status_code == 200
    assert response.json() == []


async def test_list_data_gaps_excludes_greenhouses(
    client: AsyncClient, greenhouse: GrowingArea, owner_token: str
):
    """Greenhouse areas are not monitored for NWS data gaps."""
    response = await client.get("/api/v1/data-gaps/", headers=_auth(owner_token))
    assert response.status_code == 200
    assert response.json() == []


async def test_list_data_gaps_excludes_area_without_nws_station(
    client: AsyncClient, db: AsyncSession, owner_user: User, owner_token: str
):
    area = GrowingArea(
        owner_id=owner_user.id,
        name="No Station Field",
        area_type=GrowingAreaType.open_field,
        latitude=40.1,
        longitude=-90.2,
        area_acres=10.0,
        nws_station_id=None,
        is_active=True,
    )
    db.add(area)
    await db.flush()

    response = await client.get("/api/v1/data-gaps/", headers=_auth(owner_token))
    assert response.status_code == 200
    assert response.json() == []


async def test_list_data_gaps_returns_area_with_no_readings(
    client: AsyncClient, open_field: GrowingArea, owner_token: str
):
    """Area with NWS station but zero readings → appears in gap list."""
    response = await client.get("/api/v1/data-gaps/", headers=_auth(owner_token))
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["area_id"] == str(open_field.id)
    assert data[0]["last_reading_at"] is None
    assert data[0]["gap_days"] == GAP_DAYS


async def test_list_data_gaps_no_gap_for_recent_reading(
    client: AsyncClient, db: AsyncSession, open_field: GrowingArea,
    open_field_plot: GrowingAreaPlot, owner_token: str
):
    """Area with a reading within the threshold does not appear."""
    recent = _reading(open_field.id, datetime.now(timezone.utc) - timedelta(days=1), open_field_plot.id)
    db.add(recent)
    await db.flush()

    response = await client.get("/api/v1/data-gaps/", headers=_auth(owner_token))
    assert response.status_code == 200
    assert response.json() == []


async def test_list_data_gaps_stale_reading_produces_gap(
    client: AsyncClient, db: AsyncSession, open_field: GrowingArea,
    open_field_plot: GrowingAreaPlot, owner_token: str
):
    """Last reading older than GAP_THRESHOLD_DAYS → gap returned with correct gap_days."""
    stale_dt = datetime.now(timezone.utc) - timedelta(days=10)
    db.add(_reading(open_field.id, stale_dt, open_field_plot.id))
    await db.flush()

    response = await client.get("/api/v1/data-gaps/", headers=_auth(owner_token))
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["gap_days"] == 10


async def test_list_data_gaps_skips_acknowledged_within_threshold(
    client: AsyncClient, db: AsyncSession, owner_user: User, owner_token: str
):
    """Area acknowledged within the last GAP_THRESHOLD_DAYS is excluded."""
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Ack Field",
        area_type=GrowingAreaType.open_field,
        latitude=40.1,
        longitude=-90.2,
        area_acres=10.0,
        nws_station_id="KPIA",
        is_active=True,
        gap_acknowledged_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.add(area)
    await db.flush()

    response = await client.get("/api/v1/data-gaps/", headers=_auth(owner_token))
    assert response.status_code == 200
    assert response.json() == []


# ── acknowledge endpoint ──────────────────────────────────────────────────────

async def test_acknowledge_gap_returns_204(
    client: AsyncClient, db: AsyncSession, open_field: GrowingArea, owner_token: str
):
    response = await client.post(
        f"/api/v1/data-gaps/{open_field.id}/acknowledge",
        headers=_auth(owner_token),
    )
    assert response.status_code == 204

    await db.refresh(open_field)
    assert open_field.gap_acknowledged_at is not None


async def test_acknowledge_gap_not_found_returns_404(
    client: AsyncClient, owner_token: str
):
    response = await client.post(
        f"/api/v1/data-gaps/{uuid.uuid4()}/acknowledge",
        headers=_auth(owner_token),
    )
    assert response.status_code == 404


async def test_acknowledge_gap_other_users_area_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    open_field: GrowingArea,
    farmer_user: User,
    farmer_token: str,
):
    """Farmer cannot acknowledge another owner's area."""
    response = await client.post(
        f"/api/v1/data-gaps/{open_field.id}/acknowledge",
        headers=_auth(farmer_token),
    )
    assert response.status_code == 404
