"""
Tests for tool_handler functions — called directly, bypassing the agent loop.

All handlers here are pure DB operations; no Anthropic API is required
(except handle_get_historical_context, which is deferred to a future test).
"""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_handlers import (
    dispatch_tool,
    dispatch_yield_tool,
    handle_get_historical_context,
    handle_create_alert,
    handle_get_active_alert,
    handle_get_cycle_yield_history,
    handle_get_sensor_history,
    handle_get_weather_context,
    handle_log_reading_assessment,
    handle_save_yield_plan,
    handle_send_alert_email,
    handle_update_alert,
)
from app.models.alert import Alert, AlertStatus, AlertType
from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit
from app.models.field import GrowingArea, GrowingAreaPlot, GrowingAreaType, PlotType
from app.models.sensor_reading import AssessmentStatus, ReadingSource, SensorReading
from app.models.user import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def area(db: AsyncSession, owner_user: User) -> GrowingArea:
    a = GrowingArea(
        owner_id=owner_user.id,
        name="Handler Test Field",
        area_type=GrowingAreaType.open_field,
        latitude=41.0,
        longitude=-90.0,
        area_acres=10.0,
    )
    db.add(a)
    await db.flush()
    return a


@pytest_asyncio.fixture
async def plot(db: AsyncSession, area: GrowingArea) -> GrowingAreaPlot:
    p = GrowingAreaPlot(
        growing_area_id=area.id,
        owner_id=area.owner_id,
        plot_index=0,
        plot_type=PlotType.trial_strip,
        is_active=True,
    )
    db.add(p)
    await db.flush()
    return p


@pytest_asyncio.fixture
async def corn(db: AsyncSession) -> Crop:
    crop = Crop(name="handler_corn", greenhouse_compatible=False, typical_cycle_days=167)
    db.add(crop)
    await db.flush()
    return crop


@pytest_asyncio.fixture
async def reading(db: AsyncSession, area: GrowingArea, plot: GrowingAreaPlot) -> SensorReading:
    r = SensorReading(
        growing_area_id=area.id,
        growing_area_plot_id=plot.id,
        temperature=75.0,
        humidity=60.0,
        reading_source=ReadingSource.manual,
        read_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        assessment_status=AssessmentStatus.pending,
    )
    db.add(r)
    await db.flush()
    return r


@pytest_asyncio.fixture
async def active_cycle(db: AsyncSession, area: GrowingArea, plot: GrowingAreaPlot, corn: Crop) -> CropCycle:
    cycle = CropCycle(
        growing_area_id=area.id,
        growing_area_plot_id=plot.id,
        crop_id=corn.id,
        season_year=2026,
        cycle_number=1,
        planted_at=date(2026, 4, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()
    return cycle


@pytest_asyncio.fixture
async def active_alert(db: AsyncSession, area: GrowingArea, plot: GrowingAreaPlot, reading: SensorReading) -> Alert:
    a = Alert(
        growing_area_id=area.id,
        growing_area_plot_id=plot.id,
        triggering_reading_id=reading.id,
        alert_type=AlertType.temperature_high,
        status=AlertStatus.active,
        assessment_summary="High temperature alert.",
    )
    db.add(a)
    await db.flush()
    return a


# ── Sensor history ────────────────────────────────────────────────────────────

async def test_handle_get_sensor_history_with_data(
    db: AsyncSession, area: GrowingArea, reading: SensorReading
):
    result = await handle_get_sensor_history({"growing_area_id": str(area.id)}, db)
    assert result["status"] == "ok"
    assert len(result["readings"]) == 1
    assert result["readings"][0]["temperature"] == 75.0


async def test_handle_get_sensor_history_no_data(db: AsyncSession, area: GrowingArea):
    result = await handle_get_sensor_history({"growing_area_id": str(area.id)}, db)
    assert result["status"] == "no_data"
    assert result["readings"] == []


async def test_handle_get_sensor_history_scoped_to_plot(
    db: AsyncSession, area: GrowingArea, plot: GrowingAreaPlot, reading: SensorReading
):
    other_plot = GrowingAreaPlot(
        growing_area_id=area.id,
        owner_id=area.owner_id,
        plot_index=1,
        plot_type=PlotType.trial_strip,
        is_active=True,
    )
    db.add(other_plot)
    await db.flush()

    other_reading = SensorReading(
        growing_area_id=area.id,
        growing_area_plot_id=other_plot.id,
        temperature=99.0,
        humidity=20.0,
        reading_source=ReadingSource.manual,
        read_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        assessment_status=AssessmentStatus.pending,
    )
    db.add(other_reading)
    await db.flush()

    result = await handle_get_sensor_history(
        {"growing_area_id": str(area.id), "growing_area_plot_id": str(plot.id)}, db
    )
    assert result["status"] == "ok"
    assert len(result["readings"]) == 1
    assert result["readings"][0]["temperature"] == 75.0


# ── Cycle yield history ───────────────────────────────────────────────────────

async def test_handle_get_cycle_yield_history_no_data(
    db: AsyncSession, area: GrowingArea, corn: Crop
):
    result = await handle_get_cycle_yield_history(
        {"growing_area_id": str(area.id), "crop_id": str(corn.id)}, db
    )
    assert result["status"] == "no_data"
    assert result["cycles"] == []


async def test_handle_get_cycle_yield_history_with_data(
    db: AsyncSession, area: GrowingArea, plot: GrowingAreaPlot, corn: Crop
):
    cycle = CropCycle(
        growing_area_id=area.id,
        growing_area_plot_id=plot.id,
        crop_id=corn.id,
        season_year=2025,
        cycle_number=1,
        planted_at=date(2025, 4, 1),
        harvested_at=date(2025, 8, 1),
        actual_yield=5000.0,
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.harvested,
    )
    db.add(cycle)
    await db.flush()

    result = await handle_get_cycle_yield_history(
        {"growing_area_id": str(area.id), "crop_id": str(corn.id)}, db
    )
    assert result["status"] == "ok"
    assert len(result["cycles"]) == 1
    assert result["cycles"][0]["actual_yield"] == 5000.0


async def test_handle_get_cycle_yield_history_scoped_to_plot(
    db: AsyncSession, area: GrowingArea, plot: GrowingAreaPlot, corn: Crop
):
    other_plot = GrowingAreaPlot(
        growing_area_id=area.id,
        owner_id=area.owner_id,
        plot_index=1,
        plot_type=PlotType.trial_strip,
        is_active=True,
    )
    db.add(other_plot)
    await db.flush()

    cycle_on_plot = CropCycle(
        growing_area_id=area.id,
        growing_area_plot_id=plot.id,
        crop_id=corn.id,
        season_year=2025,
        cycle_number=1,
        planted_at=date(2025, 4, 1),
        harvested_at=date(2025, 8, 1),
        actual_yield=5000.0,
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.harvested,
    )
    cycle_on_other = CropCycle(
        growing_area_id=area.id,
        growing_area_plot_id=other_plot.id,
        crop_id=corn.id,
        season_year=2025,
        cycle_number=2,
        planted_at=date(2025, 4, 1),
        harvested_at=date(2025, 8, 1),
        actual_yield=9999.0,
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.harvested,
    )
    db.add_all([cycle_on_plot, cycle_on_other])
    await db.flush()

    result = await handle_get_cycle_yield_history(
        {"growing_area_id": str(area.id), "crop_id": str(corn.id), "growing_area_plot_id": str(plot.id)},
        db,
    )
    assert result["status"] == "ok"
    assert len(result["cycles"]) == 1
    assert result["cycles"][0]["actual_yield"] == 5000.0


# ── Save yield plan ───────────────────────────────────────────────────────────

async def test_handle_save_yield_plan(
    db: AsyncSession, area: GrowingArea, plot: GrowingAreaPlot, active_cycle: CropCycle
):
    result = await handle_save_yield_plan(
        {
            "crop_cycle_id": str(active_cycle.id),
            "growing_area_id": str(area.id),
            "growing_area_plot_id": str(plot.id),
            "recommended_plant_quantity": 25000.0,
            "target_yield": 6000.0,
            "confidence_level": "high",
            "reasoning": "Based on historical yields.",
        },
        db,
    )
    assert result["status"] == "saved"
    assert "yield_plan_id" in result


async def test_handle_save_yield_plan_derives_plot_from_cycle(
    db: AsyncSession, area: GrowingArea, plot: GrowingAreaPlot, active_cycle: CropCycle
):
    result = await handle_save_yield_plan(
        {
            "crop_cycle_id": str(active_cycle.id),
            "growing_area_id": str(area.id),
            "recommended_plant_quantity": 25000.0,
            "target_yield": 6000.0,
            "confidence_level": "medium",
            "reasoning": "Derived plot from cycle.",
        },
        db,
    )
    assert result["status"] == "saved"
    assert "yield_plan_id" in result


# ── dispatch_yield_tool ───────────────────────────────────────────────────────

async def test_dispatch_yield_tool_unknown(db: AsyncSession):
    result = await dispatch_yield_tool("not_a_real_tool", {}, db)
    assert "error" in result
    assert "Unknown tool" in result["error"]


# ── Weather context ───────────────────────────────────────────────────────────

async def test_handle_get_weather_context_success(db: AsyncSession, area: GrowingArea):
    result = await handle_get_weather_context({"growing_area_id": str(area.id)}, db)
    assert result["status"] == "not_implemented"
    assert result["latitude"] == 41.0
    assert result["longitude"] == -90.0


async def test_handle_get_weather_context_not_found(db: AsyncSession):
    result = await handle_get_weather_context({"growing_area_id": str(uuid.uuid4())}, db)
    assert "error" in result


# ── Get active alert ──────────────────────────────────────────────────────────

async def test_handle_get_active_alert_none(db: AsyncSession, area: GrowingArea):
    result = await handle_get_active_alert({"growing_area_id": str(area.id)}, db)
    assert result["active_alert"] is None


async def test_handle_get_active_alert_found(
    db: AsyncSession, area: GrowingArea, active_alert: Alert
):
    result = await handle_get_active_alert({"growing_area_id": str(area.id)}, db)
    assert result["active_alert"] is not None
    assert result["active_alert"]["alert_type"] == "temperature_high"
    assert result["active_alert"]["id"] == str(active_alert.id)


# ── Create alert ──────────────────────────────────────────────────────────────

async def test_handle_create_alert(
    db: AsyncSession, area: GrowingArea, reading: SensorReading
):
    result = await handle_create_alert(
        {
            "growing_area_id": str(area.id),
            "triggering_reading_id": str(reading.id),
            "alert_type": "humidity_low",
            "assessment_summary": "Humidity critically low.",
        },
        db,
    )
    assert result["status"] == "created"
    assert "alert_id" in result


async def test_handle_create_alert_explicit_plot_id(
    db: AsyncSession, area: GrowingArea, plot: GrowingAreaPlot, reading: SensorReading
):
    result = await handle_create_alert(
        {
            "growing_area_id": str(area.id),
            "growing_area_plot_id": str(plot.id),
            "triggering_reading_id": str(reading.id),
            "alert_type": "temperature_high",
            "assessment_summary": "Temperature spiked on plot.",
        },
        db,
    )
    assert result["status"] == "created"

    from sqlalchemy import select
    from app.models.alert import Alert
    saved = await db.get(Alert, uuid.UUID(result["alert_id"]))
    assert saved.growing_area_plot_id == plot.id


# ── Update alert ──────────────────────────────────────────────────────────────

async def test_handle_update_alert_success(db: AsyncSession, active_alert: Alert):
    result = await handle_update_alert(
        {
            "alert_id": str(active_alert.id),
            "consecutive_normal_count": 2,
            "status": "active",
            "assessment_summary": "Still monitoring.",
        },
        db,
    )
    assert result["status"] == "active"
    assert result["alert_id"] == str(active_alert.id)


async def test_handle_update_alert_resolves(db: AsyncSession, active_alert: Alert):
    result = await handle_update_alert(
        {
            "alert_id": str(active_alert.id),
            "consecutive_normal_count": 3,
            "status": "resolved",
        },
        db,
    )
    assert result["status"] == "resolved"


async def test_handle_update_alert_not_found(db: AsyncSession):
    result = await handle_update_alert(
        {
            "alert_id": str(uuid.uuid4()),
            "consecutive_normal_count": 0,
            "status": "active",
        },
        db,
    )
    assert "error" in result


# ── Send alert email ──────────────────────────────────────────────────────────

async def test_handle_send_alert_email_success(db: AsyncSession, active_alert: Alert):
    with patch("app.agent.tool_handlers.send_alert_email", new=AsyncMock(return_value=None)):
        result = await handle_send_alert_email({"alert_id": str(active_alert.id)}, db)
    assert result["status"] == "sent"
    assert result["alert_id"] == str(active_alert.id)


async def test_handle_send_alert_email_not_found(db: AsyncSession):
    result = await handle_send_alert_email({"alert_id": str(uuid.uuid4())}, db)
    assert "error" in result


async def test_handle_send_alert_email_send_failure(db: AsyncSession, active_alert: Alert):
    with patch("app.agent.tool_handlers.send_alert_email", new=AsyncMock(side_effect=Exception("SMTP error"))):
        result = await handle_send_alert_email({"alert_id": str(active_alert.id)}, db)
    assert result["status"] == "email_failed"
    assert result["alert_id"] == str(active_alert.id)


# ── Log reading assessment ────────────────────────────────────────────────────

async def test_handle_log_reading_assessment_success(
    db: AsyncSession, reading: SensorReading
):
    result = await handle_log_reading_assessment(
        {
            "reading_id": str(reading.id),
            "assessment_status": "normal",
            "assessment_summary": "All values within normal range.",
        },
        db,
    )
    assert result["status"] == "logged"
    assert result["reading_id"] == str(reading.id)


async def test_handle_log_reading_assessment_not_found(db: AsyncSession):
    result = await handle_log_reading_assessment(
        {
            "reading_id": str(uuid.uuid4()),
            "assessment_status": "normal",
            "assessment_summary": "Ghost reading.",
        },
        db,
    )
    assert "error" in result


# ── dispatch_tool ─────────────────────────────────────────────────────────────

async def test_dispatch_tool_unknown(db: AsyncSession):
    result = await dispatch_tool("not_a_real_tool", {}, db)
    assert "error" in result
    assert "Unknown tool" in result["error"]


async def test_dispatch_tool_handler_exception_caught(db: AsyncSession):
    """Handler that raises an internal exception returns an error dict."""
    result = await dispatch_tool(
        "get_historical_context",
        {"growing_area_id": "not-a-uuid", "crop_id": "not-a-uuid", "temperature": 72.0, "humidity": 60.0},
        db,
    )
    assert "error" in result


async def test_dispatch_yield_tool_handler_exception_caught(db: AsyncSession):
    """Yield tool handler that raises returns an error dict."""
    result = await dispatch_yield_tool(
        "get_sensor_history",
        {"growing_area_id": "not-a-uuid"},
        db,
    )
    assert "error" in result


# ── Historical context ────────────────────────────────────────────────────────

async def test_handle_get_historical_context_unknown_crop_or_area(
    db: AsyncSession, area: GrowingArea
):
    result = await handle_get_historical_context(
        {
            "growing_area_id": str(area.id),
            "crop_id": str(uuid.uuid4()),
            "temperature": 72.0,
            "humidity": 60.0,
        },
        db,
    )
    assert result["status"] == "no_data"
    assert "not found" in result["message"]


async def test_handle_get_historical_context_no_summaries(
    db: AsyncSession, area: GrowingArea, corn: Crop
):
    with patch("app.agent.tool_handlers.generate_embedding", new=AsyncMock(return_value=[0.1] * 10)), \
         patch("app.agent.tool_handlers.find_similar_weeks", new=AsyncMock(return_value=[])):
        result = await handle_get_historical_context(
            {
                "growing_area_id": str(area.id),
                "crop_id": str(corn.id),
                "temperature": 72.0,
                "humidity": 60.0,
            },
            db,
        )
    assert result["status"] == "no_data"
    assert result["summaries"] == []


async def test_handle_get_historical_context_with_summaries(
    db: AsyncSession, area: GrowingArea, corn: Crop
):
    mock_summaries = [{"week": 1, "avg_temp": 72.0}]
    with patch("app.agent.tool_handlers.generate_embedding", new=AsyncMock(return_value=[0.1] * 10)), \
         patch("app.agent.tool_handlers.find_similar_weeks", new=AsyncMock(return_value=mock_summaries)):
        result = await handle_get_historical_context(
            {
                "growing_area_id": str(area.id),
                "crop_id": str(corn.id),
                "temperature": 72.0,
                "humidity": 60.0,
            },
            db,
        )
    assert result["status"] == "ok"
    assert result["summaries"] == mock_summaries
