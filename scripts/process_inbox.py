#!/usr/bin/env python3
"""Full inbox processing script with progress tracking and resume capability.

This script processes your entire Gmail inbox in chunks, with:
- Progress tracking saved to disk (resume after disconnection)
- Cost estimation and tracking
- Automatic retry on failures
- Cloud Run timeout handling

Usage:
    # Start fresh processing
    python scripts/process_inbox.py

    # Resume from previous run
    python scripts/process_inbox.py --resume

    # Process specific date range
    python scripts/process_inbox.py --start-date 2020-01-01 --end-date 2024-12-31

    # Dry run (show what would be processed)
    python scripts/process_inbox.py --dry-run
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("inbox_processing.log"),
    ],
)
logger = logging.getLogger(__name__)

# Configuration
SERVICE_URL = "https://gmail-agent-dev-621335261494.us-central1.run.app"
PROGRESS_FILE = "inbox_progress.json"
CHUNK_SIZE = 500  # Emails per API call
REQUEST_TIMEOUT = 3600  # 1 hour timeout for large batches
RETRY_DELAY = 60  # Seconds to wait before retry
MAX_RETRIES = 3

# Cost estimation (Anthropic pricing)
COST_PER_EMAIL = 0.00124  # ~$0.00124 per email (Haiku + 10% Sonnet escalation)


@dataclass
class ProcessingProgress:
    """Tracks processing progress for resume capability."""
    started_at: str
    last_updated: str
    status: str  # "in_progress", "completed", "failed"

    # Progress tracking
    total_emails_estimated: int
    emails_processed: int
    emails_categorized: int
    emails_labeled: int
    emails_pending_approval: int
    emails_errors: int

    # Chunk tracking
    chunks_completed: int
    current_chunk_start_date: str
    current_chunk_end_date: str

    # Cost tracking
    estimated_cost: float
    duration_seconds: float

    # Date range processing
    date_ranges_completed: list

    def save(self, filepath: str = PROGRESS_FILE):
        """Save progress to file."""
        with open(filepath, "w") as f:
            json.dump(asdict(self), f, indent=2)
        logger.debug(f"Progress saved to {filepath}")

    @classmethod
    def load(cls, filepath: str = PROGRESS_FILE) -> Optional["ProcessingProgress"]:
        """Load progress from file."""
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            return cls(**data)
        except Exception as e:
            logger.warning(f"Failed to load progress: {e}")
            return None

    @classmethod
    def create_new(cls, total_estimate: int = 65000) -> "ProcessingProgress":
        """Create new progress tracker."""
        now = datetime.now().isoformat()
        return cls(
            started_at=now,
            last_updated=now,
            status="in_progress",
            total_emails_estimated=total_estimate,
            emails_processed=0,
            emails_categorized=0,
            emails_labeled=0,
            emails_pending_approval=0,
            emails_errors=0,
            chunks_completed=0,
            current_chunk_start_date="",
            current_chunk_end_date="",
            estimated_cost=0.0,
            duration_seconds=0.0,
            date_ranges_completed=[],
        )


def get_date_ranges(start_date: datetime, end_date: datetime, months_per_chunk: int = 3) -> list:
    """Generate date ranges for chunked processing.

    Returns list of (start_date, end_date) tuples covering the full range.
    """
    ranges = []
    current = start_date

    while current < end_date:
        chunk_end = min(
            current + timedelta(days=months_per_chunk * 30),
            end_date
        )
        ranges.append((current, chunk_end))
        current = chunk_end

    return ranges


def process_chunk(query: str, max_emails: int = CHUNK_SIZE) -> dict:
    """Process a chunk of emails via the Cloud Run API.

    Returns:
        API response dict with processing results
    """
    url = f"{SERVICE_URL}/process"
    payload = {
        "trigger": "batch_script",
        "query": query,
        "max_emails": max_emails,
    }

    logger.info(f"Processing chunk: {query} (max {max_emails} emails)")

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=REQUEST_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.warning("Request timed out - Cloud Run may still be processing")
        return {"status": "timeout", "error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return {"status": "error", "error": str(e)}


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def print_progress(progress: ProcessingProgress):
    """Print current progress summary."""
    pct = (progress.emails_processed / progress.total_emails_estimated * 100) if progress.total_emails_estimated > 0 else 0

    print("\n" + "=" * 60)
    print("INBOX PROCESSING PROGRESS")
    print("=" * 60)
    print(f"Status: {progress.status}")
    print(f"Started: {progress.started_at}")
    print(f"Last updated: {progress.last_updated}")
    print(f"\nProgress: {progress.emails_processed:,} / {progress.total_emails_estimated:,} ({pct:.1f}%)")
    print(f"  - Categorized: {progress.emails_categorized:,}")
    print(f"  - Labeled: {progress.emails_labeled:,}")
    print(f"  - Pending approval: {progress.emails_pending_approval:,}")
    print(f"  - Errors: {progress.emails_errors:,}")
    print(f"\nChunks completed: {progress.chunks_completed}")
    print(f"Duration: {format_duration(progress.duration_seconds)}")
    print(f"Estimated cost: ${progress.estimated_cost:.2f}")

    # Estimate remaining
    if progress.emails_processed > 0 and progress.duration_seconds > 0:
        rate = progress.emails_processed / progress.duration_seconds
        remaining = progress.total_emails_estimated - progress.emails_processed
        eta_seconds = remaining / rate if rate > 0 else 0
        print(f"\nProcessing rate: {rate:.1f} emails/second")
        print(f"Estimated time remaining: {format_duration(eta_seconds)}")

    print("=" * 60 + "\n")


def run_processing(
    start_date: datetime,
    end_date: datetime,
    resume: bool = False,
    dry_run: bool = False,
):
    """Run the full inbox processing.

    Args:
        start_date: Start of date range to process
        end_date: End of date range to process
        resume: Whether to resume from previous progress
        dry_run: If True, show what would be processed without actually processing
    """
    # Load or create progress
    progress = None
    if resume:
        progress = ProcessingProgress.load()
        if progress:
            logger.info("Resuming from previous progress")
            print_progress(progress)
        else:
            logger.info("No previous progress found, starting fresh")

    if not progress:
        progress = ProcessingProgress.create_new()

    # Generate date ranges
    date_ranges = get_date_ranges(start_date, end_date, months_per_chunk=2)
    logger.info(f"Processing {len(date_ranges)} date range chunks from {start_date.date()} to {end_date.date()}")

    # Filter out already completed ranges if resuming
    completed_ranges = set(tuple(r) for r in progress.date_ranges_completed)
    pending_ranges = [
        r for r in date_ranges
        if (r[0].strftime("%Y/%m/%d"), r[1].strftime("%Y/%m/%d")) not in completed_ranges
    ]

    logger.info(f"Pending ranges: {len(pending_ranges)} (already completed: {len(completed_ranges)})")

    if dry_run:
        print("\n[DRY RUN] Would process the following date ranges:")
        for i, (range_start, range_end) in enumerate(pending_ranges, 1):
            print(f"  {i}. {range_start.date()} to {range_end.date()}")
        print(f"\nEstimated total cost: ${len(pending_ranges) * CHUNK_SIZE * COST_PER_EMAIL:.2f}")
        return

    # Process each date range
    start_time = time.time()

    for range_idx, (range_start, range_end) in enumerate(pending_ranges):
        range_start_str = range_start.strftime("%Y/%m/%d")
        range_end_str = range_end.strftime("%Y/%m/%d")

        logger.info(f"\n[{range_idx + 1}/{len(pending_ranges)}] Processing: {range_start_str} to {range_end_str}")

        progress.current_chunk_start_date = range_start_str
        progress.current_chunk_end_date = range_end_str

        # Process this date range (may need multiple API calls if > CHUNK_SIZE emails)
        query = f"after:{range_start_str} before:{range_end_str}"
        emails_in_range = 0
        range_complete = False

        while not range_complete:
            # Retry logic
            for retry in range(MAX_RETRIES):
                result = process_chunk(query, CHUNK_SIZE)

                if result.get("status") == "completed":
                    break
                elif result.get("status") == "timeout":
                    logger.warning(f"Timeout on attempt {retry + 1}, waiting {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                elif result.get("status") == "error":
                    logger.error(f"Error on attempt {retry + 1}: {result.get('error')}")
                    if retry < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                    else:
                        logger.error("Max retries exceeded, marking range as failed")
                        progress.status = "failed"
                        progress.save()
                        return

            # Update progress from result
            processed = result.get("processed", 0)
            emails_in_range += processed

            progress.emails_processed += processed
            progress.emails_categorized += result.get("categorized", 0)
            progress.emails_labeled += result.get("labeled", 0)
            progress.emails_pending_approval += result.get("pending_approval", 0)
            progress.emails_errors += result.get("errors", 0)
            progress.duration_seconds = time.time() - start_time
            progress.estimated_cost = progress.emails_processed * COST_PER_EMAIL
            progress.last_updated = datetime.now().isoformat()

            # Log chunk result
            logger.info(
                f"  Chunk result: {processed} processed, "
                f"{result.get('categorized', 0)} categorized, "
                f"{result.get('errors', 0)} errors, "
                f"{result.get('duration_seconds', 0):.1f}s"
            )

            # Check if range is complete (fewer than CHUNK_SIZE means no more emails)
            if processed < CHUNK_SIZE:
                range_complete = True
            else:
                # More emails in this range, continue processing
                logger.info(f"  Range has more emails, continuing...")
                time.sleep(5)  # Brief pause between chunks

        # Mark range as completed
        progress.date_ranges_completed.append((range_start_str, range_end_str))
        progress.chunks_completed += 1
        progress.save()

        # Print progress after each range
        print_progress(progress)

        # Brief pause between date ranges
        if range_idx < len(pending_ranges) - 1:
            time.sleep(10)

    # Mark as completed
    progress.status = "completed"
    progress.last_updated = datetime.now().isoformat()
    progress.save()

    logger.info("Processing completed!")
    print_progress(progress)


def main():
    parser = argparse.ArgumentParser(
        description="Process full Gmail inbox in chunks with progress tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start processing full inbox (from 2015 to now)
  python scripts/process_inbox.py

  # Resume after disconnection
  python scripts/process_inbox.py --resume

  # Process specific date range
  python scripts/process_inbox.py --start-date 2023-01-01 --end-date 2024-01-01

  # See what would be processed without actually processing
  python scripts/process_inbox.py --dry-run

  # Check current progress
  python scripts/process_inbox.py --status
        """,
    )

    parser.add_argument(
        "--resume", "-r",
        action="store_true",
        help="Resume from previous progress",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be processed without processing",
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show current progress and exit",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2015-01-01",
        help="Start date (YYYY-MM-DD), default: 2015-01-01",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD), default: today",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset progress and start fresh",
    )

    args = parser.parse_args()

    # Handle status check
    if args.status:
        progress = ProcessingProgress.load()
        if progress:
            print_progress(progress)
        else:
            print("No progress file found. Run without --status to start processing.")
        return

    # Handle reset
    if args.reset:
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
            logger.info("Progress reset")
        return

    # Parse dates
    try:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Invalid start date format: {args.start_date}")
        sys.exit(1)

    if args.end_date:
        try:
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid end date format: {args.end_date}")
            sys.exit(1)
    else:
        end_date = datetime.now()

    # Validate dates
    if start_date >= end_date:
        logger.error("Start date must be before end date")
        sys.exit(1)

    # Run processing
    try:
        run_processing(
            start_date=start_date,
            end_date=end_date,
            resume=args.resume,
            dry_run=args.dry_run,
        )
    except KeyboardInterrupt:
        logger.info("\nProcessing interrupted by user")
        progress = ProcessingProgress.load()
        if progress:
            progress.status = "interrupted"
            progress.last_updated = datetime.now().isoformat()
            progress.save()
            print("\nProgress saved. Run with --resume to continue.")
            print_progress(progress)


if __name__ == "__main__":
    main()
