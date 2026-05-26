"""
Conversational dashboard chat agent — read-only farm data analyst.

Accepts a user message + prior conversation history, calls Claude with a set of
read-only data-query tools and terminal render tools, and returns a structured
response dict describing how the frontend should display the answer.

Response types:
  chart             — ngx-echarts visualization (bar_grouped, line_multi, etc.)
  table             — column/row data table
  link              — external reference URL
  clarifying_question — follow-up question from Claude before it can answer
  text              — plain text (simple questions, "I don't know", errors)
"""

import json
import uuid
from datetime import date, datetime
from typing import Any

import anthropic
from anthropic import BadRequestError, APIStatusError
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import DASHBOARD_CHAT_SYSTEM_PROMPT
from app.config import settings
from app.mcp.client import get_session as get_mcp_session
from app.models.alert import Alert, AlertStatus
from app.models.crop import Crop, CropCycle, CropCycleStatus
from app.models.field import GrowingArea
from app.models.sensor_reading import SensorReading
from app.models.weekly_sensor_summary import WeeklySensorSummary

_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

MAX_ITERATIONS = 8

_RENDER_TOOLS = {"render_chart", "render_table", "provide_link", "ask_clarification"}
_CHAT_MCP_TOOL_NAMES = frozenset({"get_chat_memory", "save_chat_memory"})

# Cached at first call — MCP tool schemas don't change at runtime.
_chat_mcp_tool_schemas: list[dict[str, Any]] | None = None


async def _get_chat_tools() -> list[dict[str, Any]]:
    global _chat_mcp_tool_schemas
    if _chat_mcp_tool_schemas is None:
        result = await get_mcp_session().list_tools()
        _chat_mcp_tool_schemas = [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
            }
            for t in result.tools
            if t.name in _CHAT_MCP_TOOL_NAMES
        ]
    return _chat_mcp_tool_schemas + _CHAT_TOOLS

_CHAT_TOOLS = [
    # ── Existing data tools ───────────────────────────────────────────────────
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
    # ── New date-range query tools ────────────────────────────────────────────
    {
        "name": "query_sensor_readings",
        "description": (
            "Query raw sensor readings for a date range. Best for recent data (last few weeks). "
            "For longer historical ranges use query_weekly_summaries instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["temperature", "humidity", "ph", "wind_speed"],
                    "description": "The sensor metric to retrieve.",
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (inclusive).",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format (inclusive).",
                },
                "area_name": {
                    "type": "string",
                    "description": "Optional growing area name filter (partial match, case-insensitive).",
                },
            },
            "required": ["metric", "start_date", "end_date"],
        },
    },
    {
        "name": "query_weekly_summaries",
        "description": (
            "Query weekly-aggregated sensor data. Best for year-over-year comparisons and "
            "multi-month trend analysis. Returns one row per area per week."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["avg_temperature", "avg_humidity", "avg_ph", "avg_wind_speed"],
                    "description": "The aggregated metric to retrieve.",
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (inclusive).",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format (inclusive).",
                },
                "area_name": {
                    "type": "string",
                    "description": "Optional growing area name filter (partial match, case-insensitive).",
                },
            },
            "required": ["metric", "start_date", "end_date"],
        },
    },
    {
        "name": "query_harvest_history",
        "description": "Query actual harvest yields across completed crop cycles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "crop_name": {
                    "type": "string",
                    "description": "Optional crop name filter (partial match, case-insensitive).",
                },
                "start_year": {
                    "type": "integer",
                    "description": "First season year to include (inclusive).",
                },
                "end_year": {
                    "type": "integer",
                    "description": "Last season year to include (inclusive).",
                },
            },
            "required": [],
        },
    },
    # ── Terminal render tools ─────────────────────────────────────────────────
    {
        "name": "render_chart",
        "description": (
            "Render a chart as the final answer. Call this when data is best shown as a "
            "visualization. chart_type options: bar_grouped (multiple series side-by-side), "
            "bar_stacked (stacked bars), line_multi (one line per series), bar_single (one series)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Chart title shown above the chart."},
                "chart_type": {
                    "type": "string",
                    "enum": ["bar_grouped", "bar_stacked", "line_multi", "bar_single"],
                },
                "x_labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "X-axis category labels (weeks, months, years, etc.).",
                },
                "series": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "data": {
                                "type": "array",
                                "items": {"type": ["number", "null"]},
                            },
                        },
                        "required": ["name", "data"],
                    },
                    "description": "Data series — one per year, crop, or area.",
                },
                "y_axis_label": {
                    "type": "string",
                    "description": "Y-axis unit label (e.g. '°F', '%', 'bushels/acre').",
                },
            },
            "required": ["title", "chart_type", "x_labels", "series"],
        },
    },
    {
        "name": "render_table",
        "description": "Render a data table as the final answer. Use when listing records is clearer than a chart.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Column header labels.",
                },
                "rows": {
                    "type": "array",
                    "items": {"type": "array"},
                    "description": "Table rows — each row is an array matching the columns order.",
                },
            },
            "required": ["title", "columns", "rows"],
        },
    },
    {
        "name": "provide_link",
        "description": (
            "Provide an external reference link when the answer exists outside this system "
            "(e.g. NOAA weather history, university extension guides, market prices)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Short description of what this link provides.",
                },
                "url": {"type": "string", "description": "The full URL."},
            },
            "required": ["text", "url"],
        },
    },
    {
        "name": "ask_clarification",
        "description": (
            "Ask the user a follow-up question when you need more information to choose "
            "the right response type or data scope."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional suggested answer choices to show the user.",
                },
            },
            "required": ["question"],
        },
        "cache_control": {"type": "ephemeral"},
    },
]


async def run_chat(
    message: str,
    history: list[dict],
    db: AsyncSession,
    owner_id: str,
) -> dict[str, Any]:
    messages = [*history, {"role": "user", "content": message}]

    # Inject session context on the first turn so Claude knows the user_id for memory tools.
    # Goes in the user message (not system prompt) so the static system prompt stays cached.
    if not history:
        messages[0]["content"] = (
            f"[Session context: user_id={owner_id}, date={date.today().isoformat()}]\n\n"
            + messages[0]["content"]
        )

    try:
        return await _run_chat_loop(messages, db, owner_id)
    except BadRequestError as e:
        msg = e.body.get("error", {}).get("message", str(e)) if isinstance(e.body, dict) else str(e)
        return {"type": "text", "content": f"AI service error: {msg}"}
    except APIStatusError as e:
        return {"type": "text", "content": f"AI service unavailable (HTTP {e.status_code}). Please try again later."}
    except Exception:
        return {"type": "text", "content": "An unexpected error occurred. Please try again."}


async def _run_chat_loop(
    messages: list[dict],
    db: AsyncSession,
    owner_id: str,
) -> dict[str, Any]:
    all_tools = await _get_chat_tools()
    for _ in range(MAX_ITERATIONS):
        response = await _client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=2048,
            system=[{"type": "text", "text": DASHBOARD_CHAT_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=all_tools,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    return {"type": "text", "content": block.text}
            return {"type": "text", "content": "I wasn't able to generate a response."}

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if block.name in _RENDER_TOOLS:
                    return _build_render_response(block.name, block.input)
                if block.name in _CHAT_MCP_TOOL_NAMES:
                    mcp_result = await get_mcp_session().call_tool(
                        name=block.name, arguments=block.input
                    )
                    if mcp_result.isError:
                        content = json.dumps({"error": f"MCP tool {block.name} returned an error"})
                    elif mcp_result.content and hasattr(mcp_result.content[0], "text"):
                        content = mcp_result.content[0].text
                    else:
                        content = json.dumps({"error": "empty MCP response"})
                else:
                    content = str(await _dispatch(block.name, block.input, db, owner_id))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

    return {"type": "text", "content": "I wasn't able to complete your request within the allowed steps."}


def _build_render_response(tool_name: str, inp: dict) -> dict[str, Any]:
    if tool_name == "render_chart":
        return {
            "type": "chart",
            "title": inp.get("title", ""),
            "chart_type": inp.get("chart_type", "bar_grouped"),
            "x_labels": inp.get("x_labels", []),
            "series": inp.get("series", []),
            "y_axis_label": inp.get("y_axis_label"),
        }
    if tool_name == "render_table":
        return {
            "type": "table",
            "title": inp.get("title", ""),
            "columns": inp.get("columns", []),
            "rows": inp.get("rows", []),
        }
    if tool_name == "provide_link":
        return {
            "type": "link",
            "content": inp.get("text", ""),
            "url": inp.get("url", ""),
        }
    if tool_name == "ask_clarification":
        return {
            "type": "clarifying_question",
            "content": inp.get("question", ""),
            "options": inp.get("options", []),
        }
    return {"type": "text", "content": "Unknown response type."}


async def _dispatch(
    name: str, inp: dict[str, Any], db: AsyncSession, owner_id: str
) -> dict:
    if name == "get_active_cycles":
        return await _get_active_cycles(db, owner_id)
    if name == "get_recent_readings":
        return await _get_recent_readings(db, owner_id, min(int(inp.get("limit", 20)), 50))
    if name == "get_active_alerts":
        return await _get_active_alerts(db, owner_id)
    if name == "query_sensor_readings":
        return await _query_sensor_readings(db, owner_id, inp)
    if name == "query_weekly_summaries":
        return await _query_weekly_summaries(db, owner_id, inp)
    if name == "query_harvest_history":
        return await _query_harvest_history(db, owner_id, inp)
    return {"error": f"Unknown tool: {name}"}


# ── Data handlers ─────────────────────────────────────────────────────────────

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


async def _query_sensor_readings(
    db: AsyncSession, owner_id: str, inp: dict
) -> dict:
    metric = inp["metric"]
    start = date.fromisoformat(inp["start_date"])
    end = date.fromisoformat(inp["end_date"])
    area_filter = inp.get("area_name", "").strip().lower()

    metric_col = getattr(SensorReading, metric, None)
    if metric_col is None:
        return {"error": f"Unknown metric: {metric}"}

    conditions = [
        GrowingArea.owner_id == uuid.UUID(owner_id),
        SensorReading.read_at >= datetime(start.year, start.month, start.day),
        SensorReading.read_at < datetime(end.year, end.month, end.day + 1),
        metric_col.isnot(None),
    ]

    result = await db.execute(
        select(SensorReading.read_at, metric_col, GrowingArea.name)
        .join(GrowingArea, SensorReading.growing_area_id == GrowingArea.id)
        .where(and_(*conditions))
        .order_by(SensorReading.read_at)
        .limit(500)
    )
    rows = result.all()

    if area_filter:
        rows = [r for r in rows if area_filter in r[2].lower()]

    if not rows:
        return {"status": "no_data", "readings": []}

    return {
        "status": "ok",
        "metric": metric,
        "readings": [
            {"read_at": r[0].isoformat(), "value": r[1], "area_name": r[2]}
            for r in rows
        ],
    }


async def _query_weekly_summaries(
    db: AsyncSession, owner_id: str, inp: dict
) -> dict:
    metric = inp["metric"]
    start = date.fromisoformat(inp["start_date"])
    end = date.fromisoformat(inp["end_date"])
    area_filter = inp.get("area_name", "").strip().lower()

    metric_col = getattr(WeeklySensorSummary, metric, None)
    if metric_col is None:
        return {"error": f"Unknown metric: {metric}"}

    result = await db.execute(
        select(WeeklySensorSummary.week_start, metric_col, GrowingArea.name)
        .join(GrowingArea, WeeklySensorSummary.growing_area_id == GrowingArea.id)
        .where(
            GrowingArea.owner_id == uuid.UUID(owner_id),
            WeeklySensorSummary.week_start >= start,
            WeeklySensorSummary.week_start <= end,
            metric_col.isnot(None),
        )
        .order_by(WeeklySensorSummary.week_start)
    )
    rows = result.all()

    if area_filter:
        rows = [r for r in rows if area_filter in r[2].lower()]

    if not rows:
        return {"status": "no_data", "summaries": []}

    return {
        "status": "ok",
        "metric": metric,
        "summaries": [
            {"week_start": r[0].isoformat(), "value": r[1], "area_name": r[2]}
            for r in rows
        ],
    }


async def _query_harvest_history(
    db: AsyncSession, owner_id: str, inp: dict
) -> dict:
    crop_filter = inp.get("crop_name", "").strip().lower()
    start_year = inp.get("start_year")
    end_year = inp.get("end_year")

    conditions = [
        GrowingArea.owner_id == uuid.UUID(owner_id),
        CropCycle.status == CropCycleStatus.harvested,
        CropCycle.actual_yield.isnot(None),
    ]
    if start_year:
        conditions.append(CropCycle.season_year >= start_year)
    if end_year:
        conditions.append(CropCycle.season_year <= end_year)

    result = await db.execute(
        select(CropCycle, Crop, GrowingArea)
        .join(GrowingArea, CropCycle.growing_area_id == GrowingArea.id)
        .outerjoin(Crop, CropCycle.crop_id == Crop.id)
        .where(and_(*conditions))
        .order_by(CropCycle.season_year, CropCycle.harvested_at)
    )
    rows = result.all()

    if crop_filter:
        rows = [r for r in rows if crop_filter in (r[1].name if r[1] else "").lower()]

    if not rows:
        return {"status": "no_data", "cycles": []}

    return {
        "status": "ok",
        "cycles": [
            {
                "area_name": area.name,
                "crop_name": crop.name if crop else "unknown",
                "season_year": cycle.season_year,
                "actual_yield": cycle.actual_yield,
                "yield_unit": cycle.yield_unit.value,
                "harvested_at": cycle.harvested_at.isoformat() if cycle.harvested_at else None,
            }
            for cycle, crop, area in rows
        ],
    }
