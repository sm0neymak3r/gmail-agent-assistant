"""Batch job model - tracks long-running inbox processing jobs."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Float, Integer, TIMESTAMP, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class BatchJob(Base):
    """Tracks batch processing jobs for full inbox processing.

    Maps to the 'batch_jobs' table in PostgreSQL.
    """
    __tablename__ = "batch_jobs"

    # Primary identifier
    job_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Job configuration
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "full_inbox", "date_range"
    query_template: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[str] = mapped_column(String(20), nullable=False)
    end_date: Mapped[str] = mapped_column(String(20), nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, default=500)
    chunk_months: Mapped[int] = mapped_column(Integer, default=2)  # Months per chunk

    # Progress tracking
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, running, completed, failed, paused
    current_chunk_start: Mapped[Optional[str]] = mapped_column(String(20))
    current_chunk_end: Mapped[Optional[str]] = mapped_column(String(20))
    chunks_completed: Mapped[int] = mapped_column(Integer, default=0)
    chunks_total: Mapped[int] = mapped_column(Integer, default=0)

    # Email counts
    emails_processed: Mapped[int] = mapped_column(Integer, default=0)
    emails_categorized: Mapped[int] = mapped_column(Integer, default=0)
    emails_labeled: Mapped[int] = mapped_column(Integer, default=0)
    emails_pending_approval: Mapped[int] = mapped_column(Integer, default=0)
    emails_errors: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    last_activity: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())

    # Cost tracking
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)

    # Error tracking
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Processing lock (prevents concurrent chunk processing)
    processing_lock_id: Mapped[Optional[str]] = mapped_column(String(36))
    processing_lock_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)

    # Completed date ranges (JSON array of [start, end] pairs)
    completed_ranges: Mapped[Optional[dict]] = mapped_column(JSON, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<BatchJob {self.job_id}: {self.status} - {self.emails_processed} processed>"

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.chunks_total == 0:
            return 0.0
        return (self.chunks_completed / self.chunks_total) * 100

    @property
    def is_active(self) -> bool:
        """Check if job is currently active."""
        return self.status in ("pending", "running")
