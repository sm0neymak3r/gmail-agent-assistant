"""Unit tests for ApprovalCLI.

Tests the terminal-based approval interface with mocked I/O.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


class TestApprovalCLIInit:
    """Tests for ApprovalCLI initialization."""

    def test_approval_cli_initializes(self):
        """Test that ApprovalCLI initializes with required components."""
        # Import the module directly to avoid patch target issues
        from src.cli import approval as approval_module

        with patch.object(approval_module, "get_config"):
            with patch.object(approval_module, "get_sync_session"):
                cli = approval_module.ApprovalCLI()

                assert cli.console is not None
                assert cli._gmail is None  # Lazy-loaded

    def test_approval_cli_lazy_loads_gmail(self):
        """Test that Gmail client is lazy-loaded on access."""
        from src.cli import approval as approval_module

        with patch.object(approval_module, "get_config"):
            with patch.object(approval_module, "get_sync_session"):
                with patch.object(approval_module, "GmailClient") as mock_gmail:
                    mock_gmail.return_value = MagicMock()

                    cli = approval_module.ApprovalCLI()

                    # Gmail not loaded yet
                    assert cli._gmail is None

                    # Access gmail property
                    gmail = cli.gmail

                    # Now it should be loaded
                    assert gmail is not None
                    mock_gmail.assert_called_once()


class TestApprovalCLIFormatConfidence:
    """Tests for _format_confidence method."""

    def test_format_confidence_high(self):
        """Test that high confidence is formatted with green color."""
        from src.cli import approval as approval_module

        with patch.object(approval_module, "get_config"):
            with patch.object(approval_module, "get_sync_session"):
                cli = approval_module.ApprovalCLI()
                result = cli._format_confidence(0.85)

                assert "green" in result
                assert "85" in result

    def test_format_confidence_medium(self):
        """Test that medium confidence is formatted with yellow color."""
        from src.cli import approval as approval_module

        with patch.object(approval_module, "get_config"):
            with patch.object(approval_module, "get_sync_session"):
                cli = approval_module.ApprovalCLI()
                result = cli._format_confidence(0.65)

                assert "yellow" in result
                assert "65" in result

    def test_format_confidence_low(self):
        """Test that low confidence is formatted with red color."""
        from src.cli import approval as approval_module

        with patch.object(approval_module, "get_config"):
            with patch.object(approval_module, "get_sync_session"):
                cli = approval_module.ApprovalCLI()
                result = cli._format_confidence(0.45)

                assert "red" in result
                assert "45" in result

    def test_format_confidence_none(self):
        """Test that None confidence shows unknown."""
        from src.cli import approval as approval_module

        with patch.object(approval_module, "get_config"):
            with patch.object(approval_module, "get_sync_session"):
                cli = approval_module.ApprovalCLI()
                result = cli._format_confidence(None)

                assert "Unknown" in result


class TestApprovalCLIMain:
    """Tests for main entry point."""

    def test_main_creates_and_runs_cli(self):
        """Test that main() creates ApprovalCLI and runs it."""
        from src.cli import approval as approval_module

        with patch.object(approval_module, "get_config"):
            with patch.object(approval_module, "get_sync_session"):
                with patch.object(approval_module, "ApprovalCLI") as mock_cli_class:
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli

                    approval_module.main()

                    mock_cli_class.assert_called_once()
                    mock_cli.run.assert_called_once()
