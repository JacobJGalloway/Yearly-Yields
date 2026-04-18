import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field

from app.core.crop_phases import get_phase_days
from app.models.crop import CropCycleStatus, YieldUnit


class CropRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    greenhouse_compatible: bool
    typical_cycle_days: int
    default_harvest_customer_id: Optional[uuid.UUID]
    default_transplant_customer_id: Optional[uuid.UUID]
    created_at: datetime

    @computed_field
    @property
    def seeding_days(self) -> int:
        return get_phase_days(self.name).seeding_days

    @computed_field
    @property
    def growing_days(self) -> int:
        return get_phase_days(self.name).growing_days

    @computed_field
    @property
    def harvest_days(self) -> int:
        return get_phase_days(self.name).harvest_days

    @computed_field
    @property
    def sub_phases(self) -> list[dict]:
        pd = get_phase_days(self.name)
        return [
            {"name": sp.name, "label": sp.label, "day_start": sp.day_start, "day_end": sp.day_end}
            for sp in pd.seeding_sub_phases + pd.growing_sub_phases + pd.harvest_sub_phases
        ]


class CropCycleCreate(BaseModel):
    growing_area_id: uuid.UUID
    crop_id: Optional[uuid.UUID] = None
    planned_crop_id: Optional[uuid.UUID] = None
    season_year: int
    cycle_number: int
    planted_at: date
    yield_unit: YieldUnit
    target_yield: Optional[float] = None
    forecasted_end_date: Optional[date] = None


class CropCycleUpdate(BaseModel):
    status: Optional[CropCycleStatus] = None
    actual_yield: Optional[float] = None
    harvested_at: Optional[date] = None
    target_yield: Optional[float] = None
    planned_crop_id: Optional[uuid.UUID] = None
    forecasted_end_date: Optional[date] = None


class CropCycleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    growing_area_id: uuid.UUID
    crop_id: Optional[uuid.UUID]
    planned_crop_id: Optional[uuid.UUID]
    season_year: int
    cycle_number: int
    planted_at: date
    harvested_at: Optional[date]
    forecasted_end_date: Optional[date]
    yield_unit: YieldUnit
    target_yield: Optional[float]
    actual_yield: Optional[float]
    status: CropCycleStatus
    created_at: datetime
    updated_at: datetime
