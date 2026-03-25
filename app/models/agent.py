from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    aicid: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
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
    visibility: Mapped[str] = mapped_column(String(20), default="public")  # public | limited | private
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner = relationship("User", back_populates="agents")
    works = relationship("Work", back_populates="agent", cascade="all, delete-orphan")
    employments = relationship("Employment", back_populates="agent", cascade="all, delete-orphan")
    fundings = relationship("Funding", back_populates="agent", cascade="all, delete-orphan")
