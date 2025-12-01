"""Unit tests for workflow state definitions.

Tests EmailState TypedDict and state creation functions.
"""

import pytest
from datetime import datetime


class TestEmailState:
    """Tests for EmailState TypedDict."""

    def test_email_state_has_required_fields(self):
        """Test that EmailState TypedDict has expected fields."""
        from src.workflows.state import EmailState

        # EmailState is a TypedDict, check it has expected keys
        state: EmailState = {
            "email_id": "test-id",
            "message_id": "msg_test",
            "thread_id": "thread_test",
            "from_email": "test@test.com",
            "subject": "Test Subject",
            "body": "Test body",
            "processing_step": "fetched",
        }

        assert state["email_id"] == "test-id"
        assert state["processing_step"] == "fetched"

    def test_email_state_processing_steps(self):
        """Test that processing_step accepts valid values."""
        from src.workflows.state import EmailState

        valid_steps = [
            "fetched",
            "categorized",
            "importance_checked",
            "labeled",
            "pending_approval",
            "completed",
            "failed",
        ]

        for step in valid_steps:
            state: EmailState = {
                "email_id": "test",
                "message_id": "msg",
                "processing_step": step,
            }
            assert state["processing_step"] == step

    def test_email_state_optional_fields(self):
        """Test that optional fields can be omitted."""
        from src.workflows.state import EmailState

        # Minimal state with only required fields
        state: EmailState = {
            "email_id": "test",
            "message_id": "msg",
        }

        assert "category" not in state
        assert "confidence" not in state


class TestCreateInitialState:
    """Tests for create_initial_state function."""

    def test_create_initial_state_sets_all_fields(self):
        """Test that create_initial_state sets all expected fields."""
        from src.workflows.state import create_initial_state

        state = create_initial_state(
            email_id="email-123",
            message_id="msg_123",
            thread_id="thread_123",
            from_email="sender@example.com",
            to_emails=["recipient@example.com"],
            subject="Test Subject",
            body="Test body content",
            date=datetime(2025, 1, 15, 10, 30),
        )

        # Check required fields
        assert state["email_id"] == "email-123"
        assert state["message_id"] == "msg_123"
        assert state["thread_id"] == "thread_123"
        assert state["from_email"] == "sender@example.com"
        assert state["to_emails"] == ["recipient@example.com"]
        assert state["subject"] == "Test Subject"
        assert state["body"] == "Test body content"

        # Check default processing state
        assert state["processing_step"] == "fetched"
        assert state["category"] == ""
        assert state["confidence"] == 0.0
        assert state["needs_human_approval"] is False

    def test_create_initial_state_converts_date_to_iso(self):
        """Test that date is converted to ISO format string."""
        from src.workflows.state import create_initial_state

        test_date = datetime(2025, 1, 15, 10, 30, 45)
        state = create_initial_state(
            email_id="email",
            message_id="msg",
            thread_id="thread",
            from_email="test@test.com",
            to_emails=[],
            subject="Test",
            body="Body",
            date=test_date,
        )

        assert state["date"] == "2025-01-15T10:30:45"

    def test_create_initial_state_handles_string_date(self):
        """Test that string dates are preserved."""
        from src.workflows.state import create_initial_state

        date_str = "2025-01-15T10:30:45"
        state = create_initial_state(
            email_id="email",
            message_id="msg",
            thread_id="thread",
            from_email="test@test.com",
            to_emails=[],
            subject="Test",
            body="Body",
            date=date_str,
        )

        assert state["date"] == date_str

    def test_create_initial_state_sets_default_headers(self):
        """Test that headers default to empty dict."""
        from src.workflows.state import create_initial_state

        state = create_initial_state(
            email_id="email",
            message_id="msg",
            thread_id="thread",
            from_email="test@test.com",
            to_emails=[],
            subject="Test",
            body="Body",
            date=datetime.now(),
        )

        assert state["headers"] == {}

    def test_create_initial_state_sets_default_labels(self):
        """Test that labels default to empty list."""
        from src.workflows.state import create_initial_state

        state = create_initial_state(
            email_id="email",
            message_id="msg",
            thread_id="thread",
            from_email="test@test.com",
            to_emails=[],
            subject="Test",
            body="Body",
            date=datetime.now(),
        )

        assert state["labels"] == []

    def test_create_initial_state_with_optional_params(self):
        """Test that optional parameters are properly set."""
        from src.workflows.state import create_initial_state

        state = create_initial_state(
            email_id="email",
            message_id="msg",
            thread_id="thread",
            from_email="test@test.com",
            to_emails=["to@test.com"],
            subject="Test",
            body="Body",
            date=datetime.now(),
            headers={"x-custom": "value"},
            snippet="Preview text...",
            labels=["INBOX", "UNREAD"],
        )

        assert state["headers"] == {"x-custom": "value"}
        assert state["snippet"] == "Preview text..."
        assert state["labels"] == ["INBOX", "UNREAD"]

    def test_create_initial_state_sets_fetched_at(self):
        """Test that fetched_at timestamp is set."""
        from src.workflows.state import create_initial_state

        state = create_initial_state(
            email_id="email",
            message_id="msg",
            thread_id="thread",
            from_email="test@test.com",
            to_emails=[],
            subject="Test",
            body="Body",
            date=datetime.now(),
        )

        assert "fetched_at" in state
        assert state["fetched_at"] is not None
        # Should be ISO format
        assert "T" in state["fetched_at"]

    def test_create_initial_state_initializes_importance(self):
        """Test that importance fields are initialized."""
        from src.workflows.state import create_initial_state

        state = create_initial_state(
            email_id="email",
            message_id="msg",
            thread_id="thread",
            from_email="test@test.com",
            to_emails=[],
            subject="Test",
            body="Body",
            date=datetime.now(),
        )

        assert state["importance_level"] == "normal"
        assert state["importance_score"] == 0.5
        assert state["action_items"] == []

    def test_create_initial_state_error_fields(self):
        """Test that error handling fields are initialized."""
        from src.workflows.state import create_initial_state

        state = create_initial_state(
            email_id="email",
            message_id="msg",
            thread_id="thread",
            from_email="test@test.com",
            to_emails=[],
            subject="Test",
            body="Body",
            date=datetime.now(),
        )

        assert state["error"] is None
        assert state["retry_count"] == 0


class TestMergeMessages:
    """Tests for merge_messages reducer function."""

    def test_merge_messages_appends_lists(self):
        """Test that merge_messages appends right to left."""
        from src.workflows.state import merge_messages

        left = [{"role": "user", "content": "Hello"}]
        right = [{"role": "assistant", "content": "Hi"}]

        result = merge_messages(left, right)

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_merge_messages_empty_lists(self):
        """Test that merge_messages handles empty lists."""
        from src.workflows.state import merge_messages

        assert merge_messages([], []) == []
        assert merge_messages([], [{"a": 1}]) == [{"a": 1}]
        assert merge_messages([{"b": 2}], []) == [{"b": 2}]
