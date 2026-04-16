"""
Tests for alert_service.py state machine.

Covers:
  - create_alert
  - get_active_alert
  - record_normal_reading (increment + resolve at threshold)
  - record_anomalous_reading (reset counter)
  - should_send_email (new alert, interval check)
"""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertStatus, AlertType
from app.models.field import GrowingArea, GrowingAreaType
from app.models.sensor_reading import AssessmentStatus, ReadingSource, SensorReading
from app.models.user import User
from app.services.alert_service import (
    create_alert,
    get_active_alert,
    record_anomalous_reading,
    record_normal_reading,
    should_send_email,
    stamp_email_sent,
)


@pytest_asyncio.fixture
async def growing_area(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Test Field",
        area_type=GrowingAreaType.open_field,
        latitude=41.8781,
        longitude=-93.0977,
        area_acres=10.0,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def sensor_reading(db: AsyncSession, growing_area: GrowingArea) -> SensorReading:
    reading = SensorReading(
        growing_area_id=growing_area.id,
        temperature=95.0,
        humidity=20.0,
        reading_source=ReadingSource.manual,
        read_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        assessment_status=AssessmentStatus.anomalous,
    )
    db.add(reading)
    await db.flush()
    return reading


@pytest.mark.asyncio
async def test_create_alert(db: AsyncSession, growing_area: GrowingArea, sensor_reading: SensorReading):
    alert = await create_alert(
        growing_area_id=growing_area.id,
        triggering_reading_id=sensor_reading.id,
        alert_type=AlertType.temperature_high,
        assessment_summary="Temperature critically high.",
        db=db,
    )

    assert alert.id is not None
    assert alert.status == AlertStatus.active
    assert alert.consecutive_normal_count == 0
    assert alert.alert_type == AlertType.temperature_high


@pytest.mark.asyncio
async def test_get_active_alert_returns_alert(
    db: AsyncSession, growing_area: GrowingArea, sensor_reading: SensorReading
):
    await create_alert(
        growing_area_id=growing_area.id,
        triggering_reading_id=sensor_reading.id,
        alert_type=AlertType.temperature_high,
        assessment_summary="High temp.",
        db=db,
    )

    found = await get_active_alert(growing_area.id, db)
    assert found is not None
    assert found.status == AlertStatus.active


@pytest.mark.asyncio
async def test_get_active_alert_returns_none_when_no_alert(
    db: AsyncSession, growing_area: GrowingArea
):
    found = await get_active_alert(growing_area.id, db)
    assert found is None


@pytest.mark.asyncio
async def test_record_normal_reading_increments_count(
    db: AsyncSession, growing_area: GrowingArea, sensor_reading: SensorReading
):
    alert = await create_alert(
        growing_area_id=growing_area.id,
        triggering_reading_id=sensor_reading.id,
        alert_type=AlertType.humidity_low,
        assessment_summary="Low humidity.",
        db=db,
    )

    alert = await record_normal_reading(alert, "Reading back in range.", db)
    assert alert.consecutive_normal_count == 1
    assert alert.status == AlertStatus.active


@pytest.mark.asyncio
async def test_alert_resolves_at_threshold(
    db: AsyncSession, growing_area: GrowingArea, sensor_reading: SensorReading
):
    alert = await create_alert(
        growing_area_id=growing_area.id,
        triggering_reading_id=sensor_reading.id,
        alert_type=AlertType.temperature_high,
        assessment_summary="High temp.",
        db=db,
    )

    for i in range(3):
        alert = await record_normal_reading(alert, f"Normal reading {i + 1}.", db)

    assert alert.status == AlertStatus.resolved
    assert alert.resolved_at is not None
    assert alert.consecutive_normal_count == 3


@pytest.mark.asyncio
async def test_anomalous_reading_resets_counter(
    db: AsyncSession, growing_area: GrowingArea, sensor_reading: SensorReading
):
    alert = await create_alert(
        growing_area_id=growing_area.id,
        triggering_reading_id=sensor_reading.id,
        alert_type=AlertType.temperature_high,
        assessment_summary="High temp.",
        db=db,
    )

    alert = await record_normal_reading(alert, "Normal.", db)
    alert = await record_normal_reading(alert, "Normal.", db)
    assert alert.consecutive_normal_count == 2

    alert = await record_anomalous_reading(alert, "Still high.", db)
    assert alert.consecutive_normal_count == 0
    assert alert.status == AlertStatus.active


@pytest.mark.asyncio
async def test_should_send_email_on_new_alert(
    db: AsyncSession, growing_area: GrowingArea, sensor_reading: SensorReading
):
    alert = await create_alert(
        growing_area_id=growing_area.id,
        triggering_reading_id=sensor_reading.id,
        alert_type=AlertType.temperature_high,
        assessment_summary="High temp.",
        db=db,
    )
    assert await should_send_email(alert) is True


@pytest.mark.asyncio
async def test_should_not_send_email_within_interval(
    db: AsyncSession, growing_area: GrowingArea, sensor_reading: SensorReading
):
    alert = await create_alert(
        growing_area_id=growing_area.id,
        triggering_reading_id=sensor_reading.id,
        alert_type=AlertType.temperature_high,
        assessment_summary="High temp.",
        db=db,
    )
    await stamp_email_sent(alert, db)

    assert await should_send_email(alert) is False


@pytest.mark.asyncio
async def test_should_send_email_after_interval(
    db: AsyncSession, growing_area: GrowingArea, sensor_reading: SensorReading
):
    alert = await create_alert(
        growing_area_id=growing_area.id,
        triggering_reading_id=sensor_reading.id,
        alert_type=AlertType.temperature_high,
        assessment_summary="High temp.",
        db=db,
    )

    # Simulate last email sent 25 hours ago (past the 24h default interval)
    alert.last_email_sent_at = datetime.now(timezone.utc) - timedelta(hours=25)
    assert await should_send_email(alert) is True
