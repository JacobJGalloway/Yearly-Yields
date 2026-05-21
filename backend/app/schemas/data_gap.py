import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DataGapRead(BaseModel):
    area_id: uuid.UUID
    area_name: str
    last_reading_at: Optional[datetime]
    gap_days: int
