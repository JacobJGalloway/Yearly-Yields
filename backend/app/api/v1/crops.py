import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.models.crop import Crop, CropCycle, CropCycleStatus
from app.models.field import GrowingAreaType
from app.models.user import User, UserRole
from app.schemas.crop import CropCycleCreate, CropCycleRead, CropCycleUpdate, CropRead
from app.services.invoice_service import create_draft_invoice

router = APIRouter()


@router.get("/", response_model=List[CropRead])
async def list_crops(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> List[CropRead]:
    result = await db.execute(select(Crop))
    return [CropRead.model_validate(c) for c in result.scalars().all()]


@router.post("/cycles", response_model=CropCycleRead, status_code=status.HTTP_201_CREATED)
async def create_crop_cycle(
    payload: CropCycleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> CropCycleRead:
    # Enforce greenhouse crop compatibility
    if payload.crop_id is not None:
        from app.models.field import GrowingArea
        area_result = await db.execute(
            select(GrowingArea).where(GrowingArea.id == payload.growing_area_id)
        )
        area = area_result.scalar_one_or_none()
        if area is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Growing area not found")

        crop_result = await db.execute(select(Crop).where(Crop.id == payload.crop_id))
        crop = crop_result.scalar_one_or_none()
        if crop is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop not found")

        if area.area_type == GrowingAreaType.dwc_greenhouse and not crop.greenhouse_compatible:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{crop.name} is not compatible with dwc_greenhouse areas",
            )

    cycle = CropCycle(
        growing_area_id=payload.growing_area_id,
        crop_id=payload.crop_id,
        planned_crop_id=payload.planned_crop_id,
        season_year=payload.season_year,
        cycle_number=payload.cycle_number,
        planted_at=payload.planted_at,
        yield_unit=payload.yield_unit,
        target_yield=payload.target_yield,
    )
    db.add(cycle)
    await db.commit()
    await db.refresh(cycle)
    return CropCycleRead.model_validate(cycle)


@router.get("/cycles/{cycle_id}", response_model=CropCycleRead)
async def get_crop_cycle(
    cycle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CropCycleRead:
    result = await db.execute(select(CropCycle).where(CropCycle.id == cycle_id))
    cycle = result.scalar_one_or_none()
    if cycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")
    return CropCycleRead.model_validate(cycle)


@router.patch("/cycles/{cycle_id}", response_model=CropCycleRead)
async def update_crop_cycle(
    cycle_id: uuid.UUID,
    payload: CropCycleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> CropCycleRead:
    result = await db.execute(select(CropCycle).where(CropCycle.id == cycle_id))
    cycle = result.scalar_one_or_none()
    if cycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")

    if payload.status is not None:
        cycle.status = payload.status
    if payload.actual_yield is not None:
        cycle.actual_yield = payload.actual_yield
    if payload.harvested_at is not None:
        cycle.harvested_at = payload.harvested_at
    if payload.target_yield is not None:
        cycle.target_yield = payload.target_yield
    if payload.planned_crop_id is not None:
        cycle.planned_crop_id = payload.planned_crop_id

    await db.commit()
    await db.refresh(cycle)

    # Auto-generate draft invoice on harvest
    if payload.status == CropCycleStatus.harvested:
        await create_draft_invoice(cycle.id, db)

    return CropCycleRead.model_validate(cycle)
