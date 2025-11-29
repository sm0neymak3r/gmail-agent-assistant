"""Gmail API client with OAuth 2.0 authentication.

Handles email fetching, labeling, and batch operations with rate limiting.
"""

import base64
import logging
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import get_config, GmailConfig

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Parsed email message."""
    message_id: str
    thread_id: str
    from_email: str
    to_emails: list[str]
    subject: str
    body: str
    date: datetime
    snippet: str
    labels: list[str]
    headers: dict[str, str]


class GmailClient:
    """Gmail API client using OAuth 2.0 user tokens.

    Uses refresh tokens to maintain access without user interaction.
    Implements rate limiting and retry logic for API calls.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.labels",
    ]

    def __init__(self, gmail_config: Optional[GmailConfig] = None):
        """Initialize Gmail client with OAuth credentials.

        Args:
            gmail_config: Gmail configuration with OAuth tokens.
                         If None, loads from environment.
        """
        self.config = gmail_config or get_config().gmail
        self._service = None
        self._credentials = None
        self._label_cache: dict[str, str] = {}

    def _get_credentials(self) -> Credentials:
        """Get or refresh OAuth credentials."""
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
            scopes=token_data.get("scopes", self.SCOPES),
        )

        # Refresh if expired
        if self._credentials.expired and self._credentials.refresh_token:
            logger.info("Refreshing expired Gmail OAuth token")
            self._credentials.refresh(Request())

        return self._credentials

    @property
    def service(self):
        """Get or create Gmail API service."""
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build("gmail", "v1", credentials=credentials)
        return self._service

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(HttpError),
    )
    def list_messages(
        self,
        query: str = "",
        max_results: int = 100,
        label_ids: Optional[list[str]] = None,
    ) -> list[dict]:
        """List messages matching query.

        Args:
            query: Gmail search query (e.g., "is:unread", "from:example.com")
            max_results: Maximum number of messages to return (max 500)
            label_ids: Filter by label IDs

        Returns:
            List of message metadata (id, threadId)
        """
        try:
            request_params = {
                "userId": "me",
                "maxResults": min(max_results, 500),
            }
            if query:
                request_params["q"] = query
            if label_ids:
                request_params["labelIds"] = label_ids

            response = self.service.users().messages().list(**request_params).execute()
            messages = response.get("messages", [])

            logger.info(f"Listed {len(messages)} messages matching query: {query}")
            return messages

        except HttpError as e:
            logger.error(f"Gmail API error listing messages: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(HttpError),
    )
    def get_message(self, message_id: str) -> EmailMessage:
        """Get full message details.

        Args:
            message_id: Gmail message ID

        Returns:
            Parsed EmailMessage object
        """
        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            return self._parse_message(message)

        except HttpError as e:
            logger.error(f"Gmail API error getting message {message_id}: {e}")
            raise

    def batch_get_messages(
        self,
        message_ids: list[str],
        batch_size: int = 10,
        max_retries: int = 3,
    ) -> list[EmailMessage]:
        """Batch fetch multiple messages with rate limiting and retry logic.

        Args:
            message_ids: List of message IDs to fetch
            batch_size: Number of messages per batch (default 10 for reliability)
            max_retries: Maximum retry attempts for failed messages

        Returns:
            List of parsed EmailMessage objects
        """
        import time

        all_messages = []
        pending_ids = list(message_ids)
        retry_count = 0

        while pending_ids and retry_count <= max_retries:
            messages = []
            errors = []

            def callback(request_id, response, exception):
                if exception:
                    logger.warning(f"Batch request error for {request_id}: {exception}")
                    errors.append(request_id)
                else:
                    try:
                        messages.append(self._parse_message(response))
                    except Exception as e:
                        logger.error(f"Error parsing message {request_id}: {e}")

            # Process in batches
            total_batches = (len(pending_ids) + batch_size - 1) // batch_size
            for i, start in enumerate(range(0, len(pending_ids), batch_size)):
                batch = self.service.new_batch_http_request(callback=callback)
                batch_ids = pending_ids[start : start + batch_size]

                for msg_id in batch_ids:
                    batch.add(
                        self.service.users()
                        .messages()
                        .get(userId="me", id=msg_id, format="full"),
                        request_id=msg_id,
                    )

                if retry_count == 0:
                    logger.info(f"Fetching batch {i + 1}/{total_batches} ({len(batch_ids)} messages)...")
                batch.execute()

                # Add delay between batches to avoid rate limits
                # Increase delay on retries
                delay = 1.0 + (retry_count * 2.0)
                if i < total_batches - 1:
                    time.sleep(delay)

            all_messages.extend(messages)

            # If there were errors, prepare for retry
            if errors:
                retry_count += 1
                if retry_count <= max_retries:
                    logger.info(f"Retrying {len(errors)} failed messages (attempt {retry_count}/{max_retries})...")
                    pending_ids = errors
                    # Wait before retry
                    time.sleep(2.0 * retry_count)
                else:
                    logger.warning(f"Giving up on {len(errors)} messages after {max_retries} retries")
            else:
                pending_ids = []

        logger.info(f"Batch fetched {len(all_messages)} messages ({len(pending_ids)} failed)")
        return all_messages

    def _parse_message(self, message: dict) -> EmailMessage:
        """Parse Gmail API message into EmailMessage object."""
        headers = {}
        for header in message.get("payload", {}).get("headers", []):
            headers[header["name"].lower()] = header["value"]

        # Parse body
        body = self._extract_body(message.get("payload", {}))

        # Parse date
        date_str = headers.get("date", "")
        try:
            date = parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            date = datetime.utcnow()

        # Parse recipients
        to_emails = []
        if "to" in headers:
            to_emails = [addr.strip() for addr in headers["to"].split(",")]

        return EmailMessage(
            message_id=message["id"],
            thread_id=message.get("threadId", ""),
            from_email=headers.get("from", ""),
            to_emails=to_emails,
            subject=headers.get("subject", "(No Subject)"),
            body=body,
            date=date,
            snippet=message.get("snippet", ""),
            labels=message.get("labelIds", []),
            headers=headers,
        )

    def _extract_body(self, payload: dict) -> str:
        """Extract email body from payload, preferring plain text."""
        body = ""

        # Check for direct body
        if "body" in payload and payload["body"].get("data"):
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
            return body

        # Check parts for multipart messages
        parts = payload.get("parts", [])
        for part in parts:
            mime_type = part.get("mimeType", "")

            # Prefer plain text
            if mime_type == "text/plain" and part.get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                return body

            # Fall back to HTML
            if mime_type == "text/html" and part.get("body", {}).get("data") and not body:
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

            # Recurse into nested parts
            if part.get("parts"):
                nested_body = self._extract_body(part)
                if nested_body:
                    body = nested_body

        return body

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(HttpError),
    )
    def get_or_create_label(self, label_name: str) -> str:
        """Get or create a Gmail label.

        Args:
            label_name: Label name (e.g., "Category/Personal")

        Returns:
            Label ID
        """
        # Check cache
        if label_name in self._label_cache:
            return self._label_cache[label_name]

        # List existing labels
        response = self.service.users().labels().list(userId="me").execute()
        for label in response.get("labels", []):
            self._label_cache[label["name"]] = label["id"]
            if label["name"] == label_name:
                return label["id"]

        # Create new label
        label_body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        created = self.service.users().labels().create(userId="me", body=label_body).execute()
        self._label_cache[label_name] = created["id"]

        logger.info(f"Created Gmail label: {label_name}")
        return created["id"]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(HttpError),
    )
    def apply_label(self, message_id: str, label_name: str) -> None:
        """Apply a label to a message.

        Args:
            message_id: Gmail message ID
            label_name: Label name to apply
        """
        label_id = self.get_or_create_label(label_name)

        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute()

        logger.info(f"Applied label '{label_name}' to message {message_id}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(HttpError),
    )
    def remove_label(self, message_id: str, label_name: str) -> None:
        """Remove a label from a message.

        Args:
            message_id: Gmail message ID
            label_name: Label name to remove
        """
        label_id = self.get_or_create_label(label_name)

        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": [label_id]},
        ).execute()

        logger.info(f"Removed label '{label_name}' from message {message_id}")

    def archive_message(self, message_id: str) -> None:
        """Archive a message (remove from INBOX).

        Args:
            message_id: Gmail message ID
        """
        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["INBOX"]},
        ).execute()

        logger.info(f"Archived message {message_id}")
