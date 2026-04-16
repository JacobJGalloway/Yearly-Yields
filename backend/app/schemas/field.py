import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.field import GrowingAreaType


class GrowingAreaCreate(BaseModel):
    name: str
    area_type: GrowingAreaType
    latitude: float
    longitude: float
    area_acres: Optional[float] = None
    area_sqft: Optional[float] = None


class GrowingAreaUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    area_acres: Optional[float] = None
    area_sqft: Optional[float] = None


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
    is_active: bool
    created_at: datetime
    updated_at: datetime
