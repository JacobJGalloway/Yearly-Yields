import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.field import PlotType


class GrowingAreaPlotCreate(BaseModel):
    name: str = Field(..., max_length=25)
    plot_type: PlotType
    length_ft: Optional[float] = None
    width_ft: Optional[float] = None
    area_sqft: Optional[float] = None
    notes: Optional[str] = None


class GrowingAreaPlotUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=25)
    length_ft: Optional[float] = None
    width_ft: Optional[float] = None
    area_sqft: Optional[float] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class GrowingAreaPlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    growing_area_id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    plot_type: PlotType
    length_ft: Optional[float]
    width_ft: Optional[float]
    area_sqft: Optional[float]
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
