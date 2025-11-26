"""ProcessingLog model - audit log for all agent actions."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, TIMESTAMP, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class ProcessingLog(Base):
    """Audit log for all agent actions.

    Maps to the 'processing_log' table in PostgreSQL.
    Records every action taken by agents for debugging and auditing.
    """
    __tablename__ = "processing_log"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[Optional[str]] = mapped_column(String(255))
    agent: Mapped[Optional[str]] = mapped_column(String(100))
    action: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    error: Mapped[Optional[str]] = mapped_column(Text)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_processing_log_email_id", "email_id"),
        Index("idx_processing_log_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<ProcessingLog {self.log_id}: {self.agent}/{self.action} ({self.status})>"
