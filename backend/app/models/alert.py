import uuid
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.field import GrowingArea, GrowingAreaPlot
    from app.models.crop import CropCycle
    from app.models.sensor_reading import SensorReading


class AlertType(str, Enum):
    temperature_high = "temperature_high"
    temperature_low = "temperature_low"
    humidity_high = "humidity_high"
    humidity_low = "humidity_low"
    combined = "combined"


class AlertStatus(str, Enum):
    active = "active"
    resolved = "resolved"


class Alert(Base, TimestampMixin):
    """
    Tracks an active anomaly condition for a GrowingArea.

    State machine: active → resolved when consecutive_normal_count reaches 3.

    Agent behavior (see ANOMALY_CHECK_SYSTEM_PROMPT in prompts.py):
      - On each sensor reading, agent calls get_active_alert to find an open alert.
      - If reading is normal: increment consecutive_normal_count.
        If consecutive_normal_count == 3: set status=resolved, resolved_at=now.
      - If reading is anomalous: reset consecutive_normal_count to 0.
      - Email is sent on alert creation, then again only if more than
        ALERT_EMAIL_INTERVAL_HOURS hours have passed since last_email_sent_at.
        ALERT_EMAIL_INTERVAL_HOURS is configured in settings (default 24, min 4, max 72).

    The index on (growing_area_id, status) covers the agent's primary lookup:
    "is there an active alert for this growing area?"
    """

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_area_status", "growing_area_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    growing_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growing_areas.id", ondelete="CASCADE"), nullable=False
    )
    growing_area_plot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growing_area_plots.id", ondelete="RESTRICT"), nullable=False
    )
    crop_cycle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("crop_cycles.id"), nullable=True
    )
    triggering_reading_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sensor_readings.id"), nullable=True
    )
    alert_type: Mapped[AlertType] = mapped_column(
        SAEnum(AlertType, name="alerttype"), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        SAEnum(AlertStatus, name="alertstatus"),
        nullable=False,
        default=AlertStatus.active,
    )
    consecutive_normal_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_email_sent_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    assessment_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    growing_area: Mapped["GrowingArea"] = relationship(
        "GrowingArea", back_populates="alerts", lazy="select"
    )
    growing_area_plot: Mapped["GrowingAreaPlot"] = relationship(
        "GrowingAreaPlot", back_populates="alerts", lazy="select"
    )
    crop_cycle: Mapped[Optional["CropCycle"]] = relationship(
        "CropCycle", back_populates="alerts", lazy="select"
    )
    triggering_reading: Mapped[Optional["SensorReading"]] = relationship(
        "SensorReading", back_populates="alerts", lazy="select"
    )
