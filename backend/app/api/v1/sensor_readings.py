import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.loop import run_anomaly_check
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.field import GrowingArea
from app.models.sensor_reading import AssessmentStatus, SensorReading
from app.models.user import User
from app.schemas.sensor_reading import SensorReadingCreate, SensorReadingRead

router = APIRouter()


@router.post("/", response_model=SensorReadingRead, status_code=status.HTTP_201_CREATED)
async def create_sensor_reading(
    payload: SensorReadingCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SensorReadingRead:
    reading = SensorReading(
        growing_area_id=payload.growing_area_id,
        crop_cycle_id=payload.crop_cycle_id,
        temperature=payload.temperature,
        humidity=payload.humidity,
        reading_source=payload.reading_source,
        read_at=payload.read_at,
        received_at=datetime.now(timezone.utc),
        assessment_status=AssessmentStatus.pending,
    )

    db.add(reading)
    await db.commit()
    await db.refresh(reading)

    background_tasks.add_task(run_anomaly_check, reading.id, db)

    return SensorReadingRead.model_validate(reading)


@router.get("/", response_model=List[SensorReadingRead])
async def list_sensor_readings(
    growing_area_id: Optional[uuid.UUID] = None,
    crop_cycle_id: Optional[uuid.UUID] = None,
    assessment_status: Optional[AssessmentStatus] = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[SensorReadingRead]:
    query = (
        select(SensorReading)
        .join(SensorReading.growing_area)
        .where(GrowingArea.owner_id == current_user.id)
        .order_by(SensorReading.read_at.desc())
        .limit(limit)
    )
    if growing_area_id is not None:
        query = query.where(SensorReading.growing_area_id == growing_area_id)
    if crop_cycle_id is not None:
        query = query.where(SensorReading.crop_cycle_id == crop_cycle_id)
    if assessment_status is not None:
        query = query.where(SensorReading.assessment_status == assessment_status)

    result = await db.execute(query)
    return [SensorReadingRead.model_validate(r) for r in result.scalars().all()]
