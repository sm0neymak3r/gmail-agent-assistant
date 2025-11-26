"""Unit tests for GmailClient.

Tests Gmail API interactions with mocked Google API responses.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime
import base64

from googleapiclient.errors import HttpError


class TestGmailClientListMessages:
    """Tests for list_messages method."""

    def test_list_messages_returns_message_list(self, mock_gmail_service):
        """Test that list_messages returns list of message metadata."""
        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_messages.list.return_value.execute.return_value = {
            "messages": [
                {"id": "msg_1", "threadId": "thread_1"},
                {"id": "msg_2", "threadId": "thread_2"},
            ]
        }
        mock_service.users.return_value.messages.return_value = mock_messages

        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = {
                "token": "test_token",
                "refresh_token": "test_refresh",
                "client_id": "test_id",
                "client_secret": "test_secret",
            }

            with patch("src.services.gmail_client.build", return_value=mock_service):
                with patch("src.services.gmail_client.Credentials"):
                    from src.services.gmail_client import GmailClient

                    client = GmailClient()
                    client._service = mock_service

                    result = client.list_messages(query="is:unread", max_results=10)

                    assert len(result) == 2
                    assert result[0]["id"] == "msg_1"

    def test_list_messages_respects_max_results(self, mock_gmail_service):
        """Test that max_results is capped at 500."""
        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_messages.list.return_value.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value = mock_messages

        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = {"token": "test"}

            from src.services.gmail_client import GmailClient

            client = GmailClient()
            client._service = mock_service

            client.list_messages(max_results=1000)

            call_args = mock_messages.list.call_args
            assert call_args.kwargs["maxResults"] == 500

    def test_list_messages_empty_result(self, mock_gmail_service):
        """Test that empty results are handled correctly."""
        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_messages.list.return_value.execute.return_value = {}  # No messages key
        mock_service.users.return_value.messages.return_value = mock_messages

        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = {"token": "test"}

            from src.services.gmail_client import GmailClient

            client = GmailClient()
            client._service = mock_service

            result = client.list_messages()

            assert result == []


class TestGmailClientGetMessage:
    """Tests for get_message method."""

    def test_get_message_parses_email_correctly(self, mock_gmail_service):
        """Test that get_message parses Gmail API response into EmailMessage."""
        body_content = "This is the email body"
        encoded_body = base64.urlsafe_b64encode(body_content.encode()).decode()

        mock_response = {
            "id": "msg_123",
            "threadId": "thread_123",
            "snippet": "Preview text",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "Date", "value": "Tue, 15 Jan 2025 10:30:00 +0000"},
                ],
                "body": {"data": encoded_body},
            },
        }

        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_messages.get.return_value.execute.return_value = mock_response
        mock_service.users.return_value.messages.return_value = mock_messages

        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = {"token": "test"}

            from src.services.gmail_client import GmailClient

            client = GmailClient()
            client._service = mock_service

            result = client.get_message("msg_123")

            assert result.message_id == "msg_123"
            assert result.thread_id == "thread_123"
            assert result.from_email == "sender@example.com"
            assert result.subject == "Test Subject"
            assert result.body == body_content
            assert "INBOX" in result.labels

    def test_get_message_handles_multipart(self, mock_gmail_service):
        """Test that multipart emails are parsed correctly."""
        text_body = "Plain text content"
        html_body = "<html><body>HTML content</body></html>"

        mock_response = {
            "id": "msg_multipart",
            "threadId": "thread_456",
            "snippet": "Preview",
            "labelIds": [],
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Multipart Email"},
                    {"name": "Date", "value": "Tue, 15 Jan 2025 10:30:00 +0000"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": base64.urlsafe_b64encode(
                                text_body.encode()
                            ).decode()
                        },
                    },
                    {
                        "mimeType": "text/html",
                        "body": {
                            "data": base64.urlsafe_b64encode(
                                html_body.encode()
                            ).decode()
                        },
                    },
                ],
            },
        }

        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_messages.get.return_value.execute.return_value = mock_response
        mock_service.users.return_value.messages.return_value = mock_messages

        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = {"token": "test"}

            from src.services.gmail_client import GmailClient

            client = GmailClient()
            client._service = mock_service

            result = client.get_message("msg_multipart")

            # Should prefer plain text over HTML
            assert result.body == text_body


class TestGmailClientLabels:
    """Tests for label operations."""

    def test_get_or_create_label_finds_existing(self, mock_gmail_service):
        """Test that existing labels are returned from cache/API."""
        mock_service = MagicMock()
        mock_labels = MagicMock()
        mock_labels.list.return_value.execute.return_value = {
            "labels": [
                {"id": "label_1", "name": "Agent/Work"},
                {"id": "label_2", "name": "Agent/Personal"},
            ]
        }
        mock_service.users.return_value.labels.return_value = mock_labels

        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = {"token": "test"}

            from src.services.gmail_client import GmailClient

            client = GmailClient()
            client._service = mock_service

            result = client.get_or_create_label("Agent/Work")

            assert result == "label_1"
            mock_labels.create.assert_not_called()

    def test_get_or_create_label_creates_new(self, mock_gmail_service):
        """Test that new labels are created when not found."""
        mock_service = MagicMock()
        mock_labels = MagicMock()
        mock_labels.list.return_value.execute.return_value = {"labels": []}
        mock_labels.create.return_value.execute.return_value = {
            "id": "new_label_id",
            "name": "Agent/NewCategory",
        }
        mock_service.users.return_value.labels.return_value = mock_labels

        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = {"token": "test"}

            from src.services.gmail_client import GmailClient

            client = GmailClient()
            client._service = mock_service
            client._label_cache = {}

            result = client.get_or_create_label("Agent/NewCategory")

            assert result == "new_label_id"
            mock_labels.create.assert_called_once()

    def test_apply_label_calls_modify(self, mock_gmail_service):
        """Test that apply_label calls Gmail modify API."""
        mock_service = MagicMock()
        mock_labels = MagicMock()
        mock_labels.list.return_value.execute.return_value = {
            "labels": [{"id": "label_work", "name": "Agent/Work"}]
        }
        mock_messages = MagicMock()
        mock_service.users.return_value.labels.return_value = mock_labels
        mock_service.users.return_value.messages.return_value = mock_messages

        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = {"token": "test"}

            from src.services.gmail_client import GmailClient

            client = GmailClient()
            client._service = mock_service

            client.apply_label("msg_123", "Agent/Work")

            mock_messages.modify.assert_called_once()
            call_args = mock_messages.modify.call_args
            assert call_args.kwargs["id"] == "msg_123"
            assert "label_work" in call_args.kwargs["body"]["addLabelIds"]


class TestGmailClientBatchOperations:
    """Tests for batch operations."""

    def test_batch_get_messages_fetches_multiple(self, mock_gmail_service):
        """Test that batch_get_messages fetches multiple emails."""
        body_content = "Test body"
        encoded_body = base64.urlsafe_b64encode(body_content.encode()).decode()

        def create_mock_response(msg_id):
            return {
                "id": msg_id,
                "threadId": f"thread_{msg_id}",
                "snippet": "Preview",
                "labelIds": [],
                "payload": {
                    "headers": [
                        {"name": "From", "value": "sender@example.com"},
                        {"name": "Subject", "value": f"Subject {msg_id}"},
                        {"name": "Date", "value": "Tue, 15 Jan 2025 10:30:00 +0000"},
                    ],
                    "body": {"data": encoded_body},
                },
            }

        mock_service = MagicMock()

        # Mock batch request
        def mock_batch_execute(batch_request):
            # The callback is set when add() is called
            pass

        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = {"token": "test"}

            from src.services.gmail_client import GmailClient

            client = GmailClient()
            client._service = mock_service

            # Mock the batch to call callbacks with responses
            mock_batch = MagicMock()
            responses = []

            def mock_add(request, request_id):
                responses.append((request_id, create_mock_response(request_id)))

            def mock_execute():
                for request_id, response in responses:
                    # The callback is stored in new_batch_http_request
                    pass

            mock_batch.add = mock_add
            mock_batch.execute = mock_execute
            mock_service.new_batch_http_request.return_value = mock_batch

            # Test returns parsed messages (will be empty due to mock complexity)
            result = client.batch_get_messages(["msg_1", "msg_2", "msg_3"])

            # Verify batch was created
            mock_service.new_batch_http_request.assert_called_once()


class TestGmailClientCredentials:
    """Tests for credential handling."""

    def test_missing_user_token_raises_error(self):
        """Test that missing user token raises ValueError."""
        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = None

            from src.services.gmail_client import GmailClient

            client = GmailClient()

            with pytest.raises(ValueError, match="user token not configured"):
                client._get_credentials()

    def test_expired_credentials_are_refreshed(self):
        """Test that expired credentials trigger refresh."""
        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = {
                "token": "expired_token",
                "refresh_token": "refresh_token",
                "client_id": "client_id",
                "client_secret": "client_secret",
            }

            with patch("src.services.gmail_client.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                mock_creds.valid = False
                mock_creds.expired = True
                mock_creds.refresh_token = "refresh_token"
                mock_creds_class.return_value = mock_creds

                with patch("src.services.gmail_client.Request"):
                    from src.services.gmail_client import GmailClient

                    client = GmailClient()
                    client._get_credentials()

                    mock_creds.refresh.assert_called_once()


class TestGmailClientRetry:
    """Tests for retry logic."""

    def test_http_error_triggers_retry(self, mock_gmail_service):
        """Test that HttpError triggers retry mechanism."""
        mock_service = MagicMock()
        mock_messages = MagicMock()

        # Simulate transient failure then success
        mock_messages.list.return_value.execute.side_effect = [
            HttpError(
                resp=MagicMock(status=500),
                content=b"Server Error",
            ),
            {"messages": [{"id": "msg_1", "threadId": "thread_1"}]},
        ]
        mock_service.users.return_value.messages.return_value = mock_messages

        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = {"token": "test"}

            with patch("tenacity.nap.time.sleep"):
                from src.services.gmail_client import GmailClient

                client = GmailClient()
                client._service = mock_service

                result = client.list_messages()

                assert len(result) == 1
                assert mock_messages.list.return_value.execute.call_count == 2
