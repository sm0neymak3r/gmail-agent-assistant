"""Main email processing workflow using LangGraph.

Orchestrates the email processing pipeline:
1. Fetch emails from Gmail
2. Categorize using Claude
3. Apply labels
4. Queue for human approval if needed
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.config import get_config
from src.models import Email, Checkpoint, ProcessingLog, get_async_session
from src.services.gmail_client import GmailClient, EmailMessage
from src.services.anthropic_client import AnthropicClient
from src.workflows.state import EmailState, create_initial_state
from src.agents.categorization import categorize_email

logger = logging.getLogger(__name__)


def to_naive_utc(dt: datetime) -> datetime:
    """Convert timezone-aware datetime to naive UTC datetime for database storage."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


class EmailProcessor:
    """Main email processing orchestrator.

    Manages the LangGraph workflow for processing emails through:
    - Fetching from Gmail
    - Categorization via Claude
    - Labeling in Gmail
    - Human approval queue
    """

    def __init__(
        self,
        gmail_client: GmailClient | None = None,
        anthropic_client: AnthropicClient | None = None,
    ):
        """Initialize email processor.

        Args:
            gmail_client: Gmail API client
            anthropic_client: Anthropic API client
        """
        self.config = get_config()
        self.gmail = gmail_client or GmailClient()
        self.anthropic = anthropic_client or AnthropicClient()
        self._workflow = None

    @property
    def workflow(self):
        """Get or create the LangGraph workflow."""
        if self._workflow is None:
            self._workflow = create_workflow()
        return self._workflow

    async def process_batch(
        self,
        query: str = "is:unread",
        max_emails: int = 100,
    ) -> dict[str, Any]:
        """Process a batch of emails.

        Args:
            query: Gmail search query
            max_emails: Maximum emails to process

        Returns:
            Processing summary with counts and errors
        """
        logger.info(f"Starting batch processing: query='{query}', max={max_emails}")
        start_time = datetime.utcnow()

        results = {
            "processed": 0,
            "categorized": 0,
            "pending_approval": 0,
            "labeled": 0,
            "errors": 0,
            "error_details": [],
        }

        try:
            # Fetch message list
            messages = self.gmail.list_messages(query=query, max_results=max_emails)
            logger.info(f"Found {len(messages)} messages to process")

            if not messages:
                return results

            # Batch fetch full messages
            message_ids = [m["id"] for m in messages]
            full_messages = self.gmail.batch_get_messages(message_ids)

            # Process each message
            for email_msg in full_messages:
                try:
                    result = await self.process_single_email(email_msg)
                    results["processed"] += 1

                    if result.get("category"):
                        results["categorized"] += 1

                    if result.get("needs_human_approval"):
                        results["pending_approval"] += 1

                    if result.get("processing_step") == "labeled":
                        results["labeled"] += 1

                except Exception as e:
                    logger.error(f"Error processing email {email_msg.message_id}: {e}")
                    results["errors"] += 1
                    results["error_details"].append({
                        "message_id": email_msg.message_id,
                        "error": str(e),
                    })

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Batch complete: {results['processed']} processed, "
                f"{results['errors']} errors in {elapsed:.1f}s"
            )

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            results["error_details"].append({"batch_error": str(e)})

        return results

    async def process_single_email(self, email_msg: EmailMessage) -> dict[str, Any]:
        """Process a single email through the workflow.

        Args:
            email_msg: Parsed email message

        Returns:
            Final state dictionary
        """
        async_session = get_async_session()

        async with async_session() as session:
            # Check idempotency - skip if already processed
            existing = await session.execute(
                select(Email).where(Email.message_id == email_msg.message_id)
            )
            if existing.scalar_one_or_none():
                logger.info(f"Skipping already processed email: {email_msg.message_id}")
                return {"status": "already_processed", "message_id": email_msg.message_id}

            # Create initial state
            email_id = str(uuid.uuid4())
            state = create_initial_state(
                email_id=email_id,
                message_id=email_msg.message_id,
                thread_id=email_msg.thread_id,
                from_email=email_msg.from_email,
                to_emails=email_msg.to_emails,
                subject=email_msg.subject,
                body=email_msg.body,
                date=email_msg.date,
                headers=email_msg.headers,
                snippet=email_msg.snippet,
                labels=email_msg.labels,
            )

            # Insert email record
            email_record = Email(
                email_id=email_id,
                message_id=email_msg.message_id,
                thread_id=email_msg.thread_id,
                from_email=email_msg.from_email,
                to_emails=email_msg.to_emails,
                subject=email_msg.subject,
                body=email_msg.body,
                date=to_naive_utc(email_msg.date),
                status="processing",
            )
            session.add(email_record)
            await session.commit()

            # Run workflow
            try:
                # Run through LangGraph workflow
                final_state = self.workflow.invoke(state)

                # Update email record with results
                email_record.category = final_state.get("category")
                email_record.confidence = final_state.get("confidence")
                email_record.status = (
                    "pending_approval"
                    if final_state.get("needs_human_approval")
                    else "labeled"
                )
                email_record.processed_at = datetime.utcnow()

                # Apply Gmail label if confidence is high enough
                if not final_state.get("needs_human_approval") and final_state.get("category"):
                    try:
                        label_name = f"Agent/{final_state['category']}"
                        self.gmail.apply_label(email_msg.message_id, label_name)
                        final_state["processing_step"] = "labeled"
                        email_record.status = "labeled"
                    except Exception as e:
                        logger.error(f"Failed to apply label: {e}")

                # Save checkpoint
                checkpoint = Checkpoint(
                    email_id=email_id,
                    step=final_state.get("processing_step", "completed"),
                    state_json=dict(final_state),
                )
                session.add(checkpoint)

                # Log processing - compute latency from email date to now
                # Only track latency for recent emails (< 7 days) to avoid int32 overflow
                latency_ms = None
                if email_msg.date:
                    now_utc = datetime.now(timezone.utc)
                    email_date = email_msg.date if email_msg.date.tzinfo else email_msg.date.replace(tzinfo=timezone.utc)
                    age_seconds = (now_utc - email_date).total_seconds()
                    # Only log latency for emails < 7 days old (to avoid int32 overflow)
                    if age_seconds < 7 * 24 * 3600:
                        latency_ms = int(age_seconds * 1000)

                log_entry = ProcessingLog(
                    email_id=email_id,
                    agent="email_processor",
                    action="process_email",
                    status="success",
                    latency_ms=latency_ms,
                )
                session.add(log_entry)

                await session.commit()
                return dict(final_state)

            except Exception as e:
                logger.error(f"Workflow error for {email_id}: {e}")
                email_record.status = "failed"
                email_record.processed_at = datetime.utcnow()

                # Log error
                log_entry = ProcessingLog(
                    email_id=email_id,
                    agent="email_processor",
                    action="process_email",
                    status="error",
                    error=str(e),
                )
                session.add(log_entry)

                await session.commit()
                raise


def create_workflow() -> StateGraph:
    """Create the LangGraph workflow for email processing.

    Phase 1 workflow:
    START -> categorize -> route -> [apply_label | queue_approval] -> END

    Returns:
        Compiled StateGraph workflow
    """
    workflow = StateGraph(EmailState)

    # Add nodes
    workflow.add_node("categorize", categorize_email)
    workflow.add_node("apply_label", apply_label_node)
    workflow.add_node("queue_approval", queue_approval_node)

    # Define routing logic
    def route_after_categorization(state: EmailState) -> Literal["apply_label", "queue_approval"]:
        """Route based on confidence threshold."""
        if state.get("needs_human_approval", False):
            return "queue_approval"
        return "apply_label"

    # Build graph
    workflow.add_edge(START, "categorize")
    workflow.add_conditional_edges(
        "categorize",
        route_after_categorization,
        {
            "apply_label": "apply_label",
            "queue_approval": "queue_approval",
        },
    )
    workflow.add_edge("apply_label", END)
    workflow.add_edge("queue_approval", END)

    # Compile without checkpointing for now
    # TODO: Add PostgresSaver checkpointing
    return workflow.compile()


def apply_label_node(state: EmailState) -> EmailState:
    """Apply Gmail label to email.

    Args:
        state: Current email state

    Returns:
        Updated state
    """
    state["processing_step"] = "labeled"
    state["processed_at"] = datetime.utcnow().isoformat()

    logger.info(
        f"Email {state['email_id']} labeled as {state['category']} "
        f"(confidence: {state['confidence']:.2f})"
    )

    return state


def queue_approval_node(state: EmailState) -> EmailState:
    """Queue email for human approval.

    Args:
        state: Current email state

    Returns:
        Updated state
    """
    state["processing_step"] = "pending_approval"
    state["processed_at"] = datetime.utcnow().isoformat()

    logger.info(
        f"Email {state['email_id']} queued for approval: "
        f"{state['category']} (confidence: {state['confidence']:.2f})"
    )

    return state
