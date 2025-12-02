"""Main email processing workflow using LangGraph.

Orchestrates the email processing pipeline:

Phase 1:
1. Fetch emails from Gmail
2. Categorize using Claude
3. Apply labels
4. Queue for human approval if needed

Phase 2 (Multi-Agent):
1. Categorize email
2. Check importance (always)
3. In parallel:
   - Extract calendar events (if relevant)
   - Detect unsubscribe options (if newsletter/marketing)
4. Route based on confidence and agent results
5. Apply labels or queue for approval
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
from src.agents.importance import check_importance
from src.agents.calendar import extract_calendar_event, should_check_calendar
from src.agents.unsubscribe import detect_unsubscribe, UNSUBSCRIBE_CATEGORIES

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
                email_record.importance_level = final_state.get("importance_level")
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

                        # Apply importance label for high/critical emails
                        importance_level = final_state.get("importance_level")
                        if importance_level in ["critical", "high"]:
                            importance_label = f"Agent/Priority/{importance_level.capitalize()}"
                            self.gmail.apply_label(email_msg.message_id, importance_label)

                    except Exception as e:
                        logger.error(f"Failed to apply label: {e}")

                # Queue unsubscribe if detected
                if final_state.get("unsubscribe_available"):
                    from src.agents.unsubscribe import queue_unsubscribe_if_available
                    # Run async queueing in background (non-blocking)
                    import asyncio
                    asyncio.create_task(queue_unsubscribe_if_available(final_state))

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

    Phase 2 workflow with parallel agent execution:
    START -> categorize -> check_importance -> [parallel: calendar | unsubscribe] -> finalize -> route -> END

    The workflow runs:
    1. Categorization (always)
    2. Importance scoring (always)
    3. Calendar extraction (if calendar-relevant content detected)
    4. Unsubscribe detection (if newsletter/marketing category)
    5. Final routing based on confidence and agent results

    Calendar and unsubscribe agents run in parallel when both are triggered.

    Returns:
        Compiled StateGraph workflow
    """
    workflow = StateGraph(EmailState)

    # Add nodes - Phase 1
    workflow.add_node("categorize", categorize_email)
    workflow.add_node("apply_label", apply_label_node)
    workflow.add_node("queue_approval", queue_approval_node)

    # Add nodes - Phase 2
    workflow.add_node("check_importance", check_importance)
    workflow.add_node("extract_calendar", extract_calendar_event)
    workflow.add_node("detect_unsubscribe", detect_unsubscribe)
    workflow.add_node("finalize", finalize_processing_node)

    # Routing function: After importance, decide which specialized agents to run
    def route_after_importance(
        state: EmailState,
    ) -> Literal["extract_calendar", "detect_unsubscribe", "finalize"]:
        """Route to specialized agents based on email content.

        Calendar and unsubscribe agents are mutually exclusive in routing,
        but the workflow structure allows parallel execution via branches
        if LangGraph supports it in the future.

        Returns the highest-priority agent to run next.
        """
        category = state.get("category", "")

        # Check calendar triggers first (higher priority)
        if should_check_calendar(state):
            return "extract_calendar"

        # Check unsubscribe triggers
        if category in UNSUBSCRIBE_CATEGORIES:
            return "detect_unsubscribe"

        # No specialized processing needed
        return "finalize"

    # Routing function: After calendar, maybe also check unsubscribe
    def route_after_calendar(
        state: EmailState,
    ) -> Literal["detect_unsubscribe", "finalize"]:
        """After calendar extraction, check if unsubscribe also applies."""
        category = state.get("category", "")

        # Unlikely but possible: a newsletter with calendar content
        if category in UNSUBSCRIBE_CATEGORIES:
            return "detect_unsubscribe"

        return "finalize"

    # Final routing based on all agent results
    def route_final(
        state: EmailState,
    ) -> Literal["apply_label", "queue_approval"]:
        """Final routing based on confidence and agent results."""
        if state.get("needs_human_approval", False):
            return "queue_approval"
        return "apply_label"

    # Build graph
    # Phase 1: Categorization
    workflow.add_edge(START, "categorize")

    # Phase 2: Importance (always runs after categorization)
    workflow.add_edge("categorize", "check_importance")

    # Phase 2: Route to specialized agents
    workflow.add_conditional_edges(
        "check_importance",
        route_after_importance,
        {
            "extract_calendar": "extract_calendar",
            "detect_unsubscribe": "detect_unsubscribe",
            "finalize": "finalize",
        },
    )

    # After calendar, possibly also run unsubscribe
    workflow.add_conditional_edges(
        "extract_calendar",
        route_after_calendar,
        {
            "detect_unsubscribe": "detect_unsubscribe",
            "finalize": "finalize",
        },
    )

    # Unsubscribe always goes to finalize
    workflow.add_edge("detect_unsubscribe", "finalize")

    # Finalize routes to final action
    workflow.add_conditional_edges(
        "finalize",
        route_final,
        {
            "apply_label": "apply_label",
            "queue_approval": "queue_approval",
        },
    )

    # Terminal nodes
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

    approval_reasons = []
    if state.get("confidence", 1.0) < get_config().confidence_threshold:
        approval_reasons.append(f"low confidence ({state.get('confidence', 0):.2f})")
    if state.get("calendar_action") == "conflict":
        approval_reasons.append("calendar conflict detected")
    if state.get("approval_type") == "calendar" and state.get("calendar_event"):
        approval_reasons.append("calendar event needs confirmation")

    reason_str = ", ".join(approval_reasons) if approval_reasons else "manual review"

    logger.info(
        f"Email {state['email_id']} queued for approval: "
        f"{state['category']} ({reason_str})"
    )

    return state


def finalize_processing_node(state: EmailState) -> EmailState:
    """Finalize processing after all agents have run.

    Consolidates results from all Phase 2 agents and determines
    final routing (auto-label vs human approval).

    Args:
        state: Current email state with all agent results

    Returns:
        Updated state with final routing decision
    """
    config = get_config()

    # Check if any agent requires human approval
    needs_approval = False
    approval_type = "categorization"

    # Check categorization confidence
    if state.get("confidence", 1.0) < config.confidence_threshold:
        needs_approval = True
        approval_type = "categorization"

    # Check calendar conflicts or low-confidence extraction
    calendar_action = state.get("calendar_action")
    if calendar_action == "conflict":
        needs_approval = True
        approval_type = "calendar"
    elif calendar_action == "extracted":
        calendar_event = state.get("calendar_event")
        if calendar_event:
            # Low confidence extraction
            if calendar_event.get("confidence", 1.0) < 0.8:
                needs_approval = True
                approval_type = "calendar"
            # Long events need confirmation
            elif calendar_event.get("duration_minutes", 0) > 120:
                needs_approval = True
                approval_type = "calendar"

    # Update state with final routing decision
    state["needs_human_approval"] = needs_approval
    if needs_approval:
        state["approval_type"] = approval_type

    # Log summary
    importance = state.get("importance_level", "normal")
    category = state.get("category", "Unknown")

    logger.info(
        f"Finalized email {state['email_id']}: "
        f"category={category}, importance={importance}, "
        f"calendar={calendar_action}, "
        f"unsubscribe={'available' if state.get('unsubscribe_available') else 'none'}, "
        f"approval={'required' if needs_approval else 'auto'}"
    )

    return state
