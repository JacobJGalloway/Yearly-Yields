import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.alert import AlertStatus, AlertType


class AlertUpdate(BaseModel):
    status: Optional[AlertStatus] = None


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    growing_area_id: uuid.UUID
    crop_cycle_id: Optional[uuid.UUID]
    triggering_reading_id: uuid.UUID
    alert_type: AlertType
    status: AlertStatus
    consecutive_normal_count: int
    last_email_sent_at: Optional[datetime]
    resolved_at: Optional[datetime]
    assessment_summary: Optional[str]
    created_at: datetime
    updated_at: datetime
