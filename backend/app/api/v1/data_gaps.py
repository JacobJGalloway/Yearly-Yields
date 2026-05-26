import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.field import GrowingArea, GrowingAreaType
from app.models.sensor_reading import SensorReading
from app.models.user import User
from app.schemas.data_gap import DataGapRead

router = APIRouter()


@router.get("/", response_model=List[DataGapRead])
async def list_data_gaps(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[DataGapRead]:
    now = datetime.now(timezone.utc)
    gap_cutoff = now - timedelta(days=settings.GAP_THRESHOLD_DAYS)

    result = await db.execute(
        select(GrowingArea).where(
            GrowingArea.owner_id == current_user.id,
            GrowingArea.is_active.is_(True),
            GrowingArea.area_type == GrowingAreaType.open_field,
            GrowingArea.nws_station_id.isnot(None),
        )
    )
    areas = result.scalars().all()

    gaps: List[DataGapRead] = []
    for area in areas:
        if area.gap_acknowledged_at and area.gap_acknowledged_at >= gap_cutoff:
            continue

        last_result = await db.execute(
            select(func.max(SensorReading.read_at)).where(
                SensorReading.growing_area_id == area.id
            )
        )
        last_reading_at = last_result.scalar_one_or_none()

        if last_reading_at is None or last_reading_at < gap_cutoff:
            gap_days = (now - last_reading_at).days if last_reading_at else settings.GAP_THRESHOLD_DAYS
            gaps.append(DataGapRead(
                area_id=area.id,
                area_name=area.name,
                last_reading_at=last_reading_at,
                gap_days=gap_days,
            ))

    return gaps


@router.post("/{area_id}/acknowledge", status_code=status.HTTP_204_NO_CONTENT)
async def acknowledge_data_gap(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(GrowingArea).where(
            GrowingArea.id == area_id,
            GrowingArea.owner_id == current_user.id,
        )
    )
    area = result.scalar_one_or_none()
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Growing area not found")

    area.gap_acknowledged_at = datetime.now(timezone.utc)
    await db.commit()
