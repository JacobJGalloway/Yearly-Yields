import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.field import PlotType


class GrowingAreaPlotCreate(BaseModel):
    plot_index: int = Field(..., ge=1, description="Row index within the area (1-based; 0 is reserved for the open-field sentinel)")
    name: Optional[str] = Field(None, max_length=100)
    plot_type: PlotType
    harvest_weekdays: Optional[List[int]] = Field(None, description="ISO weekday integers 1=Mon … 7=Sun")
    length_ft: Optional[float] = None
    width_ft: Optional[float] = None
    area_sqft: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("harvest_weekdays")
    @classmethod
    def validate_weekdays(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None:
            for day in v:
                if day < 1 or day > 7:
                    raise ValueError("harvest_weekdays must contain ISO weekday integers 1–7")
        return v


class GrowingAreaPlotUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    harvest_weekdays: Optional[List[int]] = Field(None, description="ISO weekday integers 1=Mon … 7=Sun")
    length_ft: Optional[float] = None
    width_ft: Optional[float] = None
    area_sqft: Optional[float] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("harvest_weekdays")
    @classmethod
    def validate_weekdays(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None:
            for day in v:
                if day < 1 or day > 7:
                    raise ValueError("harvest_weekdays must contain ISO weekday integers 1–7")
        return v


class GrowingAreaPlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    growing_area_id: uuid.UUID
    owner_id: uuid.UUID
    plot_index: int
    name: Optional[str]
    plot_type: PlotType
    harvest_weekdays: Optional[List[int]]
    length_ft: Optional[float]
    width_ft: Optional[float]
    area_sqft: Optional[float]
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
