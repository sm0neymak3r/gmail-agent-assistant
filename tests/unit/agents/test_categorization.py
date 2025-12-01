"""Unit tests for CategorizationAgent.

Tests the categorization workflow including state updates and escalation.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


class TestCategorizationAgentCategorize:
    """Tests for categorize method."""

    def test_categorize_updates_state_correctly(self, classification_result_factory, categories):
        """Test that categorize updates all required state fields."""
        mock_result = classification_result_factory(
            category="Professional/Work",
            confidence=0.92,
            reasoning="Work-related meeting content",
        )

        mock_client = MagicMock()
        mock_client.classify_with_escalation.return_value = mock_result

        with patch("src.agents.categorization.get_config") as mock_config:
            mock_config.return_value.confidence_threshold = 0.8

            from src.agents.categorization import CategorizationAgent

            agent = CategorizationAgent(anthropic_client=mock_client)

            state = {
                "email_id": "test-123",
                "message_id": "msg_123",
                "subject": "Q4 Planning Meeting",
                "from_email": "manager@company.com",
                "body": "Please review the agenda for our planning meeting.",
                "processing_step": "fetched",
            }

            result_state = agent.categorize(state)

            assert result_state["category"] == "Professional/Work"
            assert result_state["confidence"] == 0.92
            assert result_state["reasoning"] == "Work-related meeting content"
            assert result_state["processing_step"] == "categorized"
            assert result_state["needs_human_approval"] is False  # 0.92 >= 0.8

    def test_categorize_sets_needs_approval_on_low_confidence(
        self, classification_result_factory
    ):
        """Test that low confidence emails are marked for human approval."""
        mock_result = classification_result_factory(
            category="Newsletters/Subscriptions",
            confidence=0.65,  # Below 0.8 threshold
            reasoning="Unclear whether newsletter or promotional",
        )

        mock_client = MagicMock()
        mock_client.classify_with_escalation.return_value = mock_result

        with patch("src.agents.categorization.get_config") as mock_config:
            mock_config.return_value.confidence_threshold = 0.8

            from src.agents.categorization import CategorizationAgent

            agent = CategorizationAgent(anthropic_client=mock_client)

            state = {
                "email_id": "test-456",
                "message_id": "msg_456",
                "subject": "Weekly Update",
                "from_email": "news@example.com",
                "body": "Here's what happened this week...",
                "processing_step": "fetched",
            }

            result_state = agent.categorize(state)

            assert result_state["needs_human_approval"] is True
            assert result_state["approval_type"] == "categorization"
            assert result_state["confidence"] == 0.65

    def test_categorize_preserves_existing_state(self, classification_result_factory):
        """Test that categorize preserves other state fields."""
        mock_result = classification_result_factory(
            category="Important",
            confidence=0.95,
        )

        mock_client = MagicMock()
        mock_client.classify_with_escalation.return_value = mock_result

        with patch("src.agents.categorization.get_config") as mock_config:
            mock_config.return_value.confidence_threshold = 0.8

            from src.agents.categorization import CategorizationAgent

            agent = CategorizationAgent(anthropic_client=mock_client)

            # State with extra fields that should be preserved
            state = {
                "email_id": "test-789",
                "message_id": "msg_789",
                "thread_id": "thread_789",
                "subject": "Urgent: Deadline Today",
                "from_email": "boss@company.com",
                "to_emails": ["me@company.com"],
                "body": "This needs immediate attention.",
                "date": datetime(2025, 1, 15),
                "processing_step": "fetched",
                "custom_field": "should_be_preserved",
            }

            result_state = agent.categorize(state)

            # Original fields preserved
            assert result_state["email_id"] == "test-789"
            assert result_state["thread_id"] == "thread_789"
            assert result_state["to_emails"] == ["me@company.com"]
            assert result_state["custom_field"] == "should_be_preserved"

            # New fields added
            assert result_state["category"] == "Important"
            assert result_state["processing_step"] == "categorized"

    def test_categorize_handles_api_error(self):
        """Test that API errors are propagated correctly."""
        import anthropic

        mock_client = MagicMock()
        mock_client.classify_with_escalation.side_effect = anthropic.APIError(
            message="API Error",
            request=MagicMock(),
            body={"error": "Test error"},
        )

        with patch("src.agents.categorization.get_config") as mock_config:
            mock_config.return_value.confidence_threshold = 0.8

            from src.agents.categorization import CategorizationAgent

            agent = CategorizationAgent(anthropic_client=mock_client)

            state = {
                "email_id": "test-error",
                "message_id": "msg_error",
                "subject": "Test",
                "from_email": "test@test.com",
                "body": "Test body",
                "processing_step": "fetched",
            }

            with pytest.raises(anthropic.APIError):
                agent.categorize(state)


class TestCategorizationAgentRecategorize:
    """Tests for recategorize_with_feedback method."""

    def test_recategorize_with_suggested_category(self):
        """Test recategorization with human-suggested category."""
        mock_client = MagicMock()

        with patch("src.agents.categorization.get_config"):
            from src.agents.categorization import CategorizationAgent

            agent = CategorizationAgent(anthropic_client=mock_client)

            state = {
                "email_id": "test-recategorize",
                "message_id": "msg_recategorize",
                "subject": "Newsletter",
                "from_email": "news@example.com",
                "body": "Weekly newsletter content",
                "category": "Marketing/Promotions",  # Original wrong category
                "confidence": 0.55,
                "processing_step": "pending_approval",
            }

            result_state = agent.recategorize_with_feedback(
                state, suggested_category="Newsletters/Subscriptions"
            )

            # Human category applied
            assert result_state["category"] == "Newsletters/Subscriptions"
            assert result_state["confidence"] == 1.0  # Human-verified
            assert "human" in result_state["reasoning"].lower()
            assert result_state["needs_human_approval"] is False
            assert result_state["processing_step"] == "recategorized"

            # classify_email should NOT have been called
            mock_client.classify_email.assert_not_called()

    def test_recategorize_without_suggestion_uses_quality_model(
        self, classification_result_factory
    ):
        """Test that recategorization without suggestion uses quality model."""
        mock_result = classification_result_factory(
            category="Professional/Recruiters",
            confidence=0.88,
            reasoning="Job opportunity from recruiter",
            model_used="claude-sonnet-4-20250514",
        )

        mock_client = MagicMock()
        mock_client.classify_email.return_value = mock_result

        with patch("src.agents.categorization.get_config"):
            from src.agents.categorization import CategorizationAgent

            agent = CategorizationAgent(anthropic_client=mock_client)

            state = {
                "email_id": "test-recategorize-2",
                "message_id": "msg_recategorize_2",
                "subject": "Job Opportunity",
                "from_email": "recruiter@techcorp.com",
                "body": "We have an exciting position...",
                "category": "Professional/Work",
                "confidence": 0.60,
                "processing_step": "pending_approval",
            }

            result_state = agent.recategorize_with_feedback(state, suggested_category=None)

            # Quality model should have been called
            mock_client.classify_email.assert_called_once()
            call_args = mock_client.classify_email.call_args
            assert call_args.kwargs["use_quality_model"] is True

            assert result_state["category"] == "Professional/Recruiters"
            assert result_state["confidence"] == 0.88
            assert result_state["processing_step"] == "recategorized"


class TestCategorizationNodeFunction:
    """Tests for standalone categorize_email node function."""

    def test_categorize_email_node_function(self, classification_result_factory):
        """Test that the standalone node function works correctly."""
        mock_result = classification_result_factory(
            category="Personal/Friends",
            confidence=0.87,
        )

        mock_client = MagicMock()
        mock_client.classify_with_escalation.return_value = mock_result

        with patch("src.agents.categorization.AnthropicClient", return_value=mock_client):
            with patch("src.agents.categorization.get_config") as mock_config:
                mock_config.return_value.confidence_threshold = 0.8

                from src.agents.categorization import categorize_email

                state = {
                    "email_id": "test-node",
                    "message_id": "msg_node",
                    "subject": "Hey there!",
                    "from_email": "friend@gmail.com",
                    "body": "Let's grab coffee sometime!",
                    "processing_step": "fetched",
                }

                result = categorize_email(state)

                assert result["category"] == "Personal/Friends"
                assert result["processing_step"] == "categorized"
