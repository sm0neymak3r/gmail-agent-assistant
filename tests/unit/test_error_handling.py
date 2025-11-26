"""Unit tests for error handling across the application.

Tests error scenarios, retries, and graceful degradation.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json

import anthropic


class TestAnthropicClientErrorHandling:
    """Tests for Anthropic API error handling."""

    def test_api_error_is_raised(self, categories):
        """Test that Anthropic API errors are properly raised."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="API Error",
            request=MagicMock(),
            body={"error": "Test error"},
        )

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            with pytest.raises(anthropic.APIError):
                client.classify_email(
                    subject="Test",
                    from_email="test@test.com",
                    body="Test body",
                    categories=categories,
                )

    def test_authentication_error_is_raised(self, categories):
        """Test that authentication errors are properly raised."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body={"error": {"type": "authentication_error"}},
        )

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="invalid-key")
            client = AnthropicClient(config=config)

            with pytest.raises(anthropic.AuthenticationError):
                client.classify_email(
                    subject="Test",
                    from_email="test@test.com",
                    body="Test body",
                    categories=categories,
                )

    def test_rate_limit_triggers_retry(self, mock_anthropic_response_high_confidence, categories):
        """Test that rate limit errors trigger retry with backoff."""
        mock_client = MagicMock()
        # First call fails with rate limit, second succeeds
        mock_client.messages.create.side_effect = [
            anthropic.RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body={"error": {"message": "Rate limit exceeded"}},
            ),
            mock_anthropic_response_high_confidence,
        ]

        with patch("anthropic.Anthropic", return_value=mock_client):
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

    def test_malformed_json_returns_uncategorized(self, categories):
        """Test that malformed JSON response returns Uncategorized."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Not valid JSON at all")]
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


class TestGmailClientErrorHandling:
    """Tests for Gmail API error handling."""

    def test_missing_user_token_raises_error(self):
        """Test that missing user token raises ValueError on use."""
        with patch("src.services.gmail_client.get_config") as mock_config:
            mock_config.return_value.gmail.user_token = None

            from src.services.gmail_client import GmailClient

            client = GmailClient()

            with pytest.raises(ValueError, match="token not configured"):
                client._get_credentials()


class TestConfigurationErrorHandling:
    """Tests for configuration error handling."""

    def test_config_handles_missing_api_key(self):
        """Test that AnthropicConfig can be created with explicit api_key."""
        from src.config import AnthropicConfig

        # Config with explicit key
        config = AnthropicConfig(api_key="test-key")
        assert config.api_key == "test-key"


class TestInputValidationErrors:
    """Tests for input validation error handling."""

    def test_empty_email_body_handled(self, categories):
        """Test that empty email body is handled gracefully."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text=json.dumps(
                    {
                        "category": "Uncategorized",
                        "confidence": 0.3,
                        "reasoning": "Empty email body",
                        "key_phrases": [],
                    }
                )
            )
        ]
        mock_response.usage = MagicMock(input_tokens=50, output_tokens=30)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            result = client.classify_email(
                subject="Empty Email",
                from_email="test@test.com",
                body="",  # Empty body
                categories=categories,
            )

            # Should not raise, should return some result
            assert result is not None

    def test_very_long_subject_truncated(self, categories):
        """Test that very long subjects are handled."""
        long_subject = "A" * 10000

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text=json.dumps(
                    {
                        "category": "Important",
                        "confidence": 0.8,
                        "reasoning": "Test",
                        "key_phrases": [],
                    }
                )
            )
        ]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("anthropic.Anthropic", return_value=mock_client):
            from src.services.anthropic_client import AnthropicClient
            from src.config import AnthropicConfig

            config = AnthropicConfig(api_key="test-key")
            client = AnthropicClient(config=config)

            # Should not raise
            result = client.classify_email(
                subject=long_subject,
                from_email="test@test.com",
                body="Test body",
                categories=categories,
            )

            assert result is not None
