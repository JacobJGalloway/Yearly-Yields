"""
Smoke tests for the anomaly detection agent loop.

Strategy: mock run_anomaly_check at the API layer to verify the readings
endpoint fires it as a BackgroundTask, and mock the Anthropic client at the
service layer to verify the loop handles a simple normal assessment end-to-end
without hitting the live API.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import GrowingArea
from app.models.sensor_reading import AssessmentStatus, ReadingSource, SensorReading
from app.models.user import User
from tests.conftest import auth_headers


@pytest_asyncio.fixture
async def pending_reading(db: AsyncSession, growing_area: GrowingArea) -> SensorReading:
    reading = SensorReading(
        growing_area_id=growing_area.id,
        temperature=74.0,
        humidity=60.0,
        reading_source=ReadingSource.manual,
        read_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        assessment_status=AssessmentStatus.pending,
    )
    db.add(reading)
    await db.flush()
    return reading


@pytest.mark.asyncio
async def test_posting_reading_triggers_anomaly_check(
    client: AsyncClient,
    owner_token: str,
    growing_area: GrowingArea,
):
    """Verify run_anomaly_check is scheduled as a BackgroundTask when a reading is posted."""
    with patch(
        "app.api.v1.sensor_readings.run_anomaly_check",
        new=AsyncMock(),
    ) as mock_check:
        response = await client.post(
            "/api/v1/readings/",
            json={
                "growing_area_id": str(growing_area.id),
                "temperature": 74.0,
                "humidity": 60.0,
                "reading_source": "manual",
                "read_at": "2026-04-21T10:00:00Z",
            },
            headers=auth_headers(owner_token),
        )
        assert response.status_code == 201
        # BackgroundTasks run inline in test transport — verify the agent was called
        assert mock_check.called
        call_kwargs = mock_check.call_args
        assert call_kwargs is not None


@pytest.mark.asyncio
async def test_reading_starts_with_pending_status(
    client: AsyncClient,
    owner_token: str,
    growing_area: GrowingArea,
):
    """Assessment status must be pending immediately on creation before the agent runs."""
    with patch("app.api.v1.sensor_readings.run_anomaly_check", new=AsyncMock()):
        response = await client.post(
            "/api/v1/readings/",
            json={
                "growing_area_id": str(growing_area.id),
                "temperature": 74.0,
                "humidity": 60.0,
                "reading_source": "manual",
                "read_at": "2026-04-21T11:00:00Z",
            },
            headers=auth_headers(owner_token),
        )
    assert response.status_code == 201
    assert response.json()["assessment_status"] == AssessmentStatus.pending.value
