from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class WorkCreate(BaseModel):
    work_type: str = "paper"
    title: str
    doi: Optional[str] = None
    url: Optional[str] = None
    journal: Optional[str] = None
    published_date: Optional[date] = None
    description: Optional[str] = None


class WorkUpdate(BaseModel):
    work_type: Optional[str] = None
    title: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    journal: Optional[str] = None
    published_date: Optional[date] = None
    description: Optional[str] = None


class WorkRead(BaseModel):
    id: int
    agent_id: int
    put_code: str
    work_type: str
    title: str
    doi: Optional[str]
    url: Optional[str]
    journal: Optional[str]
    published_date: Optional[date]
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
