import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.invoice import Invoice


class Customer(Base, TimestampMixin):
    """
    A business or individual that purchases crop output from the farm.

    Seeded customers (created before crop seed data):
      - "Global Harvest"    → default harvest buyer for corn and soybeans
      - "National Nourish"  → default harvest buyer for tomatoes and arugula lettuce
      - "Acme Farms"        → default transplant buyer for tomatoes and arugula lettuce
                              (transplant invoicing is a deferred feature)
    """

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    owner: Mapped["User"] = relationship(
        "User", back_populates="customers", lazy="select"
    )
    invoices: Mapped[List["Invoice"]] = relationship(
        "Invoice", back_populates="customer", lazy="select"
    )
