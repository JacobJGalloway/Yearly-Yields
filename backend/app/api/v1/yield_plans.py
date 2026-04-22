import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.models.crop import CropCycle, CropCycleStatus
from app.models.field import GrowingArea
from app.models.user import User, UserRole
from app.models.yield_plan import YieldPlan
from app.schemas.yield_plan import YieldPlanCreate, YieldPlanRead
from app.services.yield_service import generate_yield_plan

router = APIRouter()


@router.post("/", response_model=YieldPlanRead, status_code=status.HTTP_201_CREATED)
async def create_yield_plan(
    payload: YieldPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> YieldPlanRead:
    cycle_result = await db.execute(
        select(CropCycle)
        .join(CropCycle.growing_area)
        .where(
            CropCycle.id == payload.crop_cycle_id,
            GrowingArea.owner_id == current_user.id,
        )
    )
    cycle = cycle_result.scalar_one_or_none()
    if cycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")

    if cycle.status != CropCycleStatus.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Yield plans can only be generated for active cycles (current status: {cycle.status.value}).",
        )

    if cycle.crop_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Crop cycle has no crop assigned.",
        )

    plan = await generate_yield_plan(payload.crop_cycle_id, payload.target_yield, db)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Yield plan agent did not return a result.",
        )

    return YieldPlanRead.model_validate(plan)


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
