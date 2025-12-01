"""Feedback model - stores user feedback for model improvement."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class Feedback(Base):
    """User feedback for training and improvement.

    Maps to the 'feedback' table in PostgreSQL.
    Records user corrections to agent decisions for active learning.
    """
    __tablename__ = "feedback"

    feedback_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        ForeignKey("emails.email_id", ondelete="SET NULL"),
    )
    user_action: Mapped[str] = mapped_column(String(50), nullable=False)
    proposed_category: Mapped[Optional[str]] = mapped_column(String(255))
    final_category: Mapped[Optional[str]] = mapped_column(String(255))
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Feedback {self.feedback_id}: {self.user_action} on {self.email_id}>"

    @property
    def was_corrected(self) -> bool:
        """Check if user corrected the proposed category."""
        return (
            self.proposed_category is not None
            and self.final_category is not None
            and self.proposed_category != self.final_category
        )
