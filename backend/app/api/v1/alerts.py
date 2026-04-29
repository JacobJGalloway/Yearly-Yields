import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.alert import Alert, AlertStatus
from app.models.user import User
from app.schemas.alert import AlertRead, AlertUpdate

router = APIRouter()


@router.get("/", response_model=List[AlertRead])
async def list_alerts(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AlertRead]:
    query = select(Alert).where(
        Alert.growing_area.has(owner_id=current_user.id)
    )
    if active_only:
        query = query.where(Alert.status == AlertStatus.active)

    result = await db.execute(query)
    alerts = result.scalars().all()
    return [AlertRead.model_validate(a) for a in alerts]


@router.get("/{alert_id}", response_model=AlertRead)
async def get_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertRead:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return AlertRead.model_validate(alert)


@router.patch("/{alert_id}", response_model=AlertRead)
async def update_alert(
    alert_id: uuid.UUID,
    payload: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertRead:
    result = await db.execute(
        select(Alert).join(Alert.growing_area).where(
            Alert.id == alert_id,
            Alert.growing_area.has(owner_id=current_user.id),
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    if payload.status is not None:
        if alert.status == AlertStatus.resolved:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Alert is already resolved.",
            )
        if payload.status != AlertStatus.resolved:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Manual status update only supports transitioning to 'resolved'.",
            )
        alert.status = AlertStatus.resolved
        alert.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(alert)
    return AlertRead.model_validate(alert)
