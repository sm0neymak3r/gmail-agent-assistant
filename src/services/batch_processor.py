"""Batch processor service for reliable inbox processing.

Handles batch job processing with Cloud Tasks for guaranteed delivery
and database-level locking for concurrent chunk protection.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from src.models import get_async_session, BatchJob
from src.services.cloud_tasks import CloudTasksClient
from src.workflows.email_processor import EmailProcessor

logger = logging.getLogger(__name__)


class LockAcquisitionFailed(Exception):
    """Raised when unable to acquire processing lock."""

    pass


class BatchProcessor:
    """Handles batch job processing with Cloud Tasks.

    Architecture:
    1. POST /process-all creates job and enqueues first task
    2. Cloud Tasks dispatches to POST /batch-worker
    3. Worker acquires lock, processes chunk, enqueues next task
    4. Cloud Tasks handles retries on failure
    """

    # Cost per email (rough estimate based on Claude API usage)
    COST_PER_EMAIL = 0.00124

    # Lock timeout in minutes (stale locks older than this are released)
    LOCK_TIMEOUT_MINUTES = 30

    def __init__(self, cloud_tasks_client: Optional[CloudTasksClient] = None):
        """Initialize batch processor.

        Args:
            cloud_tasks_client: Cloud Tasks client. Creates default if None.
        """
        self.cloud_tasks = cloud_tasks_client or CloudTasksClient()

    @staticmethod
    def generate_date_ranges(
        start_date: datetime, end_date: datetime, months_per_chunk: int = 2
    ) -> list[tuple[str, str]]:
        """Generate date ranges for chunked processing.

        Args:
            start_date: Start of processing range.
            end_date: End of processing range.
            months_per_chunk: Number of months per chunk.

        Returns:
            List of (start, end) date string tuples in YYYY/MM/DD format.
        """
        ranges = []
        current = start_date
        while current < end_date:
            chunk_end = min(current + timedelta(days=months_per_chunk * 30), end_date)
            ranges.append((current.strftime("%Y/%m/%d"), chunk_end.strftime("%Y/%m/%d")))
            current = chunk_end
        return ranges

    async def start_job(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        chunk_months: int = 2,
        chunk_size: int = 500,
    ) -> BatchJob:
        """Create a new batch job and enqueue first task.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format. Defaults to today.
            chunk_months: Number of months per processing chunk.
            chunk_size: Maximum emails per chunk.

        Returns:
            Created BatchJob.

        Raises:
            ValueError: If dates are invalid or job already running.
        """
        # Parse dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()

        if start_dt >= end_dt:
            raise ValueError("start_date must be before end_date")

        async_session = get_async_session()
        async with async_session() as session:
            # Check for existing active job
            result = await session.execute(
                select(BatchJob).where(BatchJob.status.in_(["pending", "running"]))
            )
            existing = result.scalar_one_or_none()

            if existing:
                raise ValueError(
                    f"Job {existing.job_id} is already running. "
                    f"Use /process-status/{existing.job_id} to check progress."
                )

            # Calculate total chunks
            all_ranges = self.generate_date_ranges(start_dt, end_dt, chunk_months)

            # Create new job
            job_id = str(uuid.uuid4())[:8]
            job = BatchJob(
                job_id=job_id,
                job_type="full_inbox",
                query_template="after:{start} before:{end}",
                start_date=start_dt.strftime("%Y-%m-%d"),
                end_date=end_dt.strftime("%Y-%m-%d"),
                chunk_size=chunk_size,
                chunk_months=chunk_months,
                status="pending",
                chunks_total=len(all_ranges),
                completed_ranges=[],
            )
            session.add(job)
            await session.commit()

            logger.info(f"Created batch job {job_id} with {len(all_ranges)} chunks")

            # Enqueue first task
            await session.refresh(job)

        # Enqueue to Cloud Tasks
        task_id = self.cloud_tasks.enqueue_batch_worker(job_id)
        logger.info(f"Enqueued first task {task_id} for job {job_id}")

        return job

    async def process_chunk(self, job_id: str, task_id: str) -> dict:
        """Process one chunk of a batch job.

        Called by Cloud Tasks worker endpoint. Handles:
        1. Lock acquisition to prevent concurrent processing
        2. Finding next unprocessed chunk
        3. Processing emails in that chunk
        4. Updating progress and enqueueing next task

        Args:
            job_id: Batch job ID.
            task_id: Cloud Tasks task ID for idempotency.

        Returns:
            Processing result dictionary.

        Raises:
            LockAcquisitionFailed: If another worker has the lock.
            ValueError: If job not found.
        """
        lock_id = str(uuid.uuid4())
        async_session = get_async_session()

        async with async_session() as session:
            # Get job with lock check
            result = await session.execute(
                select(BatchJob).where(BatchJob.job_id == job_id)
            )
            job = result.scalar_one_or_none()

            if not job:
                raise ValueError(f"Batch job {job_id} not found")

            # Check job status
            if job.status not in ("pending", "running"):
                logger.info(f"Job {job_id} is {job.status}, skipping")
                return {"status": "skipped", "reason": f"job_status_{job.status}"}

            # Try to acquire lock
            if not await self._try_acquire_lock(session, job, lock_id):
                raise LockAcquisitionFailed(
                    f"Could not acquire lock for job {job_id}, another worker is processing"
                )

            try:
                # Find next chunk to process
                completed_ranges = set(
                    tuple(r) for r in (job.completed_ranges or [])
                )
                start_date = datetime.strptime(job.start_date, "%Y-%m-%d")
                end_date = datetime.strptime(job.end_date, "%Y-%m-%d")
                all_ranges = self.generate_date_ranges(
                    start_date, end_date, job.chunk_months
                )

                next_range = None
                for r in all_ranges:
                    if r not in completed_ranges:
                        next_range = r
                        break

                if not next_range:
                    # All chunks completed
                    job.status = "completed"
                    job.completed_at = datetime.utcnow()
                    job.last_activity = datetime.utcnow()
                    await self._release_lock(session, job, lock_id)
                    await session.commit()
                    logger.info(f"Batch job {job_id} completed!")
                    return {"status": "completed", "job_id": job_id}

                # Update job status
                job.status = "running"
                job.current_chunk_start = next_range[0]
                job.current_chunk_end = next_range[1]
                job.last_activity = datetime.utcnow()
                if not job.started_at:
                    job.started_at = datetime.utcnow()
                await session.commit()

                # Process this chunk
                logger.info(
                    f"Job {job_id}: Processing chunk {next_range[0]} to {next_range[1]}"
                )

                processor = EmailProcessor()
                query = f"after:{next_range[0]} before:{next_range[1]}"
                results = await processor.process_batch(
                    query=query, max_emails=job.chunk_size
                )

                # Update job with results
                job.emails_processed += results.get("processed", 0)
                job.emails_categorized += results.get("categorized", 0)
                job.emails_labeled += results.get("labeled", 0)
                job.emails_pending_approval += results.get("pending_approval", 0)
                job.emails_errors += results.get("errors", 0)
                job.estimated_cost = job.emails_processed * self.COST_PER_EMAIL

                # Mark range as completed
                completed = list(job.completed_ranges or [])
                completed.append(list(next_range))
                job.completed_ranges = completed
                flag_modified(job, "completed_ranges")
                job.chunks_completed = len(completed)
                job.last_activity = datetime.utcnow()
                job.retry_count = 0  # Reset on success

                # Release lock
                await self._release_lock(session, job, lock_id)
                await session.commit()

                logger.info(
                    f"Job {job_id}: Chunk complete - "
                    f"{results.get('processed', 0)} processed, "
                    f"{results.get('errors', 0)} errors"
                )

                # Enqueue next chunk if more work remains
                remaining_chunks = len(all_ranges) - len(completed)
                if remaining_chunks > 0:
                    next_task_id = self.cloud_tasks.enqueue_batch_worker(
                        job_id, delay_seconds=5
                    )
                    logger.info(
                        f"Enqueued next task {next_task_id}, "
                        f"{remaining_chunks} chunks remaining"
                    )

                return {
                    "status": "chunk_completed",
                    "job_id": job_id,
                    "chunk": f"{next_range[0]} to {next_range[1]}",
                    "processed": results.get("processed", 0),
                    "errors": results.get("errors", 0),
                    "remaining_chunks": remaining_chunks,
                }

            except LockAcquisitionFailed:
                raise
            except Exception as e:
                # Handle processing errors
                logger.error(f"Job {job_id} chunk failed: {e}")
                job.last_error = str(e)
                job.retry_count += 1
                job.last_activity = datetime.utcnow()

                # Release lock even on failure
                await self._release_lock(session, job, lock_id)

                if job.retry_count >= 3:
                    job.status = "failed"
                    logger.error(f"Job {job_id} failed after 3 retries")

                await session.commit()
                raise

    async def _try_acquire_lock(
        self, session, job: BatchJob, lock_id: str
    ) -> bool:
        """Try to acquire processing lock on a job.

        Uses optimistic locking - checks if lock is free or stale,
        then attempts to set it atomically.

        Args:
            session: Database session.
            job: BatchJob to lock.
            lock_id: Unique lock ID for this worker.

        Returns:
            True if lock acquired, False otherwise.
        """
        now = datetime.utcnow()
        lock_timeout = now - timedelta(minutes=self.LOCK_TIMEOUT_MINUTES)

        # Check if lock is held by another worker
        if job.processing_lock_id and job.processing_lock_time:
            if job.processing_lock_time > lock_timeout:
                # Lock is held and not stale
                logger.warning(
                    f"Job {job.job_id} locked by {job.processing_lock_id} "
                    f"since {job.processing_lock_time}"
                )
                return False
            else:
                # Lock is stale, we can take it
                logger.info(
                    f"Job {job.job_id} has stale lock from {job.processing_lock_id}, "
                    f"acquiring"
                )

        # Acquire lock
        job.processing_lock_id = lock_id
        job.processing_lock_time = now
        await session.commit()

        # Verify we got it (re-read to check for race)
        await session.refresh(job)
        if job.processing_lock_id != lock_id:
            logger.warning(
                f"Lost lock race for job {job.job_id} to {job.processing_lock_id}"
            )
            return False

        logger.info(f"Acquired lock {lock_id} for job {job.job_id}")
        return True

    async def _release_lock(
        self, session, job: BatchJob, lock_id: str
    ) -> None:
        """Release processing lock on a job.

        Args:
            session: Database session.
            job: BatchJob to unlock.
            lock_id: Lock ID that should be released.
        """
        if job.processing_lock_id == lock_id:
            job.processing_lock_id = None
            job.processing_lock_time = None
            logger.info(f"Released lock {lock_id} for job {job.job_id}")
        else:
            logger.warning(
                f"Cannot release lock {lock_id} for job {job.job_id}, "
                f"current lock is {job.processing_lock_id}"
            )

    async def resume_job(self, job_id: str) -> dict:
        """Resume a paused or failed job by enqueueing a new task.

        Args:
            job_id: Job ID to resume.

        Returns:
            Status dictionary.

        Raises:
            ValueError: If job not found or cannot be resumed.
        """
        async_session = get_async_session()
        async with async_session() as session:
            result = await session.execute(
                select(BatchJob).where(BatchJob.job_id == job_id)
            )
            job = result.scalar_one_or_none()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            if job.status == "completed":
                return {"status": "already_completed", "job_id": job_id}

            if job.status in ("failed", "paused"):
                job.status = "running"
                job.retry_count = 0
                job.last_activity = datetime.utcnow()
                # Clear any stale lock
                job.processing_lock_id = None
                job.processing_lock_time = None
                await session.commit()

        # Enqueue task
        task_id = self.cloud_tasks.enqueue_batch_worker(job_id)
        logger.info(f"Resumed job {job_id} with task {task_id}")

        return {"status": "resumed", "job_id": job_id, "task_id": task_id}

    async def pause_job(self, job_id: str) -> dict:
        """Pause a running job.

        The job will stop after current chunk completes since Cloud Tasks
        won't dispatch new tasks to a paused job.

        Args:
            job_id: Job ID to pause.

        Returns:
            Status dictionary.
        """
        async_session = get_async_session()
        async with async_session() as session:
            result = await session.execute(
                select(BatchJob).where(BatchJob.job_id == job_id)
            )
            job = result.scalar_one_or_none()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            if job.status not in ("pending", "running"):
                return {
                    "status": job.status,
                    "message": f"Job is {job.status}, cannot pause",
                }

            job.status = "paused"
            job.last_activity = datetime.utcnow()
            await session.commit()

            return {
                "status": "paused",
                "job_id": job_id,
                "message": "Job paused. Resume with POST /process-continue/{job_id}",
            }

    async def get_status(self, job_id: str) -> Optional[dict]:
        """Get detailed status of a batch job.

        Args:
            job_id: Job ID to check.

        Returns:
            Status dictionary or None if not found.
        """
        async_session = get_async_session()
        async with async_session() as session:
            result = await session.execute(
                select(BatchJob).where(BatchJob.job_id == job_id)
            )
            job = result.scalar_one_or_none()

            if not job:
                return None

            current_chunk = None
            if job.current_chunk_start and job.current_chunk_end:
                current_chunk = f"{job.current_chunk_start} to {job.current_chunk_end}"

            return {
                "job_id": job.job_id,
                "status": job.status,
                "progress_percent": job.progress_percent,
                "chunks_completed": job.chunks_completed,
                "chunks_total": job.chunks_total,
                "emails_processed": job.emails_processed,
                "emails_categorized": job.emails_categorized,
                "emails_labeled": job.emails_labeled,
                "emails_pending_approval": job.emails_pending_approval,
                "emails_errors": job.emails_errors,
                "estimated_cost": job.estimated_cost,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "last_activity": job.last_activity.isoformat() if job.last_activity else None,
                "current_chunk": current_chunk,
                "error": job.last_error,
                "is_locked": bool(job.processing_lock_id),
            }
