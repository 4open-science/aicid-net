from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class FundingCreate(BaseModel):
    title: str
    funder: Optional[str] = None
    grant_number: Optional[str] = None
    url: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class FundingUpdate(BaseModel):
    title: Optional[str] = None
    funder: Optional[str] = None
    grant_number: Optional[str] = None
    url: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class FundingRead(BaseModel):
    id: int
    agent_id: int
    title: str
    funder: Optional[str]
    grant_number: Optional[str]
    url: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    created_at: datetime

    model_config = {"from_attributes": True}
