"""Google Calendar API client for event conflict detection.

Provides calendar integration for the Calendar Agent:
- FreeBusy API for efficient conflict detection
- Primary calendar timezone retrieval
- Graceful degradation when calendar scope not granted

Note: Requires calendar.readonly scope to be added to OAuth consent.
If the scope is not available, the client will raise MissingCalendarScopeError.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import get_config, GmailConfig

logger = logging.getLogger(__name__)


class MissingCalendarScopeError(Exception):
    """Raised when calendar scope is not available in OAuth token."""
    pass


@dataclass
class CalendarConflict:
    """A conflicting calendar event."""
    start: datetime
    end: datetime
    summary: Optional[str] = None
    event_id: Optional[str] = None


class GoogleCalendarClient:
    """Google Calendar API client for conflict detection.

    Uses the same OAuth credentials as Gmail but requires additional
    calendar.readonly scope. If the scope is not available, operations
    will raise MissingCalendarScopeError.
    """

    REQUIRED_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

    def __init__(self, gmail_config: Optional[GmailConfig] = None):
        """Initialize Calendar client with OAuth credentials.

        Args:
            gmail_config: Gmail configuration with OAuth tokens.
                         If None, loads from environment.

        Raises:
            MissingCalendarScopeError: If calendar scope not in token
        """
        self.config = gmail_config or get_config().gmail
        self._service = None
        self._credentials = None
        self._timezone = None
        self._has_scope = None

    def _check_scope(self) -> bool:
        """Check if calendar scope is available.

        Returns:
            True if scope is available
        """
        if self._has_scope is not None:
            return self._has_scope

        token_data = self.config.user_token
        scopes = token_data.get("scopes", [])

        self._has_scope = self.REQUIRED_SCOPE in scopes
        return self._has_scope

    def _get_credentials(self) -> Credentials:
        """Get or refresh OAuth credentials.

        Returns:
            Valid credentials

        Raises:
            MissingCalendarScopeError: If calendar scope not available
        """
        if not self._check_scope():
            raise MissingCalendarScopeError(
                f"Calendar scope '{self.REQUIRED_SCOPE}' not available. "
                "Please re-run OAuth flow with calendar scope enabled."
            )

        if self._credentials is not None and self._credentials.valid:
            return self._credentials

        token_data = self.config.user_token
        if not token_data:
            raise ValueError("Gmail user token not configured")

        self._credentials = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes", []),
        )

        # Refresh if expired
        if self._credentials.expired and self._credentials.refresh_token:
            logger.info("Refreshing expired OAuth token")
            self._credentials.refresh(Request())

        return self._credentials

    @property
    def service(self):
        """Get or create Calendar API service.

        Raises:
            MissingCalendarScopeError: If calendar scope not available
        """
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build("calendar", "v3", credentials=credentials)
        return self._service

    def is_available(self) -> bool:
        """Check if calendar integration is available.

        Returns:
            True if calendar scope is granted
        """
        return self._check_scope()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(HttpError),
    )
    def get_timezone(self) -> str:
        """Get the primary calendar's timezone.

        Returns:
            Timezone string (e.g., "America/New_York")
        """
        if self._timezone:
            return self._timezone

        try:
            settings = self.service.settings().get(setting="timezone").execute()
            self._timezone = settings.get("value", "UTC")
            return self._timezone
        except HttpError as e:
            logger.warning(f"Could not get calendar timezone: {e}")
            return "UTC"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(HttpError),
    )
    def check_conflicts(
        self,
        start: datetime,
        end: datetime,
        buffer_minutes: int = 0,
    ) -> list[CalendarConflict]:
        """Check for conflicting events using FreeBusy API.

        Uses the FreeBusy API for efficient conflict detection rather than
        listing all events. This is more privacy-preserving and faster.

        Args:
            start: Event start time (should be timezone-aware or UTC)
            end: Event end time (should be timezone-aware or UTC)
            buffer_minutes: Optional buffer time before/after event
                           (for future configurability)

        Returns:
            List of conflicting time periods
        """
        # Apply buffer if specified
        if buffer_minutes > 0:
            buffer = timedelta(minutes=buffer_minutes)
            start = start - buffer
            end = end + buffer

        # Ensure we have ISO format with Z suffix for UTC
        if start.tzinfo is None:
            start_str = start.isoformat() + "Z"
        else:
            start_str = start.isoformat()

        if end.tzinfo is None:
            end_str = end.isoformat() + "Z"
        else:
            end_str = end.isoformat()

        body = {
            "timeMin": start_str,
            "timeMax": end_str,
            "items": [{"id": "primary"}],
        }

        try:
            result = self.service.freebusy().query(body=body).execute()

            busy_times = result.get("calendars", {}).get("primary", {}).get("busy", [])

            conflicts = []
            for busy in busy_times:
                conflict = CalendarConflict(
                    start=datetime.fromisoformat(busy["start"].replace("Z", "+00:00")),
                    end=datetime.fromisoformat(busy["end"].replace("Z", "+00:00")),
                )
                conflicts.append(conflict)

            logger.info(f"Found {len(conflicts)} calendar conflicts")
            return conflicts

        except HttpError as e:
            logger.error(f"Calendar API error: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(HttpError),
    )
    def get_events_in_range(
        self,
        start: datetime,
        end: datetime,
        max_results: int = 10,
    ) -> list[dict]:
        """Get detailed events in a time range.

        Unlike check_conflicts (which uses FreeBusy), this returns
        full event details including summary and event ID.

        Args:
            start: Range start time
            end: Range end time
            max_results: Maximum events to return

        Returns:
            List of event dictionaries
        """
        # Ensure we have ISO format with Z suffix for UTC
        if start.tzinfo is None:
            start_str = start.isoformat() + "Z"
        else:
            start_str = start.isoformat()

        if end.tzinfo is None:
            end_str = end.isoformat() + "Z"
        else:
            end_str = end.isoformat()

        try:
            result = self.service.events().list(
                calendarId="primary",
                timeMin=start_str,
                timeMax=end_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events = result.get("items", [])

            # Convert to standardized format
            formatted_events = []
            for event in events:
                start_time = event.get("start", {})
                end_time = event.get("end", {})

                formatted_events.append({
                    "id": event.get("id"),
                    "summary": event.get("summary", "(No title)"),
                    "start": start_time.get("dateTime") or start_time.get("date"),
                    "end": end_time.get("dateTime") or end_time.get("date"),
                    "location": event.get("location"),
                    "html_link": event.get("htmlLink"),
                })

            return formatted_events

        except HttpError as e:
            logger.error(f"Calendar API error: {e}")
            raise
