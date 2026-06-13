import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, Float, ForeignKey, String, Text
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
        "Invoice", back_populates="crop_rate", lazy="select"
    )


class Invoice(Base, TimestampMixin):
    """
    A harvest or transplant invoice auto-generated when a CropCycle transitions status.

    unit_price and unit are snapshotted from the active CropRate at creation time so
    historical invoices remain accurate after rate changes. Both are nullable — if no
    active CropRate exists at harvest time, the invoice is created in draft status
    without pricing and the owner fills it in before sending.

    total_amount = quantity × unit_price (stored for query performance).
    customer_id is nullable — null means needs_customer_assignment (no InvoiceConfig
    default was set for this growing area at harvest time).

    Status machine: draft → sent → paid
                    draft → voided
                    sent  → voided (owner only)
    """

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    crop_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crop_cycles.id"), nullable=False
    )
    crop_rate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("crop_rates.id"), nullable=True
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    invoice_type: Mapped[str] = mapped_column(String(20), nullable=False, default="harvest")
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoicestatus"),
        nullable=False,
        default=InvoiceStatus.draft,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[YieldUnit] = mapped_column(
        SAEnum(YieldUnit, name="yieldunit"), nullable=False
    )
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    invoice_date: Mapped[Date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    crop_cycle: Mapped["CropCycle"] = relationship(
        "CropCycle", back_populates="invoices", lazy="select"
    )
    crop_rate: Mapped[Optional["CropRate"]] = relationship(
        "CropRate", back_populates="invoices", lazy="select"
    )
    customer: Mapped[Optional["Customer"]] = relationship(
        "Customer", back_populates="invoices", lazy="select"
    )
