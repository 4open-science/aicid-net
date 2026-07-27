from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.orcid import normalize_orcid

_ORCID_UNVERIFIED_DESCRIPTION = (
    "Self-declared ORCID metadata, not verified by ORCID OAuth. This does not "
    "grant ORCID Verified status or link this agent to an ORCID account; it is "
    "only displayed as unverified."
)


class AgentCreate(BaseModel):
    name: str
    human_operator: str

    @field_validator("human_operator")
    @classmethod
    def human_operator_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("human_operator is required")
        return v
    orcid_unverified: Optional[str] = Field(
        default=None, title="Unverified ORCID", description=_ORCID_UNVERIFIED_DESCRIPTION
    )
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
    agent_email: Optional[str] = None
    agent_telegram: Optional[str] = None
    agent_discord: Optional[str] = None
    agent_twitter: Optional[str] = None
    agent_url: Optional[str] = None
    visibility: str = "public"

    @field_validator("orcid_unverified")
    @classmethod
    def normalize_orcid_unverified(cls, value: Optional[str]) -> Optional[str]:
        return normalize_orcid(value)


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    human_operator: Optional[str] = None
    orcid_unverified: Optional[str] = Field(
        default=None, title="Unverified ORCID", description=_ORCID_UNVERIFIED_DESCRIPTION
    )
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
    agent_email: Optional[str] = None
    agent_telegram: Optional[str] = None
    agent_discord: Optional[str] = None
    agent_twitter: Optional[str] = None
    agent_url: Optional[str] = None
    visibility: Optional[str] = None

    @field_validator("orcid_unverified")
    @classmethod
    def normalize_orcid_unverified(cls, value: Optional[str]) -> Optional[str]:
        return normalize_orcid(value)


class AgentRead(BaseModel):
    id: int
    aicid: str
    owner_id: int
    name: str
    human_operator: Optional[str]
    operator_orcid: Optional[str]
    orcid_unverified: Optional[str]
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
    agent_email: Optional[str]
    agent_telegram: Optional[str]
    agent_discord: Optional[str]
    agent_twitter: Optional[str]
    agent_url: Optional[str]
    visibility: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
