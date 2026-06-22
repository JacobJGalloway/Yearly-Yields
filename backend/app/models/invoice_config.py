import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.field import GrowingArea
    from app.models.customer import Customer


class InvoiceConfig(Base, TimestampMixin):
    """
    Default customer assignments for draft invoice auto-generation per growing area.

    One row per GrowingArea. Both customer fields are nullable — if unset, the invoice
    is created without a customer (customer_id=None) and the owner assigns one manually
    before sending.

    Updated via PATCH /api/v1/invoice-configs/{growing_area_id}.
    Seeded alongside growing areas in POST /api/v1/admin/seed.
    """

    __tablename__ = "invoice_configs"
    __table_args__ = (UniqueConstraint("growing_area_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    growing_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growing_areas.id", ondelete="CASCADE"), nullable=False
    )
    harvest_customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    transplant_customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    growing_area: Mapped["GrowingArea"] = relationship(
        "GrowingArea", back_populates="invoice_config", lazy="select"
    )
    harvest_customer: Mapped[Optional["Customer"]] = relationship(
        "Customer", foreign_keys=[harvest_customer_id], lazy="select"
    )
    transplant_customer: Mapped[Optional["Customer"]] = relationship(
        "Customer", foreign_keys=[transplant_customer_id], lazy="select"
    )
