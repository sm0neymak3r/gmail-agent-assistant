"""Shared test fixtures for Gmail Agent testing.

This module provides pytest fixtures for:
- PostgreSQL database connection (via Docker)
- Mock external services (Gmail API, Anthropic API)
- Test data factories (emails, classifications)
- FastAPI test clients
"""

import json
import os
import pytest
import pytest_asyncio
from datetime import datetime
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Environment Setup - Must happen before importing app modules
# ---------------------------------------------------------------------------

# Set test environment variables
os.environ["ENVIRONMENT"] = "test"
os.environ["PROJECT_ID"] = "test-project"
os.environ["DATABASE_HOST"] = "localhost"
os.environ["DATABASE_PORT"] = "5433"  # Test DB port
os.environ["DATABASE_NAME"] = "test_email_agent"
os.environ["DATABASE_USER"] = "test_user"
os.environ["DATABASE_PASSWORD"] = "test_password"
os.environ["ANTHROPIC_API_KEY"] = "test-api-key-sk-ant-xxxxx"
os.environ["GMAIL_OAUTH_CLIENT"] = json.dumps({
    "installed": {
        "client_id": "test-client-id.apps.googleusercontent.com",
        "client_secret": "test-client-secret",
    }
})
os.environ["GMAIL_USER_TOKEN"] = json.dumps({
    "token": "test-access-token",
    "refresh_token": "test-refresh-token",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "test-client-id.apps.googleusercontent.com",
    "client_secret": "test-client-secret",
    "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
})


# ---------------------------------------------------------------------------
# Database Fixtures (PostgreSQL via Docker)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = (
    f"postgresql://{os.environ['DATABASE_USER']}:{os.environ['DATABASE_PASSWORD']}"
    f"@{os.environ['DATABASE_HOST']}:{os.environ['DATABASE_PORT']}/{os.environ['DATABASE_NAME']}"
)

TEST_ASYNC_DATABASE_URL = (
    f"postgresql+asyncpg://{os.environ['DATABASE_USER']}:{os.environ['DATABASE_PASSWORD']}"
    f"@{os.environ['DATABASE_HOST']}:{os.environ['DATABASE_PORT']}/{os.environ['DATABASE_NAME']}"
)


@pytest.fixture(scope="session")
def sync_engine():
    """Create sync engine for test database setup and teardown."""
    engine = create_engine(TEST_DATABASE_URL, poolclass=NullPool)

    # Import and create all tables
    from src.models.base import Base
    Base.metadata.create_all(engine)

    yield engine

    # Drop all tables after tests
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def sync_session(sync_engine) -> Generator[Session, None, None]:
    """Provide a transactional sync session that rolls back after each test."""
    connection = sync_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    """Create async engine for test database."""
    engine = create_async_engine(TEST_ASYNC_DATABASE_URL, poolclass=NullPool)

    # Create tables using sync connection
    from src.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async session that rolls back after each test."""
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Mock Gmail API Service
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_gmail_service():
    """Mock Google Gmail API service object."""
    mock_service = MagicMock()

    # Default message list response
    mock_messages = MagicMock()
    mock_messages.list.return_value.execute.return_value = {
        "messages": [
            {"id": "msg_001", "threadId": "thread_001"},
            {"id": "msg_002", "threadId": "thread_002"},
        ]
    }

    # Default single message response
    mock_messages.get.return_value.execute.return_value = {
        "id": "msg_001",
        "threadId": "thread_001",
        "snippet": "This is a test email snippet...",
        "labelIds": ["INBOX", "UNREAD"],
        "payload": {
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Wed, 01 Jan 2025 12:00:00 +0000"},
            ],
            "body": {"data": "VGVzdCBlbWFpbCBib2R5IGNvbnRlbnQ="},  # base64("Test email body content")
        },
    }

    # Default labels response
    mock_labels = MagicMock()
    mock_labels.list.return_value.execute.return_value = {
        "labels": [
            {"id": "INBOX", "name": "INBOX"},
            {"id": "Label_1", "name": "Agent/Important"},
            {"id": "Label_2", "name": "Agent/Professional/Work"},
        ]
    }
    mock_labels.create.return_value.execute.return_value = {
        "id": "Label_NEW",
        "name": "Agent/NewCategory",
    }

    # Modify returns empty dict on success
    mock_messages.modify.return_value.execute.return_value = {}

    # Wire up the mock structure
    mock_users = MagicMock()
    mock_users.messages.return_value = mock_messages
    mock_users.labels.return_value = mock_labels
    mock_service.users.return_value = mock_users

    # Batch request mock
    mock_batch = MagicMock()
    mock_service.new_batch_http_request.return_value = mock_batch

    return mock_service


@pytest.fixture
def mock_gmail_credentials():
    """Mock OAuth credentials that appear valid."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.expired = False
    mock_creds.refresh_token = "test-refresh-token"
    return mock_creds


# ---------------------------------------------------------------------------
# Mock Anthropic API Client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_anthropic_response_high_confidence():
    """Mock Anthropic response with high confidence classification."""
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({
            "category": "Professional/Work",
            "confidence": 0.92,
            "reasoning": "Email contains work-related keywords like 'meeting' and 'project'",
            "key_phrases": ["meeting", "project update", "deadline"],
        }))
    ]
    mock_response.usage = MagicMock(input_tokens=150, output_tokens=75)
    return mock_response


@pytest.fixture
def mock_anthropic_response_low_confidence():
    """Mock Anthropic response with low confidence (triggers escalation)."""
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({
            "category": "Newsletters/Subscriptions",
            "confidence": 0.55,
            "reasoning": "Could be newsletter or promotional content, unclear",
            "key_phrases": ["weekly", "update"],
        }))
    ]
    mock_response.usage = MagicMock(input_tokens=150, output_tokens=75)
    return mock_response


@pytest.fixture
def mock_anthropic_client(mock_anthropic_response_high_confidence):
    """Mock Anthropic API client returning high confidence result."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_anthropic_response_high_confidence
    return mock_client


@pytest.fixture
def mock_anthropic_client_low_confidence(mock_anthropic_response_low_confidence):
    """Mock Anthropic client that returns low confidence initially."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_anthropic_response_low_confidence
    return mock_client


# ---------------------------------------------------------------------------
# Test Data Factories
# ---------------------------------------------------------------------------

@pytest.fixture
def email_factory():
    """Factory for creating test Email model instances."""
    from src.models import Email

    def _create_email(
        email_id: str = None,
        message_id: str = None,
        from_email: str = "test@example.com",
        subject: str = "Test Subject",
        body: str = "Test body content for classification",
        category: str = None,
        confidence: float = None,
        status: str = "unread",
        **kwargs
    ) -> Email:
        email_id = email_id or str(uuid.uuid4())
        message_id = message_id or f"msg_{uuid.uuid4().hex[:12]}"

        return Email(
            email_id=email_id,
            message_id=message_id,
            thread_id=kwargs.get("thread_id", f"thread_{message_id}"),
            from_email=from_email,
            to_emails=kwargs.get("to_emails", ["recipient@example.com"]),
            subject=subject,
            body=body,
            date=kwargs.get("date", datetime.utcnow()),
            category=category,
            confidence=confidence,
            status=status,
            importance_level=kwargs.get("importance_level"),
        )

    return _create_email


@pytest.fixture
def email_message_factory():
    """Factory for creating GmailClient EmailMessage objects."""
    from src.services.gmail_client import EmailMessage

    def _create_message(
        message_id: str = None,
        from_email: str = "sender@example.com",
        subject: str = "Test Email Subject",
        body: str = "This is a test email body for testing purposes.",
        **kwargs
    ) -> EmailMessage:
        message_id = message_id or f"msg_{uuid.uuid4().hex[:12]}"

        return EmailMessage(
            message_id=message_id,
            thread_id=kwargs.get("thread_id", f"thread_{message_id}"),
            from_email=from_email,
            to_emails=kwargs.get("to_emails", ["recipient@example.com"]),
            subject=subject,
            body=body,
            date=kwargs.get("date", datetime.utcnow()),
            snippet=kwargs.get("snippet", body[:100]),
            labels=kwargs.get("labels", ["INBOX", "UNREAD"]),
            headers=kwargs.get("headers", {
                "from": from_email,
                "to": "recipient@example.com",
                "subject": subject,
                "date": "Wed, 01 Jan 2025 12:00:00 +0000",
            }),
        )

    return _create_message


@pytest.fixture
def classification_result_factory():
    """Factory for creating ClassificationResult objects."""
    from src.services.anthropic_client import ClassificationResult

    def _create_result(
        category: str = "Professional/Work",
        confidence: float = 0.85,
        reasoning: str = "Email contains work-related content",
        **kwargs
    ) -> ClassificationResult:
        return ClassificationResult(
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            key_phrases=kwargs.get("key_phrases", ["work", "meeting"]),
            model_used=kwargs.get("model_used", "claude-3-haiku-20240307"),
            input_tokens=kwargs.get("input_tokens", 150),
            output_tokens=kwargs.get("output_tokens", 75),
        )

    return _create_result


# ---------------------------------------------------------------------------
# Test Configuration
# ---------------------------------------------------------------------------

@pytest.fixture
def test_config():
    """Test configuration object with test values."""
    from src.config import AppConfig, DatabaseConfig, GmailConfig, AnthropicConfig

    return AppConfig(
        project_id="test-project",
        environment="test",
        database=DatabaseConfig(
            host="localhost",
            port=5433,
            name="test_email_agent",
            user="test_user",
            password="test_password",
        ),
        gmail=GmailConfig(
            oauth_client={"installed": {"client_id": "test"}},
            user_token={"token": "test", "refresh_token": "test"},
        ),
        anthropic=AnthropicConfig(
            api_key="test-api-key",
        ),
        confidence_threshold=0.8,
    )


@pytest.fixture
def categories():
    """Test email categories."""
    from src.config import CATEGORIES
    return CATEGORIES


# ---------------------------------------------------------------------------
# FastAPI Test Clients
# ---------------------------------------------------------------------------

@pytest.fixture
def test_client(mock_gmail_service, mock_anthropic_client, mock_gmail_credentials):
    """Synchronous FastAPI test client with mocked external services."""
    with patch("src.services.gmail_client.build", return_value=mock_gmail_service):
        with patch("src.services.gmail_client.Credentials", return_value=mock_gmail_credentials):
            with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
                from src.main import app
                with TestClient(app) as client:
                    yield client


@pytest_asyncio.fixture
async def async_test_client(mock_gmail_service, mock_anthropic_client, mock_gmail_credentials):
    """Async FastAPI test client with mocked external services."""
    with patch("src.services.gmail_client.build", return_value=mock_gmail_service):
        with patch("src.services.gmail_client.Credentials", return_value=mock_gmail_credentials):
            with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
                from src.main import app
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test"
                ) as client:
                    yield client


@pytest.fixture
def async_client_app():
    """Provide the FastAPI app for async client tests without mocking.

    Returns the app and a mock session for flexible test configuration.
    """
    from src.main import app

    mock_session = MagicMock()
    return app, mock_session


# ---------------------------------------------------------------------------
# Sample Test Data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_work_email():
    """Sample work-related email data."""
    return {
        "message_id": "msg_work_001",
        "from_email": "manager@company.com",
        "subject": "Q4 Planning Meeting - Action Required",
        "body": """Hi team,

Please review the attached agenda for our Q4 planning meeting scheduled for next Monday.

Key topics:
- Budget review
- Project timeline updates
- Resource allocation

Please come prepared with your department updates.

Best,
Manager""",
    }


@pytest.fixture
def sample_newsletter_email():
    """Sample newsletter email data."""
    return {
        "message_id": "msg_newsletter_001",
        "from_email": "newsletter@techdigest.com",
        "subject": "Weekly Tech Digest - Top Stories",
        "body": """This week in tech:

1. AI breakthroughs continue
2. New smartphone releases
3. Cloud computing trends

Click here to unsubscribe from this newsletter.

You're receiving this because you signed up at techdigest.com""",
    }


@pytest.fixture
def sample_promotional_email():
    """Sample promotional email data."""
    return {
        "message_id": "msg_promo_001",
        "from_email": "deals@retailstore.com",
        "subject": "FLASH SALE - 50% Off Everything!",
        "body": """Don't miss our biggest sale of the year!

50% OFF all items for the next 24 hours only.

Use code: FLASH50 at checkout.

Shop now: https://retailstore.com/sale

Unsubscribe | Privacy Policy""",
    }
