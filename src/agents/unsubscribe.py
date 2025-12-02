"""Unsubscribe Agent for detecting and managing email unsubscribe options.

Detects unsubscribe options from email headers (RFC 2369, RFC 8058):
- List-Unsubscribe header: mailto: or http: links
- List-Unsubscribe-Post header: Indicates RFC 8058 one-click support

Note: Body link scanning is intentionally not implemented due to reliability concerns.
This is noted as a future enhancement for the manual approval CLI.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import UnsubscribeQueue, get_async_session
from src.workflows.state import EmailState

logger = logging.getLogger(__name__)


# Categories that trigger unsubscribe detection
UNSUBSCRIBE_CATEGORIES = [
    "Newsletters/Subscriptions",
    "Marketing/Promotions",
]


@dataclass
class UnsubscribeMethod:
    """Detected unsubscribe method."""
    method: Literal["one-click", "mailto", "http", "none"]
    url: Optional[str] = None
    email: Optional[str] = None
    confidence: float = 0.0


def parse_list_unsubscribe_header(header_value: str) -> list[dict]:
    """Parse List-Unsubscribe header value.

    The header contains angle-bracket enclosed URIs, comma-separated.
    Example: <mailto:unsubscribe@example.com>, <https://example.com/unsubscribe>

    Args:
        header_value: Raw header value

    Returns:
        List of parsed URIs with type (mailto or http)
    """
    if not header_value:
        return []

    results = []

    # Extract angle-bracket enclosed values
    pattern = r"<([^>]+)>"
    matches = re.findall(pattern, header_value)

    for uri in matches:
        uri = uri.strip()

        if uri.startswith("mailto:"):
            # Parse mailto URI
            email = uri[7:]  # Remove "mailto:"
            # Handle mailto parameters (e.g., mailto:unsubscribe@example.com?subject=unsubscribe)
            if "?" in email:
                email = email.split("?")[0]
            results.append({
                "type": "mailto",
                "email": email,
                "uri": uri,
            })

        elif uri.startswith("http://") or uri.startswith("https://"):
            results.append({
                "type": "http",
                "url": uri,
                "uri": uri,
            })

    return results


def detect_unsubscribe_method(headers: dict[str, str]) -> UnsubscribeMethod:
    """Detect the best unsubscribe method from email headers.

    Priority:
    1. RFC 8058 one-click (List-Unsubscribe-Post + https List-Unsubscribe)
    2. HTTP unsubscribe link
    3. Mailto unsubscribe

    Args:
        headers: Email headers dictionary (lowercase keys)

    Returns:
        UnsubscribeMethod with best available method
    """
    list_unsub = headers.get("list-unsubscribe", "")
    list_unsub_post = headers.get("list-unsubscribe-post", "")

    if not list_unsub:
        return UnsubscribeMethod(method="none", confidence=0.0)

    parsed = parse_list_unsubscribe_header(list_unsub)

    if not parsed:
        return UnsubscribeMethod(method="none", confidence=0.0)

    # Check for RFC 8058 one-click support
    # Requires: List-Unsubscribe-Post header AND https URL in List-Unsubscribe
    has_one_click = bool(list_unsub_post and "List-Unsubscribe=One-Click" in list_unsub_post)

    http_links = [p for p in parsed if p["type"] == "http"]
    mailto_links = [p for p in parsed if p["type"] == "mailto"]

    # One-click requires HTTPS
    https_links = [p for p in http_links if p["url"].startswith("https://")]

    if has_one_click and https_links:
        return UnsubscribeMethod(
            method="one-click",
            url=https_links[0]["url"],
            confidence=0.95,
        )

    # Prefer HTTPS over HTTP
    if https_links:
        return UnsubscribeMethod(
            method="http",
            url=https_links[0]["url"],
            confidence=0.90,
        )

    if http_links:
        return UnsubscribeMethod(
            method="http",
            url=http_links[0]["url"],
            confidence=0.85,
        )

    if mailto_links:
        return UnsubscribeMethod(
            method="mailto",
            email=mailto_links[0]["email"],
            confidence=0.80,
        )

    return UnsubscribeMethod(method="none", confidence=0.0)


def extract_sender_domain(from_email: str) -> str:
    """Extract domain from sender email address.

    Args:
        from_email: Full from header (may include name)

    Returns:
        Domain portion of email
    """
    # Handle "Name <email@domain.com>" format
    match = re.search(r"<([^>]+)>", from_email)
    if match:
        email = match.group(1)
    else:
        email = from_email

    if "@" in email:
        return email.split("@")[1].lower()

    return ""


class UnsubscribeAgent:
    """Agent for detecting unsubscribe options and queueing recommendations.

    Only processes emails in newsletter/marketing categories.
    Uses header-based detection for reliability.
    """

    def __init__(self):
        """Initialize unsubscribe agent."""
        pass

    def detect_unsubscribe(self, state: EmailState) -> EmailState:
        """Detect unsubscribe options and update state.

        Args:
            state: Current email processing state

        Returns:
            Updated state with unsubscribe info
        """
        category = state.get("category", "")

        # Only process relevant categories
        if category not in UNSUBSCRIBE_CATEGORIES:
            logger.debug(f"Skipping unsubscribe detection for category: {category}")
            state["unsubscribe_available"] = False
            state["unsubscribe_method"] = None
            state["processing_step"] = "unsubscribe_checked"
            return state

        logger.info(f"Detecting unsubscribe for: {state['subject'][:50]}...")

        headers = state.get("headers", {})
        method = detect_unsubscribe_method(headers)

        state["unsubscribe_available"] = method.method != "none"
        state["unsubscribe_method"] = method.method if method.method != "none" else None
        state["unsubscribe_url"] = method.url
        state["unsubscribe_email"] = method.email
        state["unsubscribe_queued"] = False
        state["processing_step"] = "unsubscribe_checked"

        if method.method != "none":
            logger.info(
                f"Unsubscribe detected: {method.method} "
                f"(confidence: {method.confidence:.2f})"
            )

        return state

    async def queue_for_review(
        self,
        state: EmailState,
        session: AsyncSession,
    ) -> None:
        """Queue unsubscribe option for user review.

        Args:
            state: Email state with unsubscribe info
            session: Database session
        """
        if not state.get("unsubscribe_available"):
            return

        from_email = state.get("from_email", "")
        sender_domain = extract_sender_domain(from_email)

        # Create queue entry
        queue_entry = UnsubscribeQueue(
            email_id=state.get("email_id"),
            sender=from_email,
            method=state.get("unsubscribe_method", "unknown"),
            unsubscribe_link=state.get("unsubscribe_url") or state.get("unsubscribe_email"),
            status="pending",
        )

        session.add(queue_entry)
        state["unsubscribe_queued"] = True

        logger.info(f"Queued unsubscribe for review: {sender_domain}")


# Standalone function for LangGraph node
def detect_unsubscribe(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node function for unsubscribe detection.

    Args:
        state: Email state dictionary

    Returns:
        Updated state dictionary

    Raises:
        Exception: Re-raises any exception to trigger workflow retry
    """
    try:
        agent = UnsubscribeAgent()
        return agent.detect_unsubscribe(state)
    except Exception as e:
        logger.error(f"Unsubscribe agent failed: {e}")
        # Re-raise to trigger workflow retry per user requirement
        raise


async def queue_unsubscribe_if_available(state: EmailState) -> None:
    """Queue unsubscribe for review if available.

    Called after workflow completion to persist queue entry.

    Args:
        state: Final email state
    """
    if not state.get("unsubscribe_available"):
        return

    async_session = get_async_session()
    async with async_session() as session:
        agent = UnsubscribeAgent()
        await agent.queue_for_review(state, session)
        await session.commit()
