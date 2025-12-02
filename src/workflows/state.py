"""State definitions for LangGraph email processing workflow."""

from datetime import datetime
from typing import Annotated, Literal, TypedDict, Optional


def merge_messages(left: list, right: list) -> list:
    """Merge two message lists, appending right to left."""
    return left + right


class EmailState(TypedDict, total=False):
    """State for email processing workflow.

    This state is passed between LangGraph nodes and checkpointed
    for crash recovery.

    Phase 1: Basic categorization with confidence-based routing
    Phase 2: Importance scoring, calendar extraction, unsubscribe detection
    """
    # Email identifiers
    email_id: str
    message_id: str
    thread_id: str

    # Email content
    from_email: str
    to_emails: list[str]
    subject: str
    body: str
    date: str
    headers: dict[str, str]
    snippet: str
    labels: list[str]

    # Processing state
    processing_step: Literal[
        "fetched",
        "categorized",
        "importance_checked",
        "calendar_checked",
        "unsubscribe_checked",
        "labeled",
        "pending_approval",
        "completed",
        "failed",
    ]

    # Classification results (Phase 1)
    category: str
    confidence: float
    reasoning: str

    # Importance detection (Phase 2)
    importance_level: Literal["critical", "high", "normal", "low"]
    importance_score: float
    importance_factors: dict[str, float]  # Individual factor scores for debugging
    action_items: list[str]  # Extracted action items from email

    # Calendar extraction (Phase 2)
    calendar_event: Optional[dict]  # Extracted event: {title, start, end, location, ...}
    calendar_conflicts: list[dict]  # Conflicting existing events
    calendar_action: Literal["extracted", "conflict", "skipped", "no_event"]

    # Unsubscribe detection (Phase 2)
    unsubscribe_available: bool
    unsubscribe_method: Optional[Literal["one-click", "mailto", "http", "none"]]
    unsubscribe_url: Optional[str]
    unsubscribe_email: Optional[str]
    unsubscribe_queued: bool

    # Human approval
    needs_human_approval: bool
    approval_type: Literal["categorization", "importance_rule", "unsubscribe", "calendar"]

    # Error handling
    error: Optional[str]
    retry_count: int

    # Timestamps
    fetched_at: str
    processed_at: str

    # Messages for LangGraph (using Annotated for proper merging)
    messages: Annotated[list, merge_messages]


def create_initial_state(
    email_id: str,
    message_id: str,
    thread_id: str,
    from_email: str,
    to_emails: list[str],
    subject: str,
    body: str,
    date: datetime,
    headers: dict[str, str] | None = None,
    snippet: str = "",
    labels: list[str] | None = None,
) -> EmailState:
    """Create initial state for email processing.

    Args:
        email_id: Unique email ID (can be same as message_id)
        message_id: Gmail message ID
        thread_id: Gmail thread ID
        from_email: Sender email address
        to_emails: List of recipient addresses
        subject: Email subject
        body: Email body text
        date: Email date
        headers: Email headers dictionary
        snippet: Email snippet/preview
        labels: Gmail label IDs

    Returns:
        Initial EmailState dictionary
    """
    return EmailState(
        email_id=email_id,
        message_id=message_id,
        thread_id=thread_id,
        from_email=from_email,
        to_emails=to_emails,
        subject=subject,
        body=body,
        date=date.isoformat() if isinstance(date, datetime) else date,
        headers=headers or {},
        snippet=snippet,
        labels=labels or [],
        processing_step="fetched",
        # Phase 1: Categorization
        category="",
        confidence=0.0,
        reasoning="",
        # Phase 2: Importance
        importance_level="normal",
        importance_score=0.5,
        importance_factors={},
        action_items=[],
        # Phase 2: Calendar
        calendar_event=None,
        calendar_conflicts=[],
        calendar_action="no_event",
        # Phase 2: Unsubscribe
        unsubscribe_available=False,
        unsubscribe_method=None,
        unsubscribe_url=None,
        unsubscribe_email=None,
        unsubscribe_queued=False,
        # Human approval
        needs_human_approval=False,
        approval_type="categorization",
        # Error handling
        error=None,
        retry_count=0,
        # Timestamps
        fetched_at=datetime.utcnow().isoformat(),
        processed_at="",
        messages=[],
    )
