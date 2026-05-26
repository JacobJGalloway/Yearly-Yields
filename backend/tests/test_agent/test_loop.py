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

import app.agent.loop as loop_module
from app.agent.loop import _call_mcp_tool, _get_all_tools, run_anomaly_check
from app.agent.tools import ANOMALY_WRITE_TOOLS
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
    """run_anomaly_check completes normally when a crop_cycle_id is set."""
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

    with patch("app.agent.loop._get_all_tools", new=AsyncMock(return_value=ANOMALY_WRITE_TOOLS)), \
         patch("app.agent.loop._client", mock_client):
        await run_anomaly_check(reading.id, db)

    await db.refresh(reading)
    assert reading.assessment_status == AssessmentStatus.normal


@pytest.mark.asyncio
async def test_get_all_tools_fetches_from_mcp():
    """_get_all_tools fetches tool schemas from MCP when the cache is empty."""
    original = loop_module._mcp_tool_schemas
    loop_module._mcp_tool_schemas = None

    mock_tool = MagicMock()
    mock_tool.name = "get_cycle_context"
    mock_tool.description = "Gets cycle context"
    mock_tool.inputSchema = {"type": "object", "properties": {}}

    mock_list_result = MagicMock()
    mock_list_result.tools = [mock_tool]

    mock_session = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=mock_list_result)

    try:
        with patch("app.agent.loop.get_mcp_session", return_value=mock_session):
            tools = await _get_all_tools()
        assert any(t["name"] == "get_cycle_context" for t in tools)
        # Second call should use cache — no additional list_tools call
        with patch("app.agent.loop.get_mcp_session", return_value=mock_session):
            tools2 = await _get_all_tools()
        assert mock_session.list_tools.call_count == 1
    finally:
        loop_module._mcp_tool_schemas = original


@pytest.mark.asyncio
async def test_call_mcp_tool_success():
    """_call_mcp_tool returns the text from the MCP result."""
    mock_content = MagicMock()
    mock_content.text = '{"field": "value"}'
    mock_result = MagicMock()
    mock_result.isError = False
    mock_result.content = [mock_content]

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)

    with patch("app.agent.loop.get_mcp_session", return_value=mock_session):
        result = await _call_mcp_tool("get_cycle_context", {"area_id": "abc"})

    assert result == '{"field": "value"}'


@pytest.mark.asyncio
async def test_call_mcp_tool_error_response():
    """_call_mcp_tool wraps MCP error responses as JSON."""
    mock_result = MagicMock()
    mock_result.isError = True
    mock_result.content = []

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)

    with patch("app.agent.loop.get_mcp_session", return_value=mock_session):
        result = await _call_mcp_tool("get_cycle_context", {})

    assert "error" in result


@pytest.mark.asyncio
async def test_loop_dispatches_mcp_tool(
    db: AsyncSession, owner_user: User, growing_area: GrowingArea
):
    """Loop routes MCP tool names to _call_mcp_tool instead of dispatch_tool."""
    reading = SensorReading(
        growing_area_id=growing_area.id,
        temperature=72.0,
        humidity=55.0,
        reading_source=ReadingSource.manual,
        read_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        assessment_status=AssessmentStatus.pending,
    )
    db.add(reading)
    await db.flush()

    mcp_block = MagicMock()
    mcp_block.type = "tool_use"
    mcp_block.name = "get_cycle_context"
    mcp_block.id = "tool_mcp"
    mcp_block.input = {}

    terminal_block = MagicMock()
    terminal_block.type = "tool_use"
    terminal_block.name = "log_reading_assessment"
    terminal_block.id = "tool_term"
    terminal_block.input = {
        "reading_id": str(reading.id),
        "assessment_status": "normal",
        "assessment_summary": "OK.",
    }

    resp_1 = MagicMock()
    resp_1.stop_reason = "tool_use"
    resp_1.content = [mcp_block]

    resp_2 = MagicMock()
    resp_2.stop_reason = "tool_use"
    resp_2.content = [terminal_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[resp_1, resp_2])

    mock_mcp_result = MagicMock()
    mock_mcp_result.isError = False
    mock_mcp_result.content = [MagicMock()]
    mock_mcp_result.content[0].text = '{"cycle": null}'

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_mcp_result)

    with patch("app.agent.loop._get_all_tools", new=AsyncMock(return_value=ANOMALY_WRITE_TOOLS)), \
         patch("app.agent.loop._client", mock_client), \
         patch("app.agent.loop.get_mcp_session", return_value=mock_session):
        await run_anomaly_check(reading.id, db)

    mock_session.call_tool.assert_called_once()
    await db.refresh(reading)
    assert reading.assessment_status == AssessmentStatus.normal


@pytest.mark.asyncio
async def test_loop_reading_not_found(db: AsyncSession):
    """run_anomaly_check returns early without error when the reading ID is unknown."""
    import uuid
    await run_anomaly_check(uuid.uuid4(), db)  # should not raise


@pytest.mark.asyncio
async def test_loop_end_turn_marks_reading_processing(
    db: AsyncSession, owner_user: User, growing_area: GrowingArea
):
    """Claude returning end_turn (no tool call) leaves the loop without crashing."""
    reading = SensorReading(
        growing_area_id=growing_area.id,
        temperature=72.0,
        humidity=55.0,
        reading_source=ReadingSource.manual,
        read_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        assessment_status=AssessmentStatus.pending,
    )
    db.add(reading)
    await db.flush()

    end_turn_resp = MagicMock()
    end_turn_resp.stop_reason = "end_turn"
    end_turn_resp.content = []

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=end_turn_resp)

    with patch("app.agent.loop._get_all_tools", new=AsyncMock(return_value=ANOMALY_WRITE_TOOLS)), \
         patch("app.agent.loop._client", mock_client):
        await run_anomaly_check(reading.id, db)

    await db.refresh(reading)
    assert reading.assessment_status == AssessmentStatus.processing


@pytest.mark.asyncio
async def test_loop_skips_non_tool_use_blocks(
    db: AsyncSession, owner_user: User, growing_area: GrowingArea
):
    """Text blocks in a Claude response are ignored; loop still terminates on log_reading_assessment."""
    reading = SensorReading(
        growing_area_id=growing_area.id,
        temperature=72.0,
        humidity=55.0,
        reading_source=ReadingSource.manual,
        read_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        assessment_status=AssessmentStatus.pending,
    )
    db.add(reading)
    await db.flush()

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Thinking..."

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "log_reading_assessment"
    tool_block.id = "tool_xyz"
    tool_block.input = {
        "reading_id": str(reading.id),
        "assessment_status": "normal",
        "assessment_summary": "Normal.",
    }

    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [text_block, tool_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=resp)

    with patch("app.agent.loop._get_all_tools", new=AsyncMock(return_value=ANOMALY_WRITE_TOOLS)), \
         patch("app.agent.loop._client", mock_client):
        await run_anomaly_check(reading.id, db)

    await db.refresh(reading)
    assert reading.assessment_status == AssessmentStatus.normal


@pytest.mark.asyncio
async def test_loop_appends_intermediate_results_and_continues(
    db: AsyncSession, owner_user: User, growing_area: GrowingArea
):
    """Multi-tool response with no terminal tool appends results and loops for next response."""
    reading = SensorReading(
        growing_area_id=growing_area.id,
        temperature=72.0,
        humidity=55.0,
        reading_source=ReadingSource.manual,
        read_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        assessment_status=AssessmentStatus.pending,
    )
    db.add(reading)
    await db.flush()

    non_terminal_block = MagicMock()
    non_terminal_block.type = "tool_use"
    non_terminal_block.name = "get_similar_readings"
    non_terminal_block.id = "tool_nt"
    non_terminal_block.input = {}

    resp_1 = MagicMock()
    resp_1.stop_reason = "tool_use"
    resp_1.content = [non_terminal_block]

    resp_2 = MagicMock()
    resp_2.stop_reason = "end_turn"
    resp_2.content = []

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[resp_1, resp_2])

    with patch("app.agent.loop._get_all_tools", new=AsyncMock(return_value=ANOMALY_WRITE_TOOLS)), \
         patch("app.agent.loop._client", mock_client), \
         patch("app.agent.loop.dispatch_tool", new=AsyncMock(return_value="{}")):
        await run_anomaly_check(reading.id, db)

    assert mock_client.messages.create.call_count == 2


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

    with patch("app.agent.loop._get_all_tools", new=AsyncMock(return_value=ANOMALY_WRITE_TOOLS)), \
         patch("app.agent.loop._client", mock_client):
        await run_anomaly_check(reading.id, db)

    await db.refresh(reading)
    assert reading.assessment_status == AssessmentStatus.error
    assert "Agent loop failed" in reading.assessment_summary
