import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User, UserRole
from app.schemas.invoice import InvoiceRead, InvoiceUpdate
from app.services.invoice_service import (
    pay_invoice,
    send_invoice,
    update_invoice,
    void_invoice,
)
from app.services.pdf_service import generate_invoice_pdf

router = APIRouter()


async def _get_invoice_or_404(invoice_id: uuid.UUID, db: AsyncSession) -> Invoice:
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


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
    return InvoiceRead.model_validate(await _get_invoice_or_404(invoice_id, db))


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
        customer_id=payload.customer_id,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        notes=payload.notes,
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return InvoiceRead.model_validate(invoice)


@router.post("/{invoice_id}/send", response_model=InvoiceRead)
async def send_invoice_endpoint(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> InvoiceRead:
    invoice = await _get_invoice_or_404(invoice_id, db)
    try:
        invoice = await send_invoice(invoice, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return InvoiceRead.model_validate(invoice)


@router.post("/{invoice_id}/pay", response_model=InvoiceRead)
async def pay_invoice_endpoint(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> InvoiceRead:
    invoice = await _get_invoice_or_404(invoice_id, db)
    try:
        invoice = await pay_invoice(invoice, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return InvoiceRead.model_validate(invoice)


@router.post("/{invoice_id}/void", response_model=InvoiceRead)
async def void_invoice_endpoint(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceRead:
    invoice = await _get_invoice_or_404(invoice_id, db)

    # sent → voided requires owner; draft → voided allows farmer too
    if invoice.status == InvoiceStatus.sent and current_user.role not in (
        UserRole.owner,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an owner can void a sent invoice.",
        )
    if current_user.role not in (UserRole.farmer, UserRole.owner):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    try:
        invoice = await void_invoice(invoice, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return InvoiceRead.model_validate(invoice)


@router.get("/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
) -> Response:
    pdf_bytes = await generate_invoice_pdf(invoice_id, db)
    if pdf_bytes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    filename = f"invoice-{str(invoice_id)[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
