import uuid
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.field import GrowingArea
    from app.models.customer import Customer


class UserRole(str, Enum):
    owner = "owner"       # full control — bypasses all permission checks
    farmer = "farmer"     # operational + financial access
    hired_hand = "hired_hand"  # physical work only (seeding/harvesting); no financial access


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole"), nullable=False, default=UserRole.farmer
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    growing_areas: Mapped[List["GrowingArea"]] = relationship(
        "GrowingArea", back_populates="owner", lazy="select"
    )
    customers: Mapped[List["Customer"]] = relationship(
        "Customer", back_populates="owner", lazy="select"
    )


class Permission(Base, CreatedAtMixin):
    """
    Named permission keys seeded at startup.
    Seeded values:
      areas:read, areas:write
      crops:read, crops:write
      sensor_readings:read, sensor_readings:create
      alerts:read, alerts:manage
      yield_plans:read, yield_plans:create
      invoices:read, invoices:create, invoices:manage
      customers:read, customers:manage
      users:manage
      owner:all  (wildcard — owner role bypasses all checks)
    """

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    role_permissions: Mapped[List["RolePermission"]] = relationship(
        "RolePermission", back_populates="permission", lazy="select"
    )


class RolePermission(Base, CreatedAtMixin):
    """
    Maps a UserRole enum value to a Permission.
    Seeded role assignments:
      owner      → owner:all
      farmer     → areas:read, crops:read, crops:write, sensor_readings:read,
                   sensor_readings:create, alerts:read, yield_plans:read,
                   yield_plans:create, invoices:read, invoices:create, customers:read
      hired_hand → areas:read, crops:write
    """

    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role", "permission_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole"), nullable=False
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id"), nullable=False
    )

    # Relationships
    permission: Mapped["Permission"] = relationship(
        "Permission", back_populates="role_permissions", lazy="select"
    )
