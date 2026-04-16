from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.loop import run_anomaly_check
from app.db.session import get_db
from app.models.sensor_reading import AssessmentStatus, SensorReading
from app.schemas.sensor_reading import SensorReadingCreate, SensorReadingRead

router = APIRouter()


@router.post("/", response_model=SensorReadingRead, status_code=status.HTTP_201_CREATED)
async def create_sensor_reading(
    payload: SensorReadingCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
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
