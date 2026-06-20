"""
Local MCP server — exposes Yearly Yields database as read-only tools.

Run as a module via stdio transport (started by app/mcp/client.py at lifespan).
Uses asyncpg directly so it carries no FastAPI/SQLAlchemy dependencies.
"""

import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
from mcp.server.fastmcp import FastMCP

from app.core.crop_phases import get_phase_days
from app.core.crop_ranges import get_crop_ranges as _get_crop_ranges

mcp = FastMCP("yearly-yields")

_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # asyncpg expects the plain postgresql:// scheme, not the SQLAlchemy async variant
        dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(dsn)
    return _pool


@mcp.tool()
async def get_cycle_context(crop_cycle_id: str) -> dict[str, Any]:
    """
    Return the current phase and ideal sensor ranges for an active crop cycle.
    Call this when a crop_cycle_id is available to get crop-specific context
    before comparing a reading against historical data.
    """
    cycle_uuid = uuid.UUID(crop_cycle_id)
    pool = await _get_pool()
    async with pool.acquire() as conn:
        cycle = await conn.fetchrow(
            "SELECT crop_id, planted_at, forecasted_end_date FROM crop_cycles WHERE id = $1",
            cycle_uuid,
        )
        if cycle is None:
            return {"error": f"Crop cycle {crop_cycle_id} not found"}

        crop = await conn.fetchrow(
            "SELECT name FROM crops WHERE id = $1",
            cycle["crop_id"],
        )
        if crop is None:
            return {"error": f"Crop not found for cycle {crop_cycle_id}"}

    crop_name: str = crop["name"]
    planted: date = cycle["planted_at"]
    forecasted_end: date | None = cycle["forecasted_end_date"]
    days_in = (date.today() - planted).days

    phase_days = get_phase_days(crop_name, planted_at=planted, forecasted_end=forecasted_end)
    if days_in < phase_days.seeding_days:
        phase = "seeding"
    elif days_in < phase_days.seeding_days + phase_days.growing_days:
        phase = "growing"
    else:
        phase = "harvest"

    ranges = _get_crop_ranges(crop_name)
    phase_range = getattr(ranges, phase) if ranges else None

    result: dict[str, Any] = {
        "crop_name": crop_name,
        "phase": phase,
        "days_in_cycle": days_in,
    }
    if phase_range:
        result.update({
            "temp_min_f": phase_range.temp_min_f,
            "temp_max_f": phase_range.temp_max_f,
            "humidity_min": phase_range.humidity_min,
            "humidity_max": phase_range.humidity_max,
            "ph_min": phase_range.ph_min,
            "ph_max": phase_range.ph_max,
        })

    return result


@mcp.tool()
async def get_active_alert(
    growing_area_id: str,
    growing_area_plot_id: str | None = None,
) -> dict[str, Any]:
    """
    Return the currently active (unresolved) alert for a growing area, or null if none.
    When growing_area_plot_id is provided, scopes the lookup to that plot only.
    Check this before creating a new alert.
    """
    area_uuid = uuid.UUID(growing_area_id)
    pool = await _get_pool()
    async with pool.acquire() as conn:
        if growing_area_plot_id:
            row = await conn.fetchrow(
                """
                SELECT id, alert_type, consecutive_normal_count,
                       last_email_sent_at, created_at
                FROM alerts
                WHERE growing_area_id = $1
                  AND growing_area_plot_id = $2
                  AND status = 'active'
                LIMIT 1
                """,
                area_uuid,
                uuid.UUID(growing_area_plot_id),
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT id, alert_type, consecutive_normal_count,
                       last_email_sent_at, created_at
                FROM alerts
                WHERE growing_area_id = $1 AND status = 'active'
                LIMIT 1
                """,
                area_uuid,
            )

    if row is None:
        return {"active_alert": None}

    return {
        "active_alert": {
            "id": str(row["id"]),
            "alert_type": row["alert_type"],
            "consecutive_normal_count": row["consecutive_normal_count"],
            "last_email_sent_at": (
                row["last_email_sent_at"].isoformat() if row["last_email_sent_at"] else None
            ),
            "created_at": row["created_at"].isoformat(),
        }
    }


@mcp.tool()
async def get_recent_readings(
    growing_area_id: str,
    limit: int = 20,
    growing_area_plot_id: str | None = None,
) -> dict[str, Any]:
    """
    Return recent sensor readings for a growing area (max 50).
    When growing_area_plot_id is provided, scopes results to that plot only.
    """
    area_uuid = uuid.UUID(growing_area_id)
    limit = min(max(limit, 1), 50)
    pool = await _get_pool()
    async with pool.acquire() as conn:
        if growing_area_plot_id:
            rows = await conn.fetch(
                """
                SELECT read_at, temperature, humidity, ph, wind_speed, assessment_status
                FROM sensor_readings
                WHERE growing_area_id = $1
                  AND growing_area_plot_id = $2
                ORDER BY read_at DESC
                LIMIT $3
                """,
                area_uuid,
                uuid.UUID(growing_area_plot_id),
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT read_at, temperature, humidity, ph, wind_speed, assessment_status
                FROM sensor_readings
                WHERE growing_area_id = $1
                ORDER BY read_at DESC
                LIMIT $2
                """,
                area_uuid,
                limit,
            )

    return {
        "readings": [
            {
                "read_at": row["read_at"].isoformat(),
                "temperature": row["temperature"],
                "humidity": row["humidity"],
                "ph": row["ph"],
                "wind_speed": row["wind_speed"],
                "assessment_status": row["assessment_status"],
            }
            for row in rows
        ]
    }


_MEMORY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "chat_memory"


@mcp.tool()
async def get_chat_memory(user_id: str) -> dict[str, Any]:
    """
    Load persisted conversation context for a user from prior sessions.
    Returns summary and key_facts if memory exists, or status 'no_memory' if not.
    """
    _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    path = _MEMORY_DIR / f"{user_id}.json"
    if not path.exists():
        return {"status": "no_memory", "summary": None, "key_facts": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"status": "ok", **data}
    except Exception:
        return {"status": "no_memory", "summary": None, "key_facts": []}


@mcp.tool()
async def save_chat_memory(user_id: str, summary: str, key_facts: list[str]) -> dict[str, Any]:
    """
    Persist conversation context for a user to recall in future sessions.
    summary: one or two sentences describing the farm and what the user typically asks about.
    key_facts: list of specific facts worth remembering (concerns, preferences, crop details).
    """
    _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    path = _MEMORY_DIR / f"{user_id}.json"
    data = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "key_facts": key_facts,
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"status": "saved"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
