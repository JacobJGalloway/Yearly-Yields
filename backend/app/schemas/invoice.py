import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.crop import YieldUnit
from app.models.invoice import InvoiceStatus


class CropRateCreate(BaseModel):
    crop_id: uuid.UUID
    rate_per_unit: float
    unit: YieldUnit
    effective_date: date


class CropRateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    crop_id: uuid.UUID
    rate_per_unit: float
    unit: YieldUnit
    is_active: bool
    effective_date: date
    created_at: datetime


class InvoiceUpdate(BaseModel):
    quantity: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[InvoiceStatus] = None


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    crop_cycle_id: uuid.UUID
    rate_id: uuid.UUID
    quantity: float
    unit: YieldUnit
    unit_price: float
    total_amount: float
    status: InvoiceStatus
    invoice_date: date
    due_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
