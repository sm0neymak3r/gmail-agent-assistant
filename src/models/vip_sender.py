"""VIPSender model - stores VIP sender patterns for importance scoring."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class VIPSender(Base):
    """VIP sender patterns for importance scoring.

    Maps to the 'vip_senders' table in PostgreSQL.
    Email patterns can be exact matches or SQL LIKE patterns with %.
    """
    __tablename__ = "vip_senders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email_pattern: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    importance_boost: Mapped[float] = mapped_column(Float, default=0.3)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<VIPSender {self.id}: {self.email_pattern} (+{self.importance_boost})>"

    def matches(self, email: str) -> bool:
        """Check if an email matches this VIP pattern.

        Args:
            email: Email address to check

        Returns:
            True if the email matches the pattern
        """
        import re

        email = email.lower()
        pattern = self.email_pattern.lower()

        if "%" not in pattern:
            # Exact match
            return email == pattern

        # Convert SQL LIKE pattern to regex
        regex_pattern = "^" + pattern.replace("%", ".*") + "$"
        return bool(re.match(regex_pattern, email))
