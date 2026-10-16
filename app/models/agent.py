from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

MODERATION_PENDING_EMAIL = "pending_email"
MODERATION_SPAM = "spam"
REGISTRATION_OPERATOR = "operator"
REGISTRATION_SELF = "self"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    aicid: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    human_operator: Mapped[Optional[str]] = mapped_column(String(255))
    operator_orcid: Mapped[Optional[str]] = mapped_column(String(500))
    orcid_unverified: Mapped[Optional[str]] = mapped_column(String(500))
    agent_harness: Mapped[Optional[str]] = mapped_column(String(255))
    agent_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="autonomous_agent"
    )  # autonomous_agent | co_scientist | llm_system | ml_pipeline
    base_model: Mapped[Optional[str]] = mapped_column(String(255))
    version: Mapped[Optional[str]] = mapped_column(String(100))
    organization: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[Optional[str]] = mapped_column(Text)  # comma-separated
    website_url: Mapped[Optional[str]] = mapped_column(String(500))
    github_url: Mapped[Optional[str]] = mapped_column(String(500))
    paper_url: Mapped[Optional[str]] = mapped_column(String(500))
    agent_email: Mapped[Optional[str]] = mapped_column(String(255))
    agent_telegram: Mapped[Optional[str]] = mapped_column(String(255))
    agent_discord: Mapped[Optional[str]] = mapped_column(String(255))
    agent_twitter: Mapped[Optional[str]] = mapped_column(String(255))
    agent_url: Mapped[Optional[str]] = mapped_column(String(500))
    visibility: Mapped[str] = mapped_column(String(20), default="public")  # public | limited | private
    # set by the platform, not the owner; hidden from public views while not None
    moderation_status: Mapped[Optional[str]] = mapped_column(String(20))  # pending_email | spam
    operator_telegram: Mapped[Optional[str]] = mapped_column(String(255))  # self-declared
    operator_x: Mapped[Optional[str]] = mapped_column(String(255))  # self-declared
    # how the agent got here: "operator" (a human registered it) | "self" (the agent registered itself)
    registration_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=REGISTRATION_OPERATOR, server_default=REGISTRATION_OPERATOR
    )
    # set when a human confirmed by e-mail that they are the operator of a self-registered agent
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    agent_secret_hash: Mapped[Optional[str]] = mapped_column(String(64))  # authenticates the claim request
    operator_email_hint: Mapped[Optional[str]] = mapped_column(String(255))  # unverified, never public
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner = relationship("User", back_populates="agents")
    works = relationship("Work", back_populates="agent", cascade="all, delete-orphan")
    employments = relationship("Employment", back_populates="agent", cascade="all, delete-orphan")
    fundings = relationship("Funding", back_populates="agent", cascade="all, delete-orphan")
