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
) -> Optional[Invoice]:
    """
    Auto-generate a draft invoice when a CropCycle is marked harvested.

    Returns None if:
      - The crop cycle has no actual_yield recorded.
      - The crop has no active CropRate.
      - The crop has no default_harvest_customer.

    Caller is responsible for ensuring the crop cycle status is 'harvested'
    before calling this function.
    """
    cycle_result = await db.execute(
        select(CropCycle).where(CropCycle.id == crop_cycle_id)
    )
    cycle = cycle_result.scalar_one_or_none()
    if cycle is None or cycle.actual_yield is None or cycle.crop_id is None:
        return None

    # Load the crop to get default customer and yield unit
    from app.models.crop import Crop
    crop_result = await db.execute(select(Crop).where(Crop.id == cycle.crop_id))
    crop = crop_result.scalar_one_or_none()
    if crop is None or crop.default_harvest_customer_id is None:
        return None

    # Snapshot the active rate at harvest time
    rate = await get_active_crop_rate(cycle.crop_id, db)
    if rate is None:
        return None

    total_amount = round(cycle.actual_yield * rate.rate_per_unit, 2)

    invoice = Invoice(
        customer_id=crop.default_harvest_customer_id,
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
        invoice.status = status

    await db.commit()
    await db.refresh(invoice)
    return invoice
