import uuid
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.field import GrowingArea, GrowingAreaPlot
    from app.models.customer import Customer
    from app.models.sensor_reading import SensorReading
    from app.models.historical_summary import HistoricalSummary
    from app.models.alert import Alert
    from app.models.yield_plan import YieldPlan
    from app.models.invoice import CropRate, Invoice


class YieldUnit(str, Enum):
    lbs = "lbs"         # tomatoes, arugula lettuce
    bushels = "bushels"  # corn, soybeans (US commodity standard)


class CropCycleStatus(str, Enum):
    active = "active"
    harvested = "harvested"
    transplanted = "transplanted"
    abandoned = "abandoned"
    fallow = "fallow"


class Crop(Base, CreatedAtMixin):
    """
    Lookup/reference table for crop types. Seeded at startup; not modified at runtime.

    Seed data (seeded after customers):
      name             | greenhouse_compatible | typical_cycle_days | harvest_customer    | transplant_customer
      corn             | False                 | 120                | Global Harvest      | —
      soybeans         | False                 | 100                | Global Harvest      | —
      tomatoes         | True                  | 90                 | National Nourish    | Prairie Start Nursery
      arugula_lettuce  | True                  | 40                 | National Nourish    | Prairie Start Nursery

    Compatibility rule (enforced at service layer):
      open_field areas accept any crop (all 4).
      dwc_greenhouse areas only accept greenhouse_compatible=True crops (tomatoes, arugula_lettuce).
    """

    __tablename__ = "crops"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    greenhouse_compatible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    typical_cycle_days: Mapped[int] = mapped_column(Integer, nullable=False)
    default_harvest_customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    default_transplant_customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )

    # Relationships
    default_harvest_customer: Mapped[Optional["Customer"]] = relationship(
        "Customer",
        foreign_keys=[default_harvest_customer_id],
        lazy="select",
    )
    default_transplant_customer: Mapped[Optional["Customer"]] = relationship(
        "Customer",
        foreign_keys=[default_transplant_customer_id],
        lazy="select",
    )
    crop_cycles: Mapped[List["CropCycle"]] = relationship(
        "CropCycle",
        back_populates="crop",
        foreign_keys="CropCycle.crop_id",
        lazy="select",
    )
    historical_summaries: Mapped[List["HistoricalSummary"]] = relationship(
        "HistoricalSummary", back_populates="crop", lazy="select"
    )
    rates: Mapped[List["CropRate"]] = relationship(
        "CropRate", back_populates="crop", lazy="select"
    )


class CropCycle(Base, TimestampMixin):
    """
    One row per growing cycle or fallow period for a GrowingArea.

    Arugula lettuce can produce 8+ cycles/year; tomatoes 2-3/year.
    cycle_number is 1-based within (growing_area, season_year).

    Fallow invariant (enforced at service layer):
      status=fallow  → crop_id IS NULL; planned_crop_id MAY be set
      status!=fallow → crop_id IS NOT NULL; planned_crop_id IS NULL

    Fallow duration:
      harvested_at is auto-set to planted_at + planned_crop.typical_cycle_days.
      If planned_crop_id is null at creation, harvested_at is left null and
      recalculated when planned_crop_id is assigned.

    Yield units are derived from the crop at cycle creation and stored explicitly
    so historical records remain accurate if crop data is updated.
    """

    __tablename__ = "crop_cycles"
    __table_args__ = (
        UniqueConstraint("growing_area_id", "season_year", "cycle_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    growing_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growing_areas.id", ondelete="CASCADE"), nullable=False
    )
    growing_area_plot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growing_area_plots.id", ondelete="RESTRICT"), nullable=False
    )
    crop_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("crops.id"), nullable=True
    )
    planned_crop_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("crops.id"), nullable=True
    )
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    planted_at: Mapped[Date] = mapped_column(Date, nullable=False)
    harvested_at: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    forecasted_end_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    yield_unit: Mapped[YieldUnit] = mapped_column(
        SAEnum(YieldUnit, name="yieldunit"), nullable=False
    )
    target_yield: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_yield: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[CropCycleStatus] = mapped_column(
        SAEnum(CropCycleStatus, name="cropcyclestatus"),
        nullable=False,
        default=CropCycleStatus.active,
    )

    # Relationships
    growing_area: Mapped["GrowingArea"] = relationship(
        "GrowingArea", back_populates="crop_cycles", lazy="select"
    )
    growing_area_plot: Mapped["GrowingAreaPlot"] = relationship(
        "GrowingAreaPlot", back_populates="crop_cycles", lazy="select"
    )
    crop: Mapped[Optional["Crop"]] = relationship(
        "Crop",
        back_populates="crop_cycles",
        foreign_keys=[crop_id],
        lazy="select",
    )
    planned_crop: Mapped[Optional["Crop"]] = relationship(
        "Crop",
        foreign_keys=[planned_crop_id],
        lazy="select",
    )
    sensor_readings: Mapped[List["SensorReading"]] = relationship(
        "SensorReading", back_populates="crop_cycle", lazy="select"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="crop_cycle", lazy="select"
    )
    yield_plans: Mapped[List["YieldPlan"]] = relationship(
        "YieldPlan", back_populates="crop_cycle", lazy="select"
    )
    invoices: Mapped[List["Invoice"]] = relationship(
        "Invoice", back_populates="crop_cycle", lazy="select"
    )
