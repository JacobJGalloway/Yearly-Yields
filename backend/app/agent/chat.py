"""
Conversational dashboard chat agent — read-only farm advisor.

Accepts a user message + prior conversation history, calls Claude with a set of
read-only tools, and returns a plain-text response. No alerts are created or modified.
"""

import uuid
from typing import Any

import anthropic
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import DASHBOARD_CHAT_SYSTEM_PROMPT
from app.config import settings
from app.models.alert import Alert, AlertStatus
from app.models.crop import Crop, CropCycle, CropCycleStatus
from app.models.field import GrowingArea
from app.models.sensor_reading import SensorReading

_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

MAX_ITERATIONS = 5

_CHAT_TOOLS = [
    {
        "name": "get_active_cycles",
        "description": "Retrieve all active crop cycles for this farm with crop name and planting details.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_recent_readings",
        "description": "Retrieve the most recent sensor readings across all growing areas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of readings to return (default 20, max 50).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_active_alerts",
        "description": "Retrieve all currently active anomaly alerts.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


async def run_chat(
    message: str,
    history: list[dict],
    db: AsyncSession,
    owner_id: str,
) -> str:
    messages = [*history, {"role": "user", "content": message}]

    for _ in range(MAX_ITERATIONS):
        response = await _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=DASHBOARD_CHAT_SYSTEM_PROMPT,
            tools=_CHAT_TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    return block.text
            return "I wasn't able to generate a response."

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await _dispatch(block.name, block.input, db, owner_id)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages.append({"role": "user", "content": tool_results})

    return "I wasn't able to complete your request within the allowed steps."


async def _dispatch(
    name: str, inp: dict[str, Any], db: AsyncSession, owner_id: str
) -> dict:
    if name == "get_active_cycles":
        return await _get_active_cycles(db, owner_id)
    if name == "get_recent_readings":
        return await _get_recent_readings(db, owner_id, min(int(inp.get("limit", 20)), 50))
    if name == "get_active_alerts":
        return await _get_active_alerts(db, owner_id)
    return {"error": f"Unknown tool: {name}"}


async def _get_active_cycles(db: AsyncSession, owner_id: str) -> dict:
    result = await db.execute(
        select(CropCycle, Crop, GrowingArea)
        .join(GrowingArea, CropCycle.growing_area_id == GrowingArea.id)
        .outerjoin(Crop, CropCycle.crop_id == Crop.id)
        .where(
            GrowingArea.owner_id == uuid.UUID(owner_id),
            CropCycle.status == CropCycleStatus.active,
        )
        .order_by(CropCycle.planted_at.desc())
    )
    rows = result.all()
    if not rows:
        return {"status": "no_data", "cycles": []}

    return {
        "status": "ok",
        "cycles": [
            {
                "area_name": area.name,
                "crop_name": crop.name if crop else "unknown",
                "planted_at": cycle.planted_at.isoformat(),
                "season_year": cycle.season_year,
                "cycle_number": cycle.cycle_number,
                "target_yield": cycle.target_yield,
                "yield_unit": cycle.yield_unit.value,
            }
            for cycle, crop, area in rows
        ],
    }


async def _get_recent_readings(db: AsyncSession, owner_id: str, limit: int) -> dict:
    result = await db.execute(
        select(SensorReading, GrowingArea)
        .join(GrowingArea, SensorReading.growing_area_id == GrowingArea.id)
        .where(GrowingArea.owner_id == uuid.UUID(owner_id))
        .order_by(desc(SensorReading.read_at))
        .limit(limit)
    )
    rows = result.all()
    if not rows:
        return {"status": "no_data", "readings": []}

    return {
        "status": "ok",
        "readings": [
            {
                "area_name": area.name,
                "read_at": reading.read_at.isoformat(),
                "temperature_f": reading.temperature,
                "humidity_pct": reading.humidity,
                "ph": reading.ph,
                "assessment_status": reading.assessment_status.value,
            }
            for reading, area in rows
        ],
    }


async def _get_active_alerts(db: AsyncSession, owner_id: str) -> dict:
    result = await db.execute(
        select(Alert, GrowingArea)
        .join(GrowingArea, Alert.growing_area_id == GrowingArea.id)
        .where(
            GrowingArea.owner_id == uuid.UUID(owner_id),
            Alert.status == AlertStatus.active,
        )
        .order_by(desc(Alert.created_at))
    )
    rows = result.all()
    if not rows:
        return {"active_alerts": []}

    return {
        "active_alerts": [
            {
                "area_name": area.name,
                "alert_type": alert.alert_type.value,
                "created_at": alert.created_at.isoformat(),
                "consecutive_normal_count": alert.consecutive_normal_count,
                "summary": alert.assessment_summary,
            }
            for alert, area in rows
        ],
    }
