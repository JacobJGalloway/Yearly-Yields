import uuid
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum as SAEnum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.crop import CropCycle
    from app.models.sensor_reading import SensorReading
    from app.models.historical_summary import HistoricalSummary
    from app.models.alert import Alert
    from app.models.yield_plan import YieldPlan


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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    area_type: Mapped[GrowingAreaType] = mapped_column(
        SAEnum(GrowingAreaType, name="growingareatype"), nullable=False
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    area_acres: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_sqft: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
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
