import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.yield_plan import YieldPlan
from app.schemas.yield_plan import YieldPlanRead

router = APIRouter()


@router.get("/", response_model=List[YieldPlanRead])
async def list_yield_plans(
    crop_cycle_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[YieldPlanRead]:
    query = select(YieldPlan).join(YieldPlan.growing_area).where(
        YieldPlan.growing_area.has(owner_id=current_user.id)
    )
    if crop_cycle_id is not None:
        query = query.where(YieldPlan.crop_cycle_id == crop_cycle_id)

    result = await db.execute(query)
    plans = result.scalars().all()
    return [YieldPlanRead.model_validate(p) for p in plans]


@router.get("/{plan_id}", response_model=YieldPlanRead)
async def get_yield_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> YieldPlanRead:
    result = await db.execute(select(YieldPlan).where(YieldPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Yield plan not found")
    return YieldPlanRead.model_validate(plan)
