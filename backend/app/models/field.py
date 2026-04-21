import uuid
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum as SAEnum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.crop import CropCycle
    from app.models.sensor_reading import SensorReading
    from app.models.historical_summary import HistoricalSummary
    from app.models.alert import Alert
    from app.models.yield_plan import YieldPlan


class PlotType(str, Enum):
    dwc_row = "dwc_row"          # vine crops on trellis/rail (tomatoes, microgreens)
    dwc_box = "dwc_box"          # container/tray crops (lettuce, pineapple, herbs)
    trial_strip = "trial_strip"  # open field variety trial (future)


class GrowingAreaType(str, Enum):
    open_field = "open_field"
    dwc_greenhouse = "dwc_greenhouse"
    # near-future: nft_greenhouse (Nutrient Film Technique — lightweight/leafy crops)
    # future: aeroponic_greenhouse, vertical_farm, home_garden


class GrowingArea(Base, TimestampMixin):
    """
    Represents any agricultural production unit owned by a user.
    Covers open fields and DWC hydroponics greenhouses today;
    extensible to NFT, aeroponic, vertical farm, and home garden types.

    Area measurement:
      open_field  → area_acres (set); area_sqft (null)
      dwc_greenhouse → area_sqft (set); area_acres (null)
    Enforced at service layer on creation.

    Location (lat/lon) is used for NOAA weather grid resolution
    and is compatible with standard tractor GPS hardware.
    """

    __tablename__ = "growing_areas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(25), nullable=False)
    area_type: Mapped[GrowingAreaType] = mapped_column(
        SAEnum(GrowingAreaType, name="growingareatype"), nullable=False
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    area_acres: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_sqft: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nws_station_id: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    temp_offset_f: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    humidity_offset_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_temp_f: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_humidity_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    owner: Mapped["User"] = relationship(
        "User", back_populates="growing_areas", lazy="select"
    )
    crop_cycles: Mapped[List["CropCycle"]] = relationship(
        "CropCycle", back_populates="growing_area", lazy="select"
    )
    sensor_readings: Mapped[List["SensorReading"]] = relationship(
        "SensorReading", back_populates="growing_area", lazy="select"
    )
    historical_summaries: Mapped[List["HistoricalSummary"]] = relationship(
        "HistoricalSummary", back_populates="growing_area", lazy="select"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="growing_area", lazy="select"
    )
    yield_plans: Mapped[List["YieldPlan"]] = relationship(
        "YieldPlan", back_populates="growing_area", lazy="select"
    )
    plots: Mapped[List["GrowingAreaPlot"]] = relationship(
        "GrowingAreaPlot", back_populates="growing_area", lazy="select"
    )


class GrowingAreaPlot(Base, TimestampMixin):
    """
    Optional sub-unit within a GrowingArea for tracking individual rows,
    box sections, or trial strips. Used when staggered seeding patterns
    or per-row crop rotation history is needed.

    plot_type guide:
      dwc_row   → vine crops on trellis/rail; use length_ft
      dwc_box   → container/tray crops (lettuce, pineapple); use area_sqft
      trial_strip → open field variety trial; use length_ft + width_ft
    """

    __tablename__ = "growing_area_plots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    growing_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growing_areas.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(25), nullable=False)
    plot_type: Mapped[PlotType] = mapped_column(
        SAEnum(PlotType, name="plottype"), nullable=False
    )
    length_ft: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width_ft: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_sqft: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    growing_area: Mapped["GrowingArea"] = relationship(
        "GrowingArea", back_populates="plots", lazy="select"
    )
    crop_cycles: Mapped[List["CropCycle"]] = relationship(
        "CropCycle", back_populates="growing_area_plot", lazy="select"
    )
