import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field

from app.core.crop_phases import get_phase_days, get_sub_phase
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
    invoice_id: Optional[uuid.UUID] = None
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
    crop_name: Optional[str] = None

    @computed_field
    @property
    def current_phase(self) -> Optional[str]:
        if self.status != CropCycleStatus.active or self.crop_name is None:
            return None
        days_in = (date.today() - self.planted_at).days
        pd = get_phase_days(self.crop_name, self.planted_at, self.forecasted_end_date)
        if days_in < pd.seeding_days:
            return "seeding"
        if days_in < pd.seeding_days + pd.growing_days:
            return "growing"
        return "harvest"

    @computed_field
    @property
    def current_sub_phase(self) -> Optional[str]:
        if self.status != CropCycleStatus.active or self.crop_name is None:
            return None
        days_in = (date.today() - self.planted_at).days
        sp = get_sub_phase(self.crop_name, days_in, self.planted_at, self.forecasted_end_date)
        return sp.label if sp else None
