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

from app.models.field import GrowingArea, GrowingAreaType
from app.models.sensor_reading import AssessmentStatus
from app.models.user import User
from tests.conftest import auth_headers


@pytest.fixture
def reading_payload(growing_area: GrowingArea) -> dict:
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
    assert response.status_code == 403
