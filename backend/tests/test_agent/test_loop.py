"""
Smoke tests for the anomaly detection agent loop.

Strategy: mock run_anomaly_check at the API layer to verify the readings
endpoint fires it as a BackgroundTask, and mock the Anthropic client at the
service layer to verify the loop handles a simple normal assessment end-to-end
without hitting the live API.
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.loop import run_anomaly_check
from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit
from app.models.field import GrowingArea, GrowingAreaType
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


def _make_log_assessment_response(reading_id) -> MagicMock:
    """Build a mock Claude response that calls log_reading_assessment and ends."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "log_reading_assessment"
    tool_block.id = "tool_abc"
    tool_block.input = {
        "reading_id": str(reading_id),
        "assessment_status": "normal",
        "assessment_summary": "All values within normal range.",
    }
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [tool_block]
    return resp


@pytest.mark.asyncio
async def test_loop_handles_crop_context(db: AsyncSession, owner_user: User):
    """run_anomaly_check extracts crop/phase context when crop_cycle_id is set."""
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Loop Test Field",
        area_type=GrowingAreaType.open_field,
        latitude=41.0,
        longitude=-90.0,
        area_acres=10.0,
    )
    db.add(area)
    crop = Crop(name="corn", greenhouse_compatible=False, typical_cycle_days=167)
    db.add(crop)
    await db.flush()

    cycle = CropCycle(
        growing_area_id=area.id,
        crop_id=crop.id,
        season_year=2026,
        cycle_number=1,
        planted_at=date(2026, 4, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()

    reading = SensorReading(
        growing_area_id=area.id,
        crop_cycle_id=cycle.id,
        temperature=74.0,
        humidity=60.0,
        reading_source=ReadingSource.manual,
        read_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        assessment_status=AssessmentStatus.pending,
    )
    db.add(reading)
    await db.flush()

    mock_resp = _make_log_assessment_response(reading.id)
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    with patch("app.agent.loop._client", mock_client):
        await run_anomaly_check(reading.id, db)

    await db.refresh(reading)
    assert reading.assessment_status == AssessmentStatus.normal


@pytest.mark.asyncio
async def test_loop_handles_exception(db: AsyncSession, owner_user: User, growing_area: GrowingArea):
    """When the Anthropic call raises, the loop marks the reading as error."""
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

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=Exception("API unavailable"))

    with patch("app.agent.loop._client", mock_client):
        await run_anomaly_check(reading.id, db)

    await db.refresh(reading)
    assert reading.assessment_status == AssessmentStatus.error
    assert "Agent loop failed" in reading.assessment_summary
