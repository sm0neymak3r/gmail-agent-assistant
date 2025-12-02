"""CalendarEvent model - stores extracted calendar events from emails."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Text, Float, Boolean, TIMESTAMP, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base


class CalendarEvent(Base):
    """Calendar events extracted from emails.

    Maps to the 'calendar_events' table in PostgreSQL.
    Stores events detected by the Calendar Agent for user review/creation.
    """
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        ForeignKey("emails.email_id", ondelete="CASCADE"),
    )

    # Event details
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    start_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    end_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    location: Mapped[Optional[str]] = mapped_column(String(500))
    is_virtual: Mapped[bool] = mapped_column(Boolean, default=False)
    virtual_link: Mapped[Optional[str]] = mapped_column(String(1000))
    attendees: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Extraction metadata
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    conflicts: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<CalendarEvent {self.id}: {self.title} @ {self.start_time}>"

    @property
    def has_conflicts(self) -> bool:
        """Check if event has any calendar conflicts."""
        return bool(self.conflicts)

    @property
    def needs_review(self) -> bool:
        """Check if event needs user review before creation."""
        return (
            self.status == "pending"
            or self.has_conflicts
            or (self.confidence is not None and self.confidence < 0.8)
        )
