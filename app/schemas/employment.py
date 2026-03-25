from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class EmploymentCreate(BaseModel):
    organization: str
    role: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class EmploymentUpdate(BaseModel):
    organization: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class EmploymentRead(BaseModel):
    id: int
    agent_id: int
    organization: str
    role: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
