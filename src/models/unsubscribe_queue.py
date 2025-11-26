"""UnsubscribeQueue model - manages pending unsubscribe actions."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class UnsubscribeQueue(Base):
    """Pending unsubscribe actions queue.

    Maps to the 'unsubscribe_queue' table in PostgreSQL.
    Manages newsletter/marketing email unsubscription workflow.
    """
    __tablename__ = "unsubscribe_queue"

    queue_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        ForeignKey("emails.email_id", ondelete="SET NULL"),
    )
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    unsubscribe_link: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    user_action: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    executed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)

    def __repr__(self) -> str:
        return f"<UnsubscribeQueue {self.queue_id}: {self.sender} ({self.status})>"
