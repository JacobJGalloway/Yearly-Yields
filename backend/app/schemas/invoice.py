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
    customer_id: Optional[uuid.UUID] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    notes: Optional[str] = None


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    crop_cycle_id: uuid.UUID
    crop_rate_id: Optional[uuid.UUID]
    customer_id: Optional[uuid.UUID]
    invoice_type: str
    status: InvoiceStatus
    description: Optional[str]
    quantity: float
    unit: YieldUnit
    unit_price: Optional[float]
    total_amount: Optional[float]
    invoice_date: date
    due_date: Optional[date]
    notes: Optional[str]
    sent_at: Optional[datetime]
    paid_at: Optional[datetime]
    voided_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class InvoiceConfigUpdate(BaseModel):
    harvest_customer_id: Optional[uuid.UUID] = None
    transplant_customer_id: Optional[uuid.UUID] = None


class InvoiceConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    growing_area_id: uuid.UUID
    harvest_customer_id: Optional[uuid.UUID]
    transplant_customer_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
