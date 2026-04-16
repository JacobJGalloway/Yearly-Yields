import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.yield_plan import ConfidenceLevel


class YieldPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    growing_area_id: uuid.UUID
    crop_cycle_id: uuid.UUID
    recommended_plant_quantity: float
    target_yield: float
    confidence_level: ConfidenceLevel
    reasoning: str
    created_at: datetime
    updated_at: datetime
