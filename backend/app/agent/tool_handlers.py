"""
Tool handler implementations for the Yearly Yields anomaly-check agent.

Each function here corresponds to one tool defined in tools.py.
The loop calls dispatch_tool() with the tool name and input from Claude,
which routes to the correct handler and returns a JSON-serializable result.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.alert import Alert, AlertStatus, AlertType
from app.models.crop import CropCycle
from app.models.field import GrowingArea
from app.models.sensor_reading import AssessmentStatus, SensorReading


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def dispatch_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    handlers = {
        "get_historical_context": handle_get_historical_context,
        "get_weather_context": handle_get_weather_context,
        "get_active_alert": handle_get_active_alert,
        "create_alert": handle_create_alert,
        "update_alert": handle_update_alert,
        "send_alert_email": handle_send_alert_email,
        "log_reading_assessment": handle_log_reading_assessment,
    }

    handler = handlers.get(tool_name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        return await handler(tool_input, db)
    except Exception as e:
        return {"error": str(e)}


# ── Handlers ──────────────────────────────────────────────────────────────────

async def handle_get_historical_context(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Vector similarity search against historical_summaries.
    TODO: implement pgvector similarity query via vector_service.py
    """
    return {
        "status": "no_data",
        "message": "Historical context service not yet implemented.",
        "summaries": [],
    }


async def handle_get_weather_context(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Fetch current regional weather from NOAA for the growing area's lat/lon.
    TODO: implement NOAA API client
    """
    growing_area_id = uuid.UUID(tool_input["growing_area_id"])
    result = await db.execute(
        select(GrowingArea).where(GrowingArea.id == growing_area_id)
    )
    area = result.scalar_one_or_none()
    if area is None:
        return {"error": f"Growing area {growing_area_id} not found."}

    return {
        "status": "not_implemented",
        "message": "NOAA weather service not yet implemented.",
        "latitude": area.latitude,
        "longitude": area.longitude,
    }


async def handle_get_active_alert(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    growing_area_id = uuid.UUID(tool_input["growing_area_id"])
    result = await db.execute(
        select(Alert).where(
            Alert.growing_area_id == growing_area_id,
            Alert.status == AlertStatus.active,
        )
    )
    alert = result.scalar_one_or_none()

    if alert is None:
        return {"active_alert": None}

    return {
        "active_alert": {
            "id": str(alert.id),
            "alert_type": alert.alert_type.value,
            "consecutive_normal_count": alert.consecutive_normal_count,
            "last_email_sent_at": (
                alert.last_email_sent_at.isoformat()
                if alert.last_email_sent_at
                else None
            ),
            "created_at": alert.created_at.isoformat(),
        }
    }


async def handle_create_alert(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    alert = Alert(
        growing_area_id=uuid.UUID(tool_input["growing_area_id"]),
        crop_cycle_id=(
            uuid.UUID(tool_input["crop_cycle_id"])
            if tool_input.get("crop_cycle_id")
            else None
        ),
        triggering_reading_id=uuid.UUID(tool_input["triggering_reading_id"]),
        alert_type=AlertType(tool_input["alert_type"]),
        status=AlertStatus.active,
        consecutive_normal_count=0,
        assessment_summary=tool_input.get("assessment_summary"),
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    return {"alert_id": str(alert.id), "status": "created"}


async def handle_update_alert(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    alert_id = uuid.UUID(tool_input["alert_id"])
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if alert is None:
        return {"error": f"Alert {alert_id} not found."}

    alert.consecutive_normal_count = tool_input["consecutive_normal_count"]
    alert.status = AlertStatus(tool_input["status"])

    if tool_input.get("assessment_summary"):
        alert.assessment_summary = tool_input["assessment_summary"]

    if alert.status == AlertStatus.resolved:
        alert.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    return {"alert_id": str(alert.id), "status": alert.status.value}


async def handle_send_alert_email(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Send alert email via SendGrid.
    TODO: implement SendGrid email service
    """
    alert_id = uuid.UUID(tool_input["alert_id"])
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if alert is None:
        return {"error": f"Alert {alert_id} not found."}

    # TODO: call SendGrid service here
    # For now, just stamp last_email_sent_at so the interval logic works
    alert.last_email_sent_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "not_implemented",
        "message": "Email service not yet implemented. Timestamp updated.",
        "alert_id": str(alert.id),
    }


async def handle_log_reading_assessment(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    reading_id = uuid.UUID(tool_input["reading_id"])
    result = await db.execute(
        select(SensorReading).where(SensorReading.id == reading_id)
    )
    reading = result.scalar_one_or_none()

    if reading is None:
        return {"error": f"SensorReading {reading_id} not found."}

    reading.assessment_status = AssessmentStatus(tool_input["assessment_status"])
    reading.assessment_summary = tool_input["assessment_summary"]
    await db.commit()

    return {"status": "logged", "reading_id": str(reading.id)}
