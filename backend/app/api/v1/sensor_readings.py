import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.loop import run_anomaly_check
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.field import GrowingArea
from app.models.sensor_reading import AssessmentStatus, SensorReading
from app.models.user import User
from app.schemas.sensor_reading import SensorReadingCreate, SensorReadingRead, WeeklySummaryRead

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
    limit: int = Query(default=100, ge=1, le=20000),
    since: Optional[datetime] = Query(default=None, description="ISO timestamp — return readings at or after this time"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[SensorReadingRead]:
    query = (
        select(SensorReading)
        .join(SensorReading.growing_area)
        .where(GrowingArea.owner_id == current_user.id)
        .order_by(SensorReading.read_at.desc())
    )
    if growing_area_id is not None:
        query = query.where(SensorReading.growing_area_id == growing_area_id)
    if crop_cycle_id is not None:
        query = query.where(SensorReading.crop_cycle_id == crop_cycle_id)
    if assessment_status is not None:
        query = query.where(SensorReading.assessment_status == assessment_status)
    if since is not None:
        query = query.where(SensorReading.read_at >= since)
    query = query.limit(limit)

    result = await db.execute(query)
    return [SensorReadingRead.model_validate(r) for r in result.scalars().all()]


@router.get("/weekly-summary", response_model=List[WeeklySummaryRead])
async def get_weekly_summary(
    growing_area_id: Optional[uuid.UUID] = None,
    weeks: int = Query(default=52, ge=1, le=156),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[WeeklySummaryRead]:
    area_filter = ""
    params: dict = {"owner_id": str(current_user.id), "weeks": weeks}

    if growing_area_id is not None:
        area_filter = "AND sr.growing_area_id = :growing_area_id"
        params["growing_area_id"] = str(growing_area_id)

    sql = text(f"""
        SELECT
            EXTRACT(ISOYEAR FROM sr.read_at)::int AS year,
            EXTRACT(WEEK FROM sr.read_at)::int    AS iso_week,
            sr.growing_area_id,
            AVG(sr.temperature)  AS avg_temp_f,
            AVG(sr.humidity)     AS avg_humidity_pct,
            COUNT(*)             AS reading_count
        FROM sensor_readings sr
        JOIN growing_areas ga ON ga.id = sr.growing_area_id
        WHERE ga.owner_id = :owner_id
          AND sr.read_at >= NOW() - (:weeks * INTERVAL '1 week')
          {area_filter}
        GROUP BY
            EXTRACT(ISOYEAR FROM sr.read_at),
            EXTRACT(WEEK FROM sr.read_at),
            sr.growing_area_id
        ORDER BY year ASC, iso_week ASC
    """)

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    return [
        WeeklySummaryRead(
            iso_week=int(row["iso_week"]),
            year=int(row["year"]),
            week_label=f"Wk {int(row['iso_week'])} {int(row['year'])}",
            avg_temp_f=float(row["avg_temp_f"]) if row["avg_temp_f"] is not None else None,
            avg_humidity_pct=float(row["avg_humidity_pct"]) if row["avg_humidity_pct"] is not None else None,
            reading_count=int(row["reading_count"]),
            growing_area_id=uuid.UUID(str(row["growing_area_id"])),
        )
        for row in rows
    ]
