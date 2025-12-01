"""ImportanceRule model - stores learned importance classification rules."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class ImportanceRule(Base):
    """Learned importance classification rules.

    Maps to the 'importance_rules' table in PostgreSQL.
    Stores patterns for automatic importance detection.
    """
    __tablename__ = "importance_rules"

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<ImportanceRule {self.rule_id}: {self.rule_type} -> {self.priority}>"

    def matches(self, text: str) -> bool:
        """Check if pattern matches given text."""
        import re
        try:
            return bool(re.search(self.pattern, text, re.IGNORECASE))
        except re.error:
            # Invalid regex, treat as literal string match
            return self.pattern.lower() in text.lower()
