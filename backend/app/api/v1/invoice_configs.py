import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_role
from app.models.field import GrowingArea
from app.models.invoice_config import InvoiceConfig
from app.models.user import User, UserRole
from app.schemas.invoice import InvoiceConfigRead, InvoiceConfigUpdate

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


@router.get("/{growing_area_id}", response_model=InvoiceConfigRead)
async def get_invoice_config(
    growing_area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> InvoiceConfigRead:
    await _get_area_or_404(growing_area_id, current_user, db)

    result = await db.execute(
        select(InvoiceConfig).where(InvoiceConfig.growing_area_id == growing_area_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No invoice config found for this growing area.",
        )
    return InvoiceConfigRead.model_validate(config)


@router.patch("/{growing_area_id}", response_model=InvoiceConfigRead)
async def update_invoice_config(
    growing_area_id: uuid.UUID,
    payload: InvoiceConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> InvoiceConfigRead:
    await _get_area_or_404(growing_area_id, current_user, db)

    result = await db.execute(
        select(InvoiceConfig).where(InvoiceConfig.growing_area_id == growing_area_id)
    )
    config = result.scalar_one_or_none()

    if config is None:
        # Upsert: create if missing (area exists but was never seeded with a config)
        config = InvoiceConfig(growing_area_id=growing_area_id)
        db.add(config)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)
    return InvoiceConfigRead.model_validate(config)
