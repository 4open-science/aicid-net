from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Work(Base):
    __tablename__ = "works"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False)
    put_code: Mapped[str] = mapped_column(String(100), index=True)  # external ref key

    work_type: Mapped[str] = mapped_column(
        String(50), default="paper"
    )  # paper | dataset | experiment | software | preprint
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    doi: Mapped[Optional[str]] = mapped_column(String(255))
    url: Mapped[Optional[str]] = mapped_column(String(500))
    journal: Mapped[Optional[str]] = mapped_column(String(255))
    published_date: Mapped[Optional[date]] = mapped_column(Date)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent = relationship("Agent", back_populates="works")
