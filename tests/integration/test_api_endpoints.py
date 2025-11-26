"""Integration tests for FastAPI endpoints.

Tests API routes with mocked external dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from httpx import AsyncClient, ASGITransport


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint_healthy(self, async_client_app):
        """Test that health endpoint returns healthy when all checks pass."""
        app, mock_session = async_client_app

        with patch("src.main.get_config") as mock_config:
            mock_config.return_value.environment = "test"
            mock_config.return_value.gmail.oauth_client = {"client_id": "test"}
            mock_config.return_value.gmail.user_token = {"token": "test"}
            mock_config.return_value.anthropic.api_key = "test-key"

            with patch("src.main.get_async_session") as mock_session_factory:
                mock_session = AsyncMock()
                mock_session.execute = AsyncMock()

                mock_context = AsyncMock()
                mock_context.__aenter__.return_value = mock_session
                mock_context.__aexit__.return_value = None

                mock_session_factory.return_value = MagicMock(return_value=mock_context)

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.get("/health")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert data["service"] == "gmail-agent"
                assert "checks" in data

    @pytest.mark.asyncio
    async def test_health_endpoint_degraded_missing_gmail(self, async_client_app):
        """Test that health endpoint returns degraded when Gmail config missing."""
        app, _ = async_client_app

        with patch("src.main.get_config") as mock_config:
            mock_config.return_value.environment = "test"
            mock_config.return_value.gmail.oauth_client = None  # Missing
            mock_config.return_value.gmail.user_token = None  # Missing
            mock_config.return_value.anthropic.api_key = "test-key"

            with patch("src.main.get_async_session") as mock_session_factory:
                mock_session = AsyncMock()
                mock_session.execute = AsyncMock()

                mock_context = AsyncMock()
                mock_context.__aenter__.return_value = mock_session
                mock_context.__aexit__.return_value = None

                mock_session_factory.return_value = MagicMock(return_value=mock_context)

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.get("/health")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "degraded"
                assert data["checks"]["gmail_oauth"] == "missing"

    @pytest.mark.asyncio
    async def test_health_endpoint_degraded_missing_anthropic(self, async_client_app):
        """Test that health endpoint returns degraded when Anthropic config missing."""
        app, _ = async_client_app

        with patch("src.main.get_config") as mock_config:
            mock_config.return_value.environment = "test"
            mock_config.return_value.gmail.oauth_client = {"client_id": "test"}
            mock_config.return_value.gmail.user_token = {"token": "test"}
            mock_config.return_value.anthropic.api_key = None  # Missing

            with patch("src.main.get_async_session") as mock_session_factory:
                mock_session = AsyncMock()
                mock_session.execute = AsyncMock()

                mock_context = AsyncMock()
                mock_context.__aenter__.return_value = mock_session
                mock_context.__aexit__.return_value = None

                mock_session_factory.return_value = MagicMock(return_value=mock_context)

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.get("/health")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "degraded"
                assert data["checks"]["anthropic"] == "missing"


class TestProcessEndpoint:
    """Tests for /process endpoint."""

    @pytest.mark.asyncio
    async def test_process_endpoint_returns_results(self, async_client_app):
        """Test that process endpoint returns processing results."""
        app, _ = async_client_app

        mock_results = {
            "processed": 5,
            "categorized": 5,
            "pending_approval": 1,
            "labeled": 4,
            "errors": 0,
            "error_details": [],
        }

        with patch("src.main.EmailProcessor") as mock_processor_class:
            mock_processor = AsyncMock()
            mock_processor.process_batch = AsyncMock(return_value=mock_results)
            mock_processor_class.return_value = mock_processor

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/process",
                    json={
                        "trigger": "manual",
                        "mode": "batch",
                        "query": "is:unread",
                        "max_emails": 10,
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["processed"] == 5
            assert data["labeled"] == 4
            assert data["pending_approval"] == 1

    @pytest.mark.asyncio
    async def test_process_endpoint_handles_errors(self, async_client_app):
        """Test that process endpoint handles errors gracefully."""
        app, _ = async_client_app

        with patch("src.main.EmailProcessor") as mock_processor_class:
            mock_processor = AsyncMock()
            mock_processor.process_batch = AsyncMock(
                side_effect=Exception("Processing failed")
            )
            mock_processor_class.return_value = mock_processor

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/process",
                    json={"query": "is:unread"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"
            assert data["errors"] == 1
            assert "Processing failed" in data["error_details"][0]["error"]


class TestPendingEndpoint:
    """Tests for /pending endpoint."""

    @pytest.mark.asyncio
    async def test_pending_endpoint_returns_pending_emails(
        self, async_client_app, email_factory
    ):
        """Test that pending endpoint returns emails pending approval."""
        app, _ = async_client_app

        mock_emails = [
            email_factory(
                email_id="email-1",
                message_id="msg_1",
                status="pending_approval",
                category="Professional/Work",
                confidence=0.65,
            ),
            email_factory(
                email_id="email-2",
                message_id="msg_2",
                status="pending_approval",
                category="Newsletters/Subscriptions",
                confidence=0.55,
            ),
        ]

        with patch("src.main.get_async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_emails
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None

            mock_session_factory.return_value = MagicMock(return_value=mock_context)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/pending")

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 2
            assert len(data["emails"]) == 2
            assert data["emails"][0]["email_id"] == "email-1"
            assert data["emails"][0]["confidence"] == 0.65

    @pytest.mark.asyncio
    async def test_pending_endpoint_empty_list(self, async_client_app):
        """Test that pending endpoint handles no pending emails."""
        app, _ = async_client_app

        with patch("src.main.get_async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None

            mock_session_factory.return_value = MagicMock(return_value=mock_context)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/pending")

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0
            assert data["emails"] == []


class TestApproveEndpoint:
    """Tests for /approve/{email_id} endpoint."""

    @pytest.mark.asyncio
    async def test_approve_endpoint_approves_email(
        self, async_client_app, email_factory
    ):
        """Test that approve endpoint updates email status."""
        app, _ = async_client_app

        mock_email = email_factory(
            email_id="email-approve",
            message_id="msg_approve",
            status="pending_approval",
            category="Professional/Work",
            confidence=0.65,
        )

        with patch("src.main.get_async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_email
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None

            mock_session_factory.return_value = MagicMock(return_value=mock_context)

            with patch("src.main.GmailClient") as mock_gmail_class:
                mock_gmail = MagicMock()
                mock_gmail.apply_label = MagicMock()
                mock_gmail_class.return_value = mock_gmail

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post("/approve/email-approve")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "approved"
                assert data["email_id"] == "email-approve"

    @pytest.mark.asyncio
    async def test_approve_endpoint_with_category_correction(
        self, async_client_app, email_factory
    ):
        """Test that approve endpoint allows category correction."""
        app, _ = async_client_app

        mock_email = email_factory(
            email_id="email-correct",
            message_id="msg_correct",
            status="pending_approval",
            category="Marketing/Promotions",
            confidence=0.55,
        )

        with patch("src.main.get_async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_email
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None

            mock_session_factory.return_value = MagicMock(return_value=mock_context)

            with patch("src.main.GmailClient") as mock_gmail_class:
                mock_gmail = MagicMock()
                mock_gmail.apply_label = MagicMock()
                mock_gmail_class.return_value = mock_gmail

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/approve/email-correct",
                        params={"category": "Newsletters/Subscriptions"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "approved"
                assert data["category"] == "Newsletters/Subscriptions"

    @pytest.mark.asyncio
    async def test_approve_endpoint_email_not_found(self, async_client_app):
        """Test that approve endpoint returns 404 for unknown email."""
        app, _ = async_client_app

        with patch("src.main.get_async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None  # Not found
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None

            mock_session_factory.return_value = MagicMock(return_value=mock_context)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/approve/nonexistent-email")

            assert response.status_code == 404


class TestRootEndpoint:
    """Tests for / root endpoint."""

    @pytest.mark.asyncio
    async def test_root_endpoint_returns_service_info(self, async_client_app):
        """Test that root endpoint returns basic service info."""
        app, _ = async_client_app

        with patch("src.main.get_config") as mock_config:
            mock_config.return_value.environment = "test"

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/")

            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "gmail-agent"
            assert data["status"] == "running"
            assert "version" in data
