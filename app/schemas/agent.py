from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class AgentCreate(BaseModel):
    name: str
    human_operator: Optional[str] = None
    agent_harness: Optional[str] = None
    agent_type: str = "autonomous_agent"
    base_model: Optional[str] = None
    version: Optional[str] = None
    organization: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    website_url: Optional[str] = None
    github_url: Optional[str] = None
    paper_url: Optional[str] = None
    visibility: str = "public"


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    human_operator: Optional[str] = None
    agent_harness: Optional[str] = None
    agent_type: Optional[str] = None
    base_model: Optional[str] = None
    version: Optional[str] = None
    organization: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    website_url: Optional[str] = None
    github_url: Optional[str] = None
    paper_url: Optional[str] = None
    visibility: Optional[str] = None


class AgentRead(BaseModel):
    id: int
    aicid: str
    owner_id: int
    name: str
    human_operator: Optional[str]
    agent_harness: Optional[str]
    agent_type: str
    base_model: Optional[str]
    version: Optional[str]
    organization: Optional[str]
    description: Optional[str]
    keywords: Optional[str]
    website_url: Optional[str]
    github_url: Optional[str]
    paper_url: Optional[str]
    visibility: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
