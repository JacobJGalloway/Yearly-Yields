import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, new_uuid

if TYPE_CHECKING:
    from app.models.field import GrowingArea


class WeeklySensorSummary(Base, CreatedAtMixin):
    """
    Weekly aggregate of sensor_readings for a GrowingArea.

    Written once by the end-of-quarter summarization job; never updated thereafter.
    Covers Sunday (week_start) through Saturday (week_end).
    avg_wind_direction is a circular mean (0.0–359.99°) to handle the 0/359 wraparound.
    All nullable columns are null when no readings reported that sensor in the week.
    """

    __tablename__ = "weekly_sensor_summaries"
    __table_args__ = (
        UniqueConstraint("growing_area_id", "week_start", name="uq_weekly_summary_area_week"),
        Index("ix_weekly_summaries_area_week_start", "growing_area_id", "week_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    growing_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growing_areas.id", ondelete="CASCADE"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)       # Sunday
    week_end: Mapped[date] = mapped_column(Date, nullable=False)         # Saturday
    avg_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_humidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_ph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_wind_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_wind_direction: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # degrees, circular mean
    reading_count: Mapped[int] = mapped_column(Integer, nullable=False)

    growing_area: Mapped["GrowingArea"] = relationship(
        "GrowingArea", back_populates="weekly_summaries", lazy="select"
    )
