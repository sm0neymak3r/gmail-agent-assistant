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
        "labeled",
        "pending_approval",
        "completed",
        "failed",
    ]

    # Classification results
    category: str
    confidence: float
    reasoning: str

    # Importance detection (Phase 2)
    importance_level: Literal["critical", "high", "normal", "low"]
    importance_score: float
    action_items: list[dict]

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
        category="",
        confidence=0.0,
        reasoning="",
        importance_level="normal",
        importance_score=0.5,
        action_items=[],
        needs_human_approval=False,
        approval_type="categorization",
        error=None,
        retry_count=0,
        fetched_at=datetime.utcnow().isoformat(),
        processed_at="",
        messages=[],
    )
