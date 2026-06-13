"""
Invoice service — owns invoice creation and lifecycle.

Responsibilities:
  1. Auto-generate a draft invoice when a CropCycle is marked harvested/transplanted.
  2. Look up InvoiceConfig by growing_area_id for the default customer assignment.
  3. Snapshot the active CropRate at creation time for audit immutability.
  4. Manage invoice status transitions with timestamp tracking.

Rules:
  - Only farmer and owner roles may create invoices (enforced at endpoint layer).
  - unit_price and unit are snapshotted from the active CropRate — never recalculated after creation.
  - total_amount = quantity × unit_price (stored for query performance; null if no rate at creation time).
  - Customer is resolved from InvoiceConfig per growing area, not from Crop.default_*_customer_id.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crop import Crop, CropCycle
from app.models.field import GrowingArea
from app.models.invoice import CropRate, Invoice, InvoiceStatus
from app.models.invoice_config import InvoiceConfig

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


async def generate_draft(
    crop_cycle_id: uuid.UUID,
    db: AsyncSession,
    invoice_type: str = "harvest",
) -> Optional[Invoice]:
    """
    Auto-generate a draft invoice when a CropCycle transitions to harvested or transplanted.

    Customer is resolved from InvoiceConfig for the cycle's growing_area — not from
    Crop.default_*_customer_id. If no InvoiceConfig exists or no customer is configured,
    the invoice is created with customer_id=None (owner assigns manually before sending).

    If no active CropRate exists for the crop, unit_price and total_amount are null
    (owner fills in pricing before sending).

    Returns None only if the cycle has no actual_yield or no crop assigned.
    """
    cycle_result = await db.execute(select(CropCycle).where(CropCycle.id == crop_cycle_id))
    cycle = cycle_result.scalar_one_or_none()
    if cycle is None or cycle.actual_yield is None or cycle.crop_id is None:
        return None

    # Resolve customer from InvoiceConfig for this growing area
    config_result = await db.execute(
        select(InvoiceConfig).where(InvoiceConfig.growing_area_id == cycle.growing_area_id)
    )
    config = config_result.scalar_one_or_none()
    customer_id = None
    if config:
        customer_id = (
            config.transplant_customer_id
            if invoice_type == "transplant"
            else config.harvest_customer_id
        )

    # Build description from crop + growing area names
    crop_result = await db.execute(select(Crop).where(Crop.id == cycle.crop_id))
    crop = crop_result.scalar_one_or_none()

    area_result = await db.execute(select(GrowingArea).where(GrowingArea.id == cycle.growing_area_id))
    area = area_result.scalar_one_or_none()

    crop_name = crop.name if crop else "Unknown crop"
    area_name = area.name if area else "Unknown area"
    description = f"{crop_name} — {area_name} {invoice_type}"

    # Snapshot active CropRate (nullable — no rate = no pricing at draft time)
    rate = await get_active_crop_rate(cycle.crop_id, db)
    unit_price = rate.rate_per_unit if rate else None
    total_amount = round(cycle.actual_yield * rate.rate_per_unit, 2) if rate else None

    invoice = Invoice(
        crop_cycle_id=crop_cycle_id,
        crop_rate_id=rate.id if rate else None,
        customer_id=customer_id,
        invoice_type=invoice_type,
        status=InvoiceStatus.draft,
        description=description,
        quantity=cycle.actual_yield,
        unit=cycle.yield_unit,
        unit_price=unit_price,
        total_amount=total_amount,
        invoice_date=date.today(),
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def send_invoice(invoice: Invoice, db: AsyncSession) -> Invoice:
    """Transition draft → sent and record sent_at timestamp."""
    validate_invoice_transition(invoice.status, InvoiceStatus.sent)
    invoice.status = InvoiceStatus.sent
    invoice.sent_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def pay_invoice(invoice: Invoice, db: AsyncSession) -> Invoice:
    """Transition sent → paid and record paid_at timestamp."""
    validate_invoice_transition(invoice.status, InvoiceStatus.paid)
    invoice.status = InvoiceStatus.paid
    invoice.paid_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def void_invoice(invoice: Invoice, db: AsyncSession) -> Invoice:
    """Transition draft/sent → voided and record voided_at timestamp."""
    validate_invoice_transition(invoice.status, InvoiceStatus.voided)
    invoice.status = InvoiceStatus.voided
    invoice.voided_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def update_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession,
    customer_id: Optional[uuid.UUID] = None,
    quantity: Optional[float] = None,
    notes: Optional[str] = None,
) -> Optional[Invoice]:
    """
    Update a draft invoice. Farmers can reassign the customer, adjust quantity, and edit notes.
    Recalculates total_amount if quantity changes and unit_price is set.
    """
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if invoice is None:
        return None

    if customer_id is not None:
        invoice.customer_id = customer_id

    if quantity is not None:
        invoice.quantity = quantity
        if invoice.unit_price is not None:
            invoice.total_amount = round(quantity * invoice.unit_price, 2)

    if notes is not None:
        invoice.notes = notes

    await db.commit()
    await db.refresh(invoice)
    return invoice
