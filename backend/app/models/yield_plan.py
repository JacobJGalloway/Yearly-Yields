import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.field import GrowingArea
    from app.models.crop import CropCycle


class ConfidenceLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class YieldPlan(Base, TimestampMixin):
    """
    Agent-generated planting recommendation for a CropCycle.

    Answers: "How much should I plant to hit my target yield?"
    The agent accounts for historical sensor trends, regional weather,
    and known risk factors (disease pressure, equipment failure, weather variance).

    recommended_plant_quantity is in seeds or transplants count.
    target_yield is in the CropCycle's yield_unit (lbs or bushels).
    reasoning is farmer-readable and includes confidence explanation.

    Only farmer and owner roles can generate yield plans.
    """

    __tablename__ = "yield_plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    growing_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growing_areas.id", ondelete="CASCADE"), nullable=False
    )
    crop_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crop_cycles.id"), nullable=False
    )
    recommended_plant_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    target_yield: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_level: Mapped[ConfidenceLevel] = mapped_column(
        SAEnum(ConfidenceLevel, name="confidencelevel"), nullable=False
    )
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    growing_area: Mapped["GrowingArea"] = relationship(
        "GrowingArea", back_populates="yield_plans", lazy="select"
    )
    crop_cycle: Mapped["CropCycle"] = relationship(
        "CropCycle", back_populates="yield_plans", lazy="select"
    )
