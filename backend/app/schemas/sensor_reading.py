import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.sensor_reading import AssessmentStatus, ReadingSource


class WeeklySummaryRead(BaseModel):
    iso_week: int
    year: int
    week_label: str
    avg_temp_f: Optional[float]
    avg_humidity_pct: Optional[float]
    reading_count: int
    growing_area_id: uuid.UUID


class SensorReadingCreate(BaseModel):
    growing_area_id: uuid.UUID
    crop_cycle_id: Optional[uuid.UUID] = None
    temperature: Optional[float] = Field(None, description="Temperature in °F; null if sensor fault")
    humidity: Optional[float] = Field(None, ge=0.0, le=100.0, description="Relative humidity %; null if sensor fault")
    ph: Optional[float] = Field(None, ge=0.0, le=14.0, description="pH — DWC only, null for open field")
    wind_speed: Optional[float] = Field(None, ge=0.0, description="Wind speed in mph; open field / NWS only")
    wind_direction: Optional[str] = Field(None, max_length=3, description="Compass direction: N/NE/NNE etc.")
    reading_source: ReadingSource
    read_at: datetime


class SensorReadingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    growing_area_id: uuid.UUID
    crop_cycle_id: Optional[uuid.UUID]
    temperature: Optional[float]
    humidity: Optional[float]
    ph: Optional[float]
    wind_speed: Optional[float]
    wind_direction: Optional[str]
    reading_source: ReadingSource
    read_at: datetime
    received_at: datetime
    assessment_status: AssessmentStatus
    assessment_summary: Optional[str]
    created_at: datetime
