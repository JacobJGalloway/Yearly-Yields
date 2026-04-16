import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.models.invoice import Invoice
from app.models.user import User, UserRole
from app.schemas.invoice import InvoiceRead, InvoiceUpdate
from app.services.invoice_service import update_invoice

router = APIRouter()


@router.get("/", response_model=List[InvoiceRead])
async def list_invoices(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> List[InvoiceRead]:
    result = await db.execute(select(Invoice))
    return [InvoiceRead.model_validate(i) for i in result.scalars().all()]


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> InvoiceRead:
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return InvoiceRead.model_validate(invoice)


@router.patch("/{invoice_id}", response_model=InvoiceRead)
async def update_invoice_endpoint(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> InvoiceRead:
    invoice = await update_invoice(
        invoice_id=invoice_id,
        db=db,
        quantity=payload.quantity,
        notes=payload.notes,
        status=payload.status,
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return InvoiceRead.model_validate(invoice)
