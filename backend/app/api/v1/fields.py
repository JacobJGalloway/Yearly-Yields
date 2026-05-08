import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.models.field import GrowingArea, GrowingAreaType
from app.models.user import User, UserRole
from app.schemas.field import GrowingAreaCreate, GrowingAreaRead, GrowingAreaUpdate

router = APIRouter()


@router.post("/", response_model=GrowingAreaRead, status_code=status.HTTP_201_CREATED)
async def create_growing_area(
    payload: GrowingAreaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> GrowingAreaRead:
    # Enforce area measurement rules
    if payload.area_type == GrowingAreaType.open_field and payload.area_acres is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="area_acres is required for open_field areas",
        )
    if payload.area_type == GrowingAreaType.dwc_greenhouse and payload.area_sqft is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="area_sqft is required for dwc_greenhouse areas",
        )

    area = GrowingArea(
        owner_id=current_user.id,
        name=payload.name,
        area_type=payload.area_type,
        latitude=payload.latitude,
        longitude=payload.longitude,
        area_acres=payload.area_acres,
        area_sqft=payload.area_sqft,
        nws_station_id=payload.nws_station_id,
        temp_offset_f=payload.temp_offset_f,
        humidity_offset_pct=payload.humidity_offset_pct,
        target_temp_f=payload.target_temp_f,
        target_humidity_pct=payload.target_humidity_pct,
    )
    db.add(area)
    await db.commit()
    await db.refresh(area)
    return GrowingAreaRead.model_validate(area)


@router.get("/", response_model=List[GrowingAreaRead])
async def list_growing_areas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[GrowingAreaRead]:
    result = await db.execute(
        select(GrowingArea).where(GrowingArea.owner_id == current_user.id)
    )
    areas = result.scalars().all()
    return [GrowingAreaRead.model_validate(a) for a in areas]


@router.get("/{area_id}", response_model=GrowingAreaRead)
async def get_growing_area(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GrowingAreaRead:
    result = await db.execute(
        select(GrowingArea).where(
            GrowingArea.id == area_id,
            GrowingArea.owner_id == current_user.id,
        )
    )
    area = result.scalar_one_or_none()
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Growing area not found")
    return GrowingAreaRead.model_validate(area)


@router.patch("/{area_id}", response_model=GrowingAreaRead)
async def update_growing_area(
    area_id: uuid.UUID,
    payload: GrowingAreaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> GrowingAreaRead:
    result = await db.execute(
        select(GrowingArea).where(
            GrowingArea.id == area_id,
            GrowingArea.owner_id == current_user.id,
        )
    )
    area = result.scalar_one_or_none()
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Growing area not found")

    if payload.name is not None:
        area.name = payload.name
    if payload.is_active is not None:
        area.is_active = payload.is_active
    if payload.area_acres is not None:
        area.area_acres = payload.area_acres
    if payload.area_sqft is not None:
        area.area_sqft = payload.area_sqft
    if payload.nws_station_id is not None:
        area.nws_station_id = payload.nws_station_id
    if payload.temp_offset_f is not None:
        area.temp_offset_f = payload.temp_offset_f
    if payload.humidity_offset_pct is not None:
        area.humidity_offset_pct = payload.humidity_offset_pct
    if payload.target_temp_f is not None:
        area.target_temp_f = payload.target_temp_f
    if payload.target_humidity_pct is not None:
        area.target_humidity_pct = payload.target_humidity_pct

    await db.commit()
    await db.refresh(area)
    return GrowingAreaRead.model_validate(area)
