"""
Invoice service — owns invoice creation and lifecycle.

Responsibilities:
  1. Auto-generate a draft invoice when a CropCycle is marked harvested.
  2. Snapshot the active CropRate at creation time for audit immutability.
  3. Manage invoice status transitions (draft → sent → paid / voided).

Rules:
  - Only farmer and owner roles may create invoices (enforced at endpoint layer).
  - unit_price and unit are copied from the active CropRate — never recalculated.
  - total_amount = quantity × unit_price (stored for query performance).
  - Transplant invoicing (default_transplant_customer) is a deferred feature.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crop import CropCycle
from app.models.invoice import CropRate, Invoice, InvoiceStatus

VALID_INVOICE_TRANSITIONS: dict[InvoiceStatus, set[InvoiceStatus]] = {
    InvoiceStatus.draft: {InvoiceStatus.sent, InvoiceStatus.voided},
    InvoiceStatus.sent: {InvoiceStatus.paid, InvoiceStatus.voided},
    InvoiceStatus.paid: set(),
    InvoiceStatus.voided: set(),
}


def validate_invoice_transition(current: InvoiceStatus, target: InvoiceStatus) -> None:
    allowed = VALID_INVOICE_TRANSITIONS[current]
    if target not in allowed:
        allowed_str = ", ".join(s.value for s in allowed) if allowed else "none (terminal state)"
        raise ValueError(
            f"Cannot transition invoice from '{current.value}' to '{target.value}'. "
            f"Allowed: {allowed_str}."
        )


async def get_active_crop_rate(
    crop_id: uuid.UUID,
    db: AsyncSession,
) -> Optional[CropRate]:
    """Return the currently active rate for a crop, or None if none is set."""
    result = await db.execute(
        select(CropRate).where(
            CropRate.crop_id == crop_id,
            CropRate.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def set_crop_rate(
    crop_id: uuid.UUID,
    rate_per_unit: float,
    unit: str,
    effective_date: date,
    db: AsyncSession,
) -> CropRate:
    """
    Create a new active CropRate and deactivate the previous one.
    Rates are immutable once created — this inserts a new record.
    """
    # Deactivate current active rate if one exists
    result = await db.execute(
        select(CropRate).where(
            CropRate.crop_id == crop_id,
            CropRate.is_active == True,  # noqa: E712
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.is_active = False

    new_rate = CropRate(
        crop_id=crop_id,
        rate_per_unit=rate_per_unit,
        unit=unit,
        is_active=True,
        effective_date=effective_date,
    )
    db.add(new_rate)
    await db.commit()
    await db.refresh(new_rate)
    return new_rate


async def create_draft_invoice(
    crop_cycle_id: uuid.UUID,
    db: AsyncSession,
    use_transplant_customer: bool = False,
) -> Optional[Invoice]:
    """
    Auto-generate a draft invoice when a CropCycle is marked harvested or transplanted.

    use_transplant_customer=True routes the invoice to default_transplant_customer_id
    (e.g. Prairie Start Nursery) instead of default_harvest_customer_id.

    Returns None if:
      - The crop cycle has no actual_yield recorded.
      - The crop has no active CropRate.
      - The crop has no matching default customer for the invoice type.
    """
    cycle_result = await db.execute(
        select(CropCycle).where(CropCycle.id == crop_cycle_id)
    )
    cycle = cycle_result.scalar_one_or_none()
    if cycle is None or cycle.actual_yield is None or cycle.crop_id is None:
        return None

    from app.models.crop import Crop
    crop_result = await db.execute(select(Crop).where(Crop.id == cycle.crop_id))
    crop = crop_result.scalar_one_or_none()

    customer_id = (
        crop.default_transplant_customer_id if use_transplant_customer
        else crop.default_harvest_customer_id
    )
    if crop is None or customer_id is None:
        return None

    # Snapshot the active rate at harvest time
    rate = await get_active_crop_rate(cycle.crop_id, db)
    if rate is None:
        return None

    total_amount = round(cycle.actual_yield * rate.rate_per_unit, 2)

    invoice = Invoice(
        customer_id=customer_id,
        crop_cycle_id=crop_cycle_id,
        rate_id=rate.id,
        quantity=cycle.actual_yield,
        unit=cycle.yield_unit,
        unit_price=rate.rate_per_unit,
        total_amount=total_amount,
        status=InvoiceStatus.draft,
        invoice_date=date.today(),
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def update_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession,
    quantity: Optional[float] = None,
    notes: Optional[str] = None,
    status: Optional[InvoiceStatus] = None,
) -> Optional[Invoice]:
    """
    Update a draft invoice. Farmers can adjust quantity and notes before sending.
    Recalculates total_amount if quantity changes.
    """
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if invoice is None:
        return None

    if quantity is not None:
        invoice.quantity = quantity
        invoice.total_amount = round(quantity * invoice.unit_price, 2)

    if notes is not None:
        invoice.notes = notes

    if status is not None:
        validate_invoice_transition(invoice.status, status)
        invoice.status = status

    await db.commit()
    await db.refresh(invoice)
    return invoice
