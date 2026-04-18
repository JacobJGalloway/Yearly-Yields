import uuid
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, new_uuid

if TYPE_CHECKING:
    from app.models.field import GrowingArea
    from app.models.crop import CropCycle
    from app.models.alert import Alert


class ReadingSource(str, Enum):
    nws = "nws"         # NWS CO-OP station observations (api.weather.gov + NOAA CDO backfill)
    manual = "manual"   # farmer manual entry via the fallback form
    fiot = "fiot"       # fake IoT — simulated sensor data for dev/demo (greenhouse effect simulation)
    sensor = "sensor"   # real IoT device POST (future; not yet deployed)


class AssessmentStatus(str, Enum):
    pending = "pending"       # received; agent not yet triggered
    processing = "processing"  # agent loop currently running
    normal = "normal"          # assessed; within historical variance
    anomalous = "anomalous"    # assessed; outside historical variance — alert may be active
    error = "error"            # agent loop failed; requires manual review


class SensorReading(Base, CreatedAtMixin):
    """
    An individual temperature + humidity observation for a GrowingArea.

    Readings are immutable once created (no updated_at). The agent writes
    assessment_summary and updates assessment_status via the
    log_reading_assessment tool as its final action on every run.

    read_at   = when the observation was taken (sensor clock or NOAA obs time)
    received_at = when this server ingested it (may differ for batched/delayed posts)

    Primary query pattern: (growing_area_id, read_at DESC) — covered by index below.
    """

    __tablename__ = "sensor_readings"
    __table_args__ = (
        Index("ix_sensor_readings_area_read_at", "growing_area_id", "read_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    growing_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growing_areas.id", ondelete="CASCADE"), nullable=False
    )
    crop_cycle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("crop_cycles.id"), nullable=True
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False)       # °F
    humidity: Mapped[float] = mapped_column(Float, nullable=False)         # % (0.0–100.0)
    ph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)      # DWC only; null for open field
    reading_source: Mapped[ReadingSource] = mapped_column(
        SAEnum(ReadingSource, name="readingsource"), nullable=False
    )
    read_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    assessment_status: Mapped[AssessmentStatus] = mapped_column(
        SAEnum(AssessmentStatus, name="assessmentstatus"),
        nullable=False,
        default=AssessmentStatus.pending,
    )
    assessment_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    growing_area: Mapped["GrowingArea"] = relationship(
        "GrowingArea", back_populates="sensor_readings", lazy="select"
    )
    crop_cycle: Mapped[Optional["CropCycle"]] = relationship(
        "CropCycle", back_populates="sensor_readings", lazy="select"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="triggering_reading", lazy="select"
    )
