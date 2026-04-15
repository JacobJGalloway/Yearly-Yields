import uuid
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, Enum as SAEnum, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin, new_uuid
from app.models.crop import YieldUnit

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.crop import Crop, CropCycle


class InvoiceStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    paid = "paid"
    voided = "voided"


class CropRate(Base, CreatedAtMixin):
    """
    The price per unit for a crop at a given point in time.

    Only one record per crop should have is_active=True at any time.
    The service layer deactivates the previous active rate before inserting a new one.
    Old rates are retained (not deleted) so historical invoices remain accurate.

    Rates are immutable once created (no updated_at). To change a rate, insert a new
    record and deactivate the old one.
    """

    __tablename__ = "crop_rates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    crop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crops.id"), nullable=False
    )
    rate_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[YieldUnit] = mapped_column(
        SAEnum(YieldUnit, name="yieldunit"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_date: Mapped[Date] = mapped_column(Date, nullable=False)

    # Relationships
    crop: Mapped["Crop"] = relationship(
        "Crop", back_populates="rates", lazy="select"
    )
    invoices: Mapped[List["Invoice"]] = relationship(
        "Invoice", back_populates="rate", lazy="select"
    )


class Invoice(Base, TimestampMixin):
    """
    A harvest invoice auto-generated when a CropCycle is marked harvested.

    unit_price and unit are copied from the active CropRate at creation time so
    historical invoices remain accurate after rate changes.

    total_amount = quantity × unit_price (stored for query performance; recompute
    is not needed but quantity × unit_price should always equal it).

    Workflow:
      1. CropCycle status → harvested, actual_yield set.
      2. Service creates Invoice(status=draft) using crop's default_harvest_customer
         and the currently active CropRate. quantity defaults to actual_yield.
      3. Farmer (or owner) reviews draft, adjusts quantity if needed, then sends.

    Only farmer and owner roles can create invoices (hired_hand cannot).
    Transplant invoicing (using default_transplant_customer) is a deferred feature.
    """

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id"), nullable=False
    )
    crop_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crop_cycles.id"), nullable=False
    )
    rate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crop_rates.id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[YieldUnit] = mapped_column(
        SAEnum(YieldUnit, name="yieldunit"), nullable=False
    )
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoicestatus"),
        nullable=False,
        default=InvoiceStatus.draft,
    )
    invoice_date: Mapped[Date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer", back_populates="invoices", lazy="select"
    )
    crop_cycle: Mapped["CropCycle"] = relationship(
        "CropCycle", back_populates="invoices", lazy="select"
    )
    rate: Mapped["CropRate"] = relationship(
        "CropRate", back_populates="invoices", lazy="select"
    )
