"""Calendar Agent for extracting events from emails and detecting conflicts.

Extracts calendar events from emails containing:
- Meetings and appointments
- Reservations (hotel, restaurant, flight)
- Interviews
- Conferences

Phase 2 Scope:
- Single, timed events only
- Location and details extraction
- Conflict detection with existing calendar

Future Enhancements (noted for roadmap):
- Recurring event detection
- All-day events
- Multi-day events
- Timezone detection from email content
"""

import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Literal, Optional

from src.config import get_config
from src.services.anthropic_client import AnthropicClient
from src.services.google_calendar import (
    GoogleCalendarClient,
    MissingCalendarScopeError,
    CalendarConflict,
)
from src.workflows.state import EmailState

logger = logging.getLogger(__name__)


# Categories and keywords that trigger calendar extraction
CALENDAR_CATEGORIES = [
    "Professional/Work",
    "Professional/Recruiters",
    "Important",
]

CALENDAR_KEYWORDS = [
    "meeting", "appointment", "interview", "reservation",
    "flight", "hotel", "conference", "call", "webinar",
    "scheduled", "invite", "calendar", "booking", "confirmation",
]


@dataclass
class CalendarEvent:
    """Extracted calendar event from email.

    Phase 2: Single, timed events with location and details.
    """
    title: str
    start_datetime: str  # ISO 8601 format
    end_datetime: Optional[str]  # ISO 8601 format
    duration_minutes: Optional[int]
    location: Optional[str]
    is_virtual: bool
    virtual_link: Optional[str]  # Zoom, Meet, Teams links
    attendees: list[str]
    description: Optional[str]  # Confirmation numbers, details
    confidence: float

    def to_dict(self) -> dict:
        """Convert to dictionary for state storage."""
        return asdict(self)


def should_check_calendar(state: EmailState) -> bool:
    """Determine if email should be checked for calendar events.

    Args:
        state: Email processing state

    Returns:
        True if calendar extraction should run
    """
    category = state.get("category", "")
    subject = state.get("subject", "").lower()
    body = (state.get("body", "") or "")[:1000].lower()

    # Check if category suggests calendar-relevant content
    if category in CALENDAR_CATEGORIES:
        # For work/recruiter emails, only check if importance is high
        importance = state.get("importance_level", "normal")
        if importance in ["critical", "high"]:
            return True

    # Check for calendar keywords in subject or body
    text = f"{subject} {body}"
    if any(kw in text for kw in CALENDAR_KEYWORDS):
        return True

    return False


def extract_virtual_link(text: str) -> Optional[str]:
    """Extract video conferencing link from text.

    Args:
        text: Email body text

    Returns:
        Video conferencing URL if found
    """
    patterns = [
        r"https://[a-z0-9-]+\.zoom\.us/[^\s<>\"]+",  # Zoom
        r"https://meet\.google\.com/[a-z-]+",  # Google Meet
        r"https://teams\.microsoft\.com/[^\s<>\"]+",  # Microsoft Teams
        r"https://[a-z0-9-]+\.webex\.com/[^\s<>\"]+",  # Webex
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    return None


class CalendarAgent:
    """Agent for extracting calendar events from emails.

    Uses Claude to extract event details and Google Calendar API
    for conflict detection.
    """

    def __init__(
        self,
        anthropic_client: Optional[AnthropicClient] = None,
        calendar_client: Optional[GoogleCalendarClient] = None,
    ):
        """Initialize calendar agent.

        Args:
            anthropic_client: Client for LLM extraction
            calendar_client: Client for calendar conflict detection
        """
        self.anthropic = anthropic_client or AnthropicClient()
        self._calendar_client = calendar_client
        self._calendar_available = None

    @property
    def calendar_client(self) -> Optional[GoogleCalendarClient]:
        """Get calendar client, checking availability.

        Returns:
            Calendar client if scope available, None otherwise
        """
        if self._calendar_client is None:
            try:
                client = GoogleCalendarClient()
                if client.is_available():
                    self._calendar_client = client
                    self._calendar_available = True
                else:
                    self._calendar_available = False
            except Exception as e:
                logger.warning(f"Calendar client unavailable: {e}")
                self._calendar_available = False

        return self._calendar_client if self._calendar_available else None

    def extract_calendar_event(self, state: EmailState) -> EmailState:
        """Extract calendar event from email and check for conflicts.

        Args:
            state: Current email processing state

        Returns:
            Updated state with calendar event info
        """
        # Check if we should process this email
        if not should_check_calendar(state):
            logger.debug(f"Skipping calendar extraction for: {state['subject'][:50]}")
            state["calendar_event"] = None
            state["calendar_conflicts"] = []
            state["calendar_action"] = "skipped"
            state["processing_step"] = "calendar_checked"
            return state

        logger.info(f"Extracting calendar event from: {state['subject'][:50]}...")

        # Extract event using LLM
        event = self._extract_event_with_llm(state)

        if event is None:
            state["calendar_event"] = None
            state["calendar_conflicts"] = []
            state["calendar_action"] = "no_event"
            state["processing_step"] = "calendar_checked"
            return state

        # Store extracted event
        state["calendar_event"] = event.to_dict()

        # Check for conflicts if calendar client available
        conflicts = []
        if self.calendar_client and event.start_datetime:
            try:
                conflicts = self._check_conflicts(event)
                state["calendar_conflicts"] = [
                    {"start": c.start.isoformat(), "end": c.end.isoformat()}
                    for c in conflicts
                ]
            except MissingCalendarScopeError:
                logger.warning("Calendar scope not available, skipping conflict check")
                state["calendar_conflicts"] = []
            except Exception as e:
                logger.error(f"Error checking conflicts: {e}")
                state["calendar_conflicts"] = []
        else:
            state["calendar_conflicts"] = []

        # Determine action based on confidence and conflicts
        if conflicts:
            state["calendar_action"] = "conflict"
            state["needs_human_approval"] = True
            state["approval_type"] = "calendar"
        elif event.confidence < 0.8:
            state["calendar_action"] = "extracted"
            state["needs_human_approval"] = True
            state["approval_type"] = "calendar"
        elif event.duration_minutes and event.duration_minutes > 120:
            # Events > 2 hours need confirmation
            state["calendar_action"] = "extracted"
            state["needs_human_approval"] = True
            state["approval_type"] = "calendar"
        else:
            state["calendar_action"] = "extracted"

        state["processing_step"] = "calendar_checked"

        logger.info(
            f"Calendar event extracted: {event.title} "
            f"(confidence: {event.confidence:.2f}, conflicts: {len(conflicts)})"
        )

        return state

    def _extract_event_with_llm(self, state: EmailState) -> Optional[CalendarEvent]:
        """Use Claude to extract event details from email.

        Args:
            state: Email state

        Returns:
            Extracted CalendarEvent or None
        """
        # Check for virtual meeting link first
        body = state.get("body", "") or ""
        virtual_link = extract_virtual_link(body)

        system_prompt = """You are an expert at extracting calendar event details from emails.
Extract event information including date, time, location, and any relevant details.

IMPORTANT:
- Only extract if there is a clear, specific event with a date/time
- For dates, convert to ISO 8601 format (YYYY-MM-DDTHH:MM:SS)
- Assume the user's local timezone if not specified
- Include confirmation numbers, booking references in the description
- Set is_virtual to true for video calls, webinars, online meetings

Respond with ONLY a valid JSON object in this format:
{
  "title": "Event title",
  "start_datetime": "2025-01-15T14:00:00",
  "end_datetime": "2025-01-15T15:00:00",
  "duration_minutes": 60,
  "location": "123 Main St, City" or null,
  "is_virtual": false,
  "virtual_link": null or "https://...",
  "attendees": ["email@example.com"],
  "description": "Confirmation #12345, any other details",
  "confidence": 0.85
}

If no clear event is found, respond with: {"no_event": true}

Confidence guidelines:
- 0.9-1.0: Clear date/time, specific event
- 0.7-0.9: Date/time present but some ambiguity
- 0.5-0.7: Probable event, missing some details
- Below 0.5: Very uncertain"""

        user_prompt = f"""Extract calendar event from this email:

Subject: {state.get('subject', '')}
From: {state.get('from_email', '')}
Date: {state.get('date', '')}

Body:
{body[:5000]}

{"Note: Video link detected: " + virtual_link if virtual_link else ""}

Respond with ONLY a JSON object."""

        try:
            response = self.anthropic.client.messages.create(
                model=self.anthropic.config.fast_model,
                max_tokens=500,
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
            )

            content = response.content[0].text.strip()

            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)

            if result.get("no_event"):
                return None

            # Add detected virtual link if not in response
            if virtual_link and not result.get("virtual_link"):
                result["virtual_link"] = virtual_link
                result["is_virtual"] = True

            return CalendarEvent(
                title=result.get("title", "Untitled Event"),
                start_datetime=result.get("start_datetime"),
                end_datetime=result.get("end_datetime"),
                duration_minutes=result.get("duration_minutes"),
                location=result.get("location"),
                is_virtual=result.get("is_virtual", False),
                virtual_link=result.get("virtual_link"),
                attendees=result.get("attendees", []),
                description=result.get("description"),
                confidence=float(result.get("confidence", 0.5)),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse calendar extraction response: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting calendar event: {e}")
            raise

    def _check_conflicts(self, event: CalendarEvent) -> list[CalendarConflict]:
        """Check for calendar conflicts.

        Args:
            event: Extracted event

        Returns:
            List of conflicting time periods
        """
        if not event.start_datetime:
            return []

        try:
            start = datetime.fromisoformat(event.start_datetime)

            if event.end_datetime:
                end = datetime.fromisoformat(event.end_datetime)
            elif event.duration_minutes:
                end = start + timedelta(minutes=event.duration_minutes)
            else:
                # Default to 1 hour if no end time
                end = start + timedelta(hours=1)

            return self.calendar_client.check_conflicts(start, end)

        except ValueError as e:
            logger.warning(f"Invalid datetime format: {e}")
            return []


# Standalone function for LangGraph node
def extract_calendar_event(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node function for calendar event extraction.

    Args:
        state: Email state dictionary

    Returns:
        Updated state dictionary

    Raises:
        Exception: Re-raises any exception to trigger workflow retry
    """
    try:
        agent = CalendarAgent()
        return agent.extract_calendar_event(state)
    except Exception as e:
        logger.error(f"Calendar agent failed: {e}")
        # Re-raise to trigger workflow retry per user requirement
        raise
