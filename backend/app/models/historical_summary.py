import uuid
from typing import TYPE_CHECKING, List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.field import GrowingArea
    from app.models.crop import Crop


class HistoricalSummary(Base, TimestampMixin):
    """
    Weekly aggregated sensor data for a (GrowingArea, Crop, ISO week, year) combination.

    crop_id is NOT NULL. For active cycles, it is the crop being grown. For fallow cycles,
    it is the planned_crop_id from the CropCycle record — so fallow-year data is anchored
    to the intended next crop and remains useful for comparison. If planned_crop_id is not
    yet set on the fallow cycle, summary generation is deferred until it is assigned.

    This design keeps the unique constraint on (growing_area_id, crop_id, week_number, year)
    clean: PostgreSQL treats NULLs as unequal in unique constraints, which would silently
    allow duplicate rows if crop_id were nullable.

    The embedding column stores a pgvector representation for semantic similarity retrieval
    by the anomaly check agent. Exact dimension and embedding strategy are finalized in
    vector_service.py. An IVFFlat ANN index should be added after initial data load
    (requires minimum row count to build effectively — do not add at table creation time).

    All temperature values are in °F; humidity values are percentages (0.0–100.0).
    """

    __tablename__ = "historical_summaries"
    __table_args__ = (
        UniqueConstraint("growing_area_id", "crop_id", "week_number", "year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    growing_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growing_areas.id", ondelete="CASCADE"), nullable=False
    )
    crop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crops.id"), nullable=False
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)  # ISO week 1–53
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    avg_temperature: Mapped[float] = mapped_column(Float, nullable=False)
    min_temperature: Mapped[float] = mapped_column(Float, nullable=False)
    max_temperature: Mapped[float] = mapped_column(Float, nullable=False)

    avg_humidity: Mapped[float] = mapped_column(Float, nullable=False)
    min_humidity: Mapped[float] = mapped_column(Float, nullable=False)
    max_humidity: Mapped[float] = mapped_column(Float, nullable=False)

    reading_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # pgvector embedding — dimension finalized in vector_service.py
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536), nullable=True
    )

    # Relationships
    growing_area: Mapped["GrowingArea"] = relationship(
        "GrowingArea", back_populates="historical_summaries", lazy="select"
    )
    crop: Mapped["Crop"] = relationship(
        "Crop", back_populates="historical_summaries", lazy="select"
    )
