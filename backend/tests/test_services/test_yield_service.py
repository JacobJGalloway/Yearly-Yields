"""
Tests for yield_service.generate_yield_plan.

The Anthropic client is mocked so tests run without an API key.
The test DB session is passed directly — yield_service accepts a db parameter.
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit
from app.models.field import GrowingArea, GrowingAreaType
from app.models.user import User
from app.services.yield_service import generate_yield_plan

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def area(db: AsyncSession, owner_user: User) -> GrowingArea:
    a = GrowingArea(
        owner_id=owner_user.id,
        name="Yield Plan Field",
        area_type=GrowingAreaType.open_field,
        latitude=40.1,
        longitude=-90.2,
        area_acres=60.0,
    )
    db.add(a)
    await db.flush()
    return a


@pytest_asyncio.fixture
async def crop(db: AsyncSession) -> Crop:
    c = Crop(name="yield_corn", greenhouse_compatible=False, typical_cycle_days=167)
    db.add(c)
    await db.flush()
    return c


@pytest_asyncio.fixture
async def active_cycle(db: AsyncSession, area: GrowingArea, crop: Crop) -> CropCycle:
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
    return cycle


def _save_plan_response(crop_cycle_id, growing_area_id) -> MagicMock:
    """Build a mock Claude response that calls save_yield_plan."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "save_yield_plan"
    tool_block.id = "tool_yield_1"
    tool_block.input = {
        "crop_cycle_id": str(crop_cycle_id),
        "growing_area_id": str(growing_area_id),
        "recommended_plant_quantity": 28000.0,
        "target_yield": 7000.0,
        "confidence_level": "medium",
        "reasoning": "Based on historical data, recommend 28,000 seeds.",
    }
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [tool_block]
    return resp


def _sensor_history_response(growing_area_id) -> MagicMock:
    """Build a mock Claude response that calls get_sensor_history (non-terminal)."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "get_sensor_history"
    tool_block.id = "tool_hist_1"
    tool_block.input = {"growing_area_id": str(growing_area_id)}
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [tool_block]
    return resp


# ── generate_yield_plan ───────────────────────────────────────────────────────

async def test_generate_yield_plan_cycle_not_found(db: AsyncSession):
    result = await generate_yield_plan(uuid.uuid4(), 7000.0, db)
    assert result is None


async def test_generate_yield_plan_success(
    db: AsyncSession, active_cycle: CropCycle, area: GrowingArea
):
    resp = _save_plan_response(active_cycle.id, area.id)
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=resp)

    with patch("app.services.yield_service._client", mock_client):
        result = await generate_yield_plan(active_cycle.id, 7000.0, db)

    assert result is not None
    assert result.recommended_plant_quantity == 28000.0
    assert result.target_yield == 7000.0
    assert result.crop_cycle_id == active_cycle.id


async def test_generate_yield_plan_end_turn_returns_none(
    db: AsyncSession, active_cycle: CropCycle
):
    """If Claude returns end_turn without calling save_yield_plan, result is None."""
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = []

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=resp)

    with patch("app.services.yield_service._client", mock_client):
        result = await generate_yield_plan(active_cycle.id, 7000.0, db)

    assert result is None


async def test_generate_yield_plan_multi_turn(
    db: AsyncSession, active_cycle: CropCycle, area: GrowingArea
):
    """Two-turn loop: first call returns a non-terminal tool, second saves the plan."""
    resp_1 = _sensor_history_response(area.id)
    resp_2 = _save_plan_response(active_cycle.id, area.id)

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[resp_1, resp_2])

    with patch("app.services.yield_service._client", mock_client):
        result = await generate_yield_plan(active_cycle.id, 7000.0, db)

    assert result is not None
    assert mock_client.messages.create.call_count == 2


async def test_generate_yield_plan_no_crop_id(
    db: AsyncSession, area: GrowingArea, owner_user: User
):
    """Cycle with no crop assigned still runs — crop name falls back to 'unknown'."""
    fallow = CropCycle(
        growing_area_id=area.id,
        crop_id=None,
        season_year=2026,
        cycle_number=9,
        planted_at=date(2026, 5, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.fallow,
    )
    db.add(fallow)
    await db.flush()

    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = []

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=resp)

    with patch("app.services.yield_service._client", mock_client):
        result = await generate_yield_plan(fallow.id, 5000.0, db)

    # end_turn with no save → None, but the function ran without error
    assert result is None
    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs.get("messages") or call_args.args[0] if call_args.args else []
    # Verify "unknown" was used for crop name in the user message
    user_content = call_args.kwargs.get("messages", [])[0]["content"] if call_args.kwargs.get("messages") else ""
    assert "unknown" in user_content
