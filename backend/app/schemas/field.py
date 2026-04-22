import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.field import GrowingAreaType


class GrowingAreaCreate(BaseModel):
    name: str = Field(..., max_length=25)
    area_type: GrowingAreaType
    latitude: float
    longitude: float
    area_acres: Optional[float] = None
    area_sqft: Optional[float] = None
    nws_station_id: Optional[str] = None
    temp_offset_f: Optional[float] = None
    humidity_offset_pct: Optional[float] = None
    target_temp_f: Optional[float] = None
    target_humidity_pct: Optional[float] = None


class GrowingAreaUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=25)
    is_active: Optional[bool] = None
    area_acres: Optional[float] = None
    area_sqft: Optional[float] = None
    nws_station_id: Optional[str] = None
    temp_offset_f: Optional[float] = None
    humidity_offset_pct: Optional[float] = None
    target_temp_f: Optional[float] = None
    target_humidity_pct: Optional[float] = None


class GrowingAreaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    area_type: GrowingAreaType
    latitude: float
    longitude: float
    area_acres: Optional[float]
    area_sqft: Optional[float]
    nws_station_id: Optional[str]
    temp_offset_f: Optional[float]
    humidity_offset_pct: Optional[float]
    target_temp_f: Optional[float]
    target_humidity_pct: Optional[float]
    is_active: bool
    created_at: datetime
    updated_at: datetime
