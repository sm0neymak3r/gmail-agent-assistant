"""Checkpoint model - stores LangGraph state for recovery."""

from datetime import datetime
from typing import Any, Optional
from sqlalchemy import String, Integer, ForeignKey, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class Checkpoint(Base):
    """LangGraph checkpoint state for recovery.

    Maps to the 'checkpoints' table in PostgreSQL.
    Stores serialized state at each processing step for crash recovery.
    """
    __tablename__ = "checkpoints"

    checkpoint_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        ForeignKey("emails.email_id", ondelete="CASCADE"),
    )
    step: Mapped[str] = mapped_column(String(100), nullable=False)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_checkpoints_email_id", "email_id"),
        Index("idx_checkpoints_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Checkpoint {self.checkpoint_id}: {self.email_id} @ {self.step}>"
