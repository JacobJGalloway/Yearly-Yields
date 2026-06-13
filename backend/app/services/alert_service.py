"""
Alert service — owns the alert state machine.

State machine:
  active → resolved when consecutive_normal_count reaches 3.

Rules (enforced here, not in the agent):
  - Only one active alert per growing area at a time.
  - On anomalous reading: create alert (if none active) or reset consecutive_normal_count to 0.
  - On normal reading: increment consecutive_normal_count.
    If consecutive_normal_count == 3: resolve the alert.
  - Email on creation; repeat email only after ALERT_EMAIL_INTERVAL_HOURS have passed.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.alert import Alert, AlertStatus, AlertType
from app.models.sensor_reading import SensorReading


async def get_active_alert(
    growing_area_id: uuid.UUID,
    db: AsyncSession,
) -> Optional[Alert]:
    """Return the active alert for a growing area, or None if none exists."""
    result = await db.execute(
        select(Alert).where(
            Alert.growing_area_id == growing_area_id,
            Alert.status == AlertStatus.active,
        )
    )
    return result.scalar_one_or_none()


async def create_alert(
    growing_area_id: uuid.UUID,
    triggering_reading_id: uuid.UUID,
    alert_type: AlertType,
    assessment_summary: str,
    db: AsyncSession,
    crop_cycle_id: Optional[uuid.UUID] = None,
) -> Alert:
    """
    Create a new active alert.
    Caller is responsible for ensuring no active alert already exists
    for this growing area (call get_active_alert first).
    """
    reading_result = await db.execute(
        select(SensorReading).where(SensorReading.id == triggering_reading_id)
    )
    reading = reading_result.scalar_one_or_none()
    plot_id = reading.growing_area_plot_id if reading else None

    alert = Alert(
        growing_area_id=growing_area_id,
        growing_area_plot_id=plot_id,
        crop_cycle_id=crop_cycle_id,
        triggering_reading_id=triggering_reading_id,
        alert_type=alert_type,
        status=AlertStatus.active,
        consecutive_normal_count=0,
        assessment_summary=assessment_summary,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


async def record_anomalous_reading(
    alert: Alert,
    assessment_summary: str,
    db: AsyncSession,
) -> Alert:
    """
    Called when an anomalous reading comes in and an active alert already exists.
    Resets the consecutive normal counter — the farmer is still in trouble.
    """
    alert.consecutive_normal_count = 0
    alert.assessment_summary = assessment_summary
    await db.commit()
    await db.refresh(alert)
    return alert


async def record_normal_reading(
    alert: Alert,
    assessment_summary: str,
    db: AsyncSession,
) -> Alert:
    """
    Called when a normal reading comes in while an alert is active.
    Increments the consecutive normal counter.
    Resolves the alert when the threshold (3) is reached.
    """
    alert.consecutive_normal_count += 1
    alert.assessment_summary = assessment_summary

    if alert.consecutive_normal_count >= settings.ALERT_RESOLUTION_THRESHOLD:
        alert.status = AlertStatus.resolved
        alert.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(alert)
    return alert


async def should_send_email(alert: Alert) -> bool:
    """
    Return True if an alert email should be sent.

    Conditions:
      - New alert (last_email_sent_at is None), OR
      - More than ALERT_EMAIL_INTERVAL_HOURS have passed since the last email.
    """
    if alert.last_email_sent_at is None:
        return True

    now = datetime.now(timezone.utc)
    hours_since_last = (now - alert.last_email_sent_at).total_seconds() / 3600
    return hours_since_last >= settings.ALERT_EMAIL_INTERVAL_HOURS


async def stamp_email_sent(alert: Alert, db: AsyncSession) -> None:
    """Update last_email_sent_at to now after an email is dispatched."""
    alert.last_email_sent_at = datetime.now(timezone.utc)
    await db.commit()
