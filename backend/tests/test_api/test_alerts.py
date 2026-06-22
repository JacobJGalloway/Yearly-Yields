"""
Tests for /api/v1/alerts/ endpoints.

Covers:
  - GET / returns empty list when no alerts exist
  - GET / returns only alerts for the current user's growing areas
  - GET /?active_only=true filters out resolved alerts
  - GET /{id} returns alert by id
  - GET /{id} returns 404 for unknown alert
  - PATCH /{id} manually resolves an active alert
  - PATCH /{id} returns 422 when alert is already resolved
  - PATCH /{id} returns 422 for invalid status (non-resolved target)
  - GET and PATCH return 401 when unauthenticated
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertStatus, AlertType
from app.models.field import GrowingArea, GrowingAreaPlot
from app.models.sensor_reading import AssessmentStatus, ReadingSource, SensorReading
from app.models.user import User
from tests.conftest import auth_headers


@pytest_asyncio.fixture
async def sensor_reading(
    db: AsyncSession, growing_area: GrowingArea, growing_area_plot: GrowingAreaPlot
) -> SensorReading:
    reading = SensorReading(
        growing_area_id=growing_area.id,
        growing_area_plot_id=growing_area_plot.id,
        temperature=102.0,
        humidity=18.0,
        reading_source=ReadingSource.manual,
        read_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        assessment_status=AssessmentStatus.anomalous,
    )
    db.add(reading)
    await db.flush()
    return reading


@pytest_asyncio.fixture
async def active_alert(
    db: AsyncSession, growing_area: GrowingArea, growing_area_plot: GrowingAreaPlot,
    sensor_reading: SensorReading,
) -> Alert:
    alert = Alert(
        growing_area_id=growing_area.id,
        growing_area_plot_id=growing_area_plot.id,
        triggering_reading_id=sensor_reading.id,
        alert_type=AlertType.temperature_high,
        status=AlertStatus.active,
        assessment_summary="Temperature critically high.",
    )
    db.add(alert)
    await db.flush()
    return alert


@pytest_asyncio.fixture
async def resolved_alert(
    db: AsyncSession, growing_area: GrowingArea, growing_area_plot: GrowingAreaPlot,
    sensor_reading: SensorReading,
) -> Alert:
    alert = Alert(
        growing_area_id=growing_area.id,
        growing_area_plot_id=growing_area_plot.id,
        triggering_reading_id=sensor_reading.id,
        alert_type=AlertType.humidity_low,
        status=AlertStatus.resolved,
        assessment_summary="Humidity recovered.",
        resolved_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    await db.flush()
    return alert


# ── List alerts ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_alerts_empty(client: AsyncClient, owner_token: str):
    response = await client.get("/api/v1/alerts/", headers=auth_headers(owner_token))
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_alerts_returns_own(
    client: AsyncClient, owner_token: str, active_alert: Alert
):
    response = await client.get("/api/v1/alerts/", headers=auth_headers(owner_token))
    assert response.status_code == 200
    ids = [a["id"] for a in response.json()]
    assert str(active_alert.id) in ids


@pytest.mark.asyncio
async def test_list_alerts_active_only_excludes_resolved(
    client: AsyncClient,
    owner_token: str,
    active_alert: Alert,
    resolved_alert: Alert,
):
    response = await client.get(
        "/api/v1/alerts/?active_only=true",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    ids = [a["id"] for a in response.json()]
    assert str(active_alert.id) in ids
    assert str(resolved_alert.id) not in ids


@pytest.mark.asyncio
async def test_list_alerts_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/alerts/")
    assert response.status_code == 401


# ── Get by ID ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_alert_by_id(
    client: AsyncClient, owner_token: str, active_alert: Alert
):
    response = await client.get(
        f"/api/v1/alerts/{active_alert.id}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(active_alert.id)
    assert response.json()["status"] == "active"


@pytest.mark.asyncio
async def test_get_alert_not_found(client: AsyncClient, owner_token: str):
    response = await client.get(
        f"/api/v1/alerts/{uuid.uuid4()}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 404


# ── Manual resolution ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_manual_resolve_active_alert(
    client: AsyncClient, owner_token: str, active_alert: Alert
):
    response = await client.patch(
        f"/api/v1/alerts/{active_alert.id}",
        json={"status": "resolved"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["resolved_at"] is not None


@pytest.mark.asyncio
async def test_resolve_already_resolved_returns_422(
    client: AsyncClient, owner_token: str, resolved_alert: Alert
):
    response = await client.patch(
        f"/api/v1/alerts/{resolved_alert.id}",
        json={"status": "resolved"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422
    assert "already resolved" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_resolve_to_invalid_status_returns_422(
    client: AsyncClient, owner_token: str, active_alert: Alert
):
    response = await client.patch(
        f"/api/v1/alerts/{active_alert.id}",
        json={"status": "active"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_alert_not_found(client: AsyncClient, owner_token: str):
    response = await client.patch(
        f"/api/v1/alerts/{uuid.uuid4()}",
        json={"status": "resolved"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_alert_unauthenticated(client: AsyncClient, active_alert: Alert):
    response = await client.patch(
        f"/api/v1/alerts/{active_alert.id}",
        json={"status": "resolved"},
    )
    assert response.status_code == 401
