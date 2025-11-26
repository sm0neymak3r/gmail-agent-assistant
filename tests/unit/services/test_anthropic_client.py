"""Unit tests for AnthropicClient.

Tests classification functionality, model escalation, and error handling.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

import anthropic


class TestAnthropicClientClassifyEmail:
    """Tests for classify_email method."""

    def test_classify_email_returns_valid_result(
        self, mock_anthropic_response_high_confidence, categories
    ):
        """Test that classify_email returns a properly structured ClassificationResult."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response_high_confidence

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient, ClassificationResult
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            result = client.classify_email(
                subject="Q4 Planning Meeting",
                from_email="manager@company.com",
                body="Please review the project timeline.",
                categories=categories,
            )

            assert isinstance(result, ClassificationResult)
            assert result.category == "Professional/Work"
            assert result.confidence == 0.92
            assert "meeting" in result.reasoning.lower() or "work" in result.reasoning.lower()
            assert isinstance(result.key_phrases, list)
            assert result.model_used == "claude-3-haiku-20240307"
            assert result.input_tokens == 150
            assert result.output_tokens == 75

    def test_classify_email_uses_fast_model_by_default(
        self, mock_anthropic_response_high_confidence, categories
    ):
        """Test that fast model (Haiku) is used by default."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response_high_confidence

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            client.classify_email(
                subject="Test",
                from_email="test@test.com",
                body="Test body",
                categories=categories,
                use_quality_model=False,
            )

            call_args = mock_client.messages.create.call_args
            assert "haiku" in call_args.kwargs["model"]

    def test_classify_email_uses_quality_model_when_requested(
        self, mock_anthropic_response_high_confidence, categories
    ):
        """Test that quality model (Sonnet) is used when requested."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response_high_confidence

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            client.classify_email(
                subject="Test",
                from_email="test@test.com",
                body="Test body",
                categories=categories,
                use_quality_model=True,
            )

            call_args = mock_client.messages.create.call_args
            assert "sonnet" in call_args.kwargs["model"]

    def test_classify_handles_json_in_markdown_blocks(self, categories):
        """Test that JSON wrapped in markdown code blocks is parsed correctly."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text="""```json
{
  "category": "Marketing/Promotions",
  "confidence": 0.88,
  "reasoning": "Promotional content with sale keywords",
  "key_phrases": ["sale", "discount"]
}
```""")
        ]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            result = client.classify_email(
                subject="Big Sale",
                from_email="deals@store.com",
                body="50% off everything!",
                categories=categories,
            )

            assert result.category == "Marketing/Promotions"
            assert result.confidence == 0.88

    def test_classify_handles_malformed_json(self, categories):
        """Test that malformed JSON returns low-confidence Uncategorized result."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text="This is not valid JSON at all")
        ]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            result = client.classify_email(
                subject="Test",
                from_email="test@test.com",
                body="Test body",
                categories=categories,
            )

            assert result.category == "Uncategorized"
            assert result.confidence == 0.0
            assert "parse" in result.reasoning.lower()

    def test_classify_truncates_long_body(self, mock_anthropic_response_high_confidence, categories):
        """Test that very long email bodies are truncated to ~10k chars."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response_high_confidence

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            # Create a very long body
            long_body = "x" * 20000

            client.classify_email(
                subject="Test",
                from_email="test@test.com",
                body=long_body,
                categories=categories,
            )

            # Check the prompt sent to the API
            call_args = mock_client.messages.create.call_args
            user_message = call_args.kwargs["messages"][0]["content"]
            # Body should be truncated to 10000 chars
            assert len(user_message) < 15000  # Some overhead for prompt template


class TestAnthropicClientEscalation:
    """Tests for classify_with_escalation method."""

    def test_classify_with_escalation_uses_fast_model_first(
        self, mock_anthropic_response_high_confidence, categories
    ):
        """Test that escalation starts with fast model."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response_high_confidence

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            result = client.classify_with_escalation(
                subject="Meeting tomorrow",
                from_email="boss@company.com",
                body="Let's discuss the project",
                categories=categories,
            )

            # Should only call once since confidence is high
            assert mock_client.messages.create.call_count == 1
            assert result.confidence == 0.92

    def test_classify_with_escalation_escalates_on_low_confidence(self, categories):
        """Test that low confidence triggers escalation to quality model."""
        # First response: low confidence
        low_conf_response = MagicMock()
        low_conf_response.content = [
            MagicMock(text=json.dumps({
                "category": "Newsletters/Subscriptions",
                "confidence": 0.55,
                "reasoning": "Unclear content",
                "key_phrases": [],
            }))
        ]
        low_conf_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        # Second response: higher confidence from quality model
        high_conf_response = MagicMock()
        high_conf_response.content = [
            MagicMock(text=json.dumps({
                "category": "Marketing/Promotions",
                "confidence": 0.82,
                "reasoning": "Promotional content identified",
                "key_phrases": ["sale", "offer"],
            }))
        ]
        high_conf_response.usage = MagicMock(input_tokens=150, output_tokens=75)

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [low_conf_response, high_conf_response]

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            result = client.classify_with_escalation(
                subject="Special Offer",
                from_email="deals@store.com",
                body="Limited time sale",
                categories=categories,
                confidence_threshold=0.7,
            )

            # Should call twice (fast then quality)
            assert mock_client.messages.create.call_count == 2

            # First call should use fast model
            first_call = mock_client.messages.create.call_args_list[0]
            assert "haiku" in first_call.kwargs["model"]

            # Second call should use quality model
            second_call = mock_client.messages.create.call_args_list[1]
            assert "sonnet" in second_call.kwargs["model"]

            # Final result should be from quality model
            assert result.category == "Marketing/Promotions"
            assert result.confidence == 0.82

    def test_classify_with_escalation_no_escalate_when_above_threshold(self, categories):
        """Test that escalation doesn't happen when confidence meets threshold."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps({
                "category": "Professional/Work",
                "confidence": 0.75,
                "reasoning": "Work content",
                "key_phrases": ["meeting"],
            }))
        ]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            result = client.classify_with_escalation(
                subject="Meeting",
                from_email="coworker@company.com",
                body="Team meeting tomorrow",
                categories=categories,
                confidence_threshold=0.7,  # 0.75 >= 0.7, no escalation
            )

            # Should only call once
            assert mock_client.messages.create.call_count == 1
            assert result.confidence == 0.75


class TestAnthropicClientRetry:
    """Tests for retry logic on rate limits."""

    def test_classify_retries_on_rate_limit(self, mock_anthropic_response_high_confidence, categories):
        """Test that rate limit errors trigger retry."""
        mock_client = MagicMock()
        # First call raises rate limit, second succeeds
        mock_client.messages.create.side_effect = [
            anthropic.RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body={"error": {"message": "Rate limit exceeded"}},
            ),
            mock_anthropic_response_high_confidence,
        ]

        with patch("anthropic.Anthropic", return_value=mock_client):
            # Patch sleep to speed up test
            with patch("tenacity.nap.time.sleep"):
                from src.services.anthropic_client import AnthropicClient
                from src.config import AnthropicConfig

                config = AnthropicConfig(api_key="test-key")
                client = AnthropicClient(config=config)

                result = client.classify_email(
                    subject="Test",
                    from_email="test@test.com",
                    body="Test body",
                    categories=categories,
                )

                # Should have retried and succeeded
                assert mock_client.messages.create.call_count == 2
                assert result.category == "Professional/Work"


class TestAnthropicClientTokenTracking:
    """Tests for token usage tracking."""

    def test_token_usage_tracked(self, categories):
        """Test that input and output tokens are tracked in result."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps({
                "category": "Important",
                "confidence": 0.95,
                "reasoning": "Urgent content",
                "key_phrases": ["urgent"],
            }))
        ]
        mock_response.usage = MagicMock(input_tokens=250, output_tokens=100)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            result = client.classify_email(
                subject="URGENT: Action Required",
                from_email="boss@company.com",
                body="This needs immediate attention",
                categories=categories,
            )

            assert result.input_tokens == 250
            assert result.output_tokens == 100
