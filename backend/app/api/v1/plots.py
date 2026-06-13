import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.models.field import GrowingArea, GrowingAreaPlot
from app.models.user import User, UserRole
from app.schemas.plot import GrowingAreaPlotCreate, GrowingAreaPlotRead, GrowingAreaPlotUpdate

router = APIRouter()


async def _get_area_or_404(area_id: uuid.UUID, user: User, db: AsyncSession) -> GrowingArea:
    result = await db.execute(
        select(GrowingArea).where(
            GrowingArea.id == area_id,
            GrowingArea.owner_id == user.id,
        )
    )
    area = result.scalar_one_or_none()
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Growing area not found")
    return area


@router.post(
    "/",
    response_model=GrowingAreaPlotRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_plot(
    area_id: uuid.UUID,
    payload: GrowingAreaPlotCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> GrowingAreaPlotRead:
    await _get_area_or_404(area_id, current_user, db)

    if payload.plot_index == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="plot_index 0 is reserved for the open-field sentinel and cannot be assigned manually.",
        )

    plot = GrowingAreaPlot(
        growing_area_id=area_id,
        owner_id=current_user.id,
        plot_index=payload.plot_index,
        name=payload.name,
        plot_type=payload.plot_type,
        harvest_weekdays=payload.harvest_weekdays,
        length_ft=payload.length_ft,
        width_ft=payload.width_ft,
        area_sqft=payload.area_sqft,
        notes=payload.notes,
    )
    db.add(plot)
    await db.commit()
    await db.refresh(plot)
    return GrowingAreaPlotRead.model_validate(plot)


@router.get("/", response_model=List[GrowingAreaPlotRead])
async def list_plots(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[GrowingAreaPlotRead]:
    await _get_area_or_404(area_id, current_user, db)

    result = await db.execute(
        select(GrowingAreaPlot).where(GrowingAreaPlot.growing_area_id == area_id)
    )
    return [GrowingAreaPlotRead.model_validate(p) for p in result.scalars().all()]


@router.get("/{plot_id}", response_model=GrowingAreaPlotRead)
async def get_plot(
    area_id: uuid.UUID,
    plot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GrowingAreaPlotRead:
    await _get_area_or_404(area_id, current_user, db)

    result = await db.execute(
        select(GrowingAreaPlot).where(
            GrowingAreaPlot.id == plot_id,
            GrowingAreaPlot.growing_area_id == area_id,
        )
    )
    plot = result.scalar_one_or_none()
    if plot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot not found")
    return GrowingAreaPlotRead.model_validate(plot)


@router.patch("/{plot_id}", response_model=GrowingAreaPlotRead)
async def update_plot(
    area_id: uuid.UUID,
    plot_id: uuid.UUID,
    payload: GrowingAreaPlotUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> GrowingAreaPlotRead:
    await _get_area_or_404(area_id, current_user, db)

    result = await db.execute(
        select(GrowingAreaPlot).where(
            GrowingAreaPlot.id == plot_id,
            GrowingAreaPlot.growing_area_id == area_id,
        )
    )
    plot = result.scalar_one_or_none()
    if plot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plot, field, value)

    await db.commit()
    await db.refresh(plot)
    return GrowingAreaPlotRead.model_validate(plot)
