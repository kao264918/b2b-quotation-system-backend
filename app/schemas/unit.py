from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UnitBase(BaseModel):
    label: str


class UnitCreate(UnitBase):
    pass


class UnitUpdate(BaseModel):
    label: Optional[str] = None


class Unit(UnitBase):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
