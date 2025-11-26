"""Email model - stores processed email data."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Float, TIMESTAMP, ARRAY, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class Email(Base):
    """Processed email storage.

    Maps to the 'emails' table in PostgreSQL.
    """
    __tablename__ = "emails"

    # Primary identifiers
    email_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    thread_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Email metadata
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    to_emails: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    subject: Mapped[Optional[str]] = mapped_column(Text)
    date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)

    # Classification results
    category: Mapped[Optional[str]] = mapped_column(String(255))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    importance_level: Mapped[Optional[str]] = mapped_column(String(20))

    # Processing status
    status: Mapped[str] = mapped_column(String(50), default="unread")
    processed_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now()
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_emails_date", "date"),
        Index("idx_emails_category", "category"),
        Index("idx_emails_from", "from_email"),
        Index("idx_emails_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Email {self.email_id}: {self.subject[:50] if self.subject else 'No subject'}>"

    @property
    def needs_approval(self) -> bool:
        """Check if email needs human approval based on confidence."""
        from src.config import get_config
        config = get_config()
        return (
            self.confidence is not None
            and self.confidence < config.confidence_threshold
            and self.status == "pending_approval"
        )
