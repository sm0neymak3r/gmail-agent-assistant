"""Unit tests for Email model.

Tests database model validation and constraints.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select


class TestEmailModel:
    """Tests for Email SQLAlchemy model."""

    @pytest.mark.asyncio
    async def test_email_created_with_required_fields(self, async_session):
        """Test that email can be created with required fields."""
        from src.models import Email

        email = Email(
            email_id=str(uuid4()),
            message_id="msg_test_123",
            thread_id="thread_test_123",
            from_email="sender@example.com",
            subject="Test Subject",
            date=datetime.utcnow(),
            status="fetched",
        )

        async_session.add(email)
        await async_session.commit()

        result = await async_session.execute(
            select(Email).where(Email.message_id == "msg_test_123")
        )
        saved_email = result.scalar_one()

        assert saved_email.message_id == "msg_test_123"
        assert saved_email.from_email == "sender@example.com"
        assert saved_email.status == "fetched"

    @pytest.mark.asyncio
    async def test_email_defaults_are_set(self, async_session):
        """Test that email model defaults are properly set."""
        from src.models import Email

        email = Email(
            email_id=str(uuid4()),
            message_id="msg_defaults_test",
            thread_id="thread_defaults",
            from_email="test@test.com",
            subject="Test",
            date=datetime.utcnow(),
            status="fetched",
        )

        async_session.add(email)
        await async_session.commit()

        result = await async_session.execute(
            select(Email).where(Email.message_id == "msg_defaults_test")
        )
        saved_email = result.scalar_one()

        # Check defaults
        assert saved_email.created_at is not None
        assert saved_email.category is None
        assert saved_email.confidence is None

    @pytest.mark.asyncio
    async def test_email_unique_message_id_constraint(self, async_session):
        """Test that duplicate message_ids are rejected."""
        from src.models import Email
        from sqlalchemy.exc import IntegrityError

        email1 = Email(
            email_id=str(uuid4()),
            message_id="msg_duplicate",
            thread_id="thread_1",
            from_email="test@test.com",
            subject="First Email",
            date=datetime.utcnow(),
            status="fetched",
        )
        async_session.add(email1)
        await async_session.commit()

        email2 = Email(
            email_id=str(uuid4()),
            message_id="msg_duplicate",  # Same message_id
            thread_id="thread_2",
            from_email="other@test.com",
            subject="Second Email",
            date=datetime.utcnow(),
            status="fetched",
        )
        async_session.add(email2)

        with pytest.raises(IntegrityError):
            await async_session.commit()

    @pytest.mark.asyncio
    async def test_email_status_can_be_updated(self, async_session):
        """Test that email status can be updated."""
        from src.models import Email

        email_id = str(uuid4())
        email = Email(
            email_id=email_id,
            message_id="msg_status_update",
            thread_id="thread_status",
            from_email="test@test.com",
            subject="Test",
            date=datetime.utcnow(),
            status="fetched",
        )
        async_session.add(email)
        await async_session.commit()

        # Update status
        email.status = "categorized"
        email.category = "Professional/Work"
        email.confidence = 0.92
        await async_session.commit()

        result = await async_session.execute(
            select(Email).where(Email.email_id == email_id)
        )
        updated_email = result.scalar_one()

        assert updated_email.status == "categorized"
        assert updated_email.category == "Professional/Work"
        assert updated_email.confidence == 0.92

    @pytest.mark.asyncio
    async def test_email_stores_body_content(self, async_session):
        """Test that email body text is stored correctly."""
        from src.models import Email

        long_body = "This is a test email body. " * 100
        email = Email(
            email_id=str(uuid4()),
            message_id="msg_body_test",
            thread_id="thread_body",
            from_email="test@test.com",
            subject="Test Body Storage",
            body=long_body,
            date=datetime.utcnow(),
            status="fetched",
        )

        async_session.add(email)
        await async_session.commit()

        result = await async_session.execute(
            select(Email).where(Email.message_id == "msg_body_test")
        )
        saved_email = result.scalar_one()

        assert saved_email.body == long_body

    @pytest.mark.asyncio
    async def test_email_date_field(self, async_session):
        """Test that email date is stored correctly."""
        from src.models import Email

        test_date = datetime(2025, 1, 15, 10, 30, 0)
        email = Email(
            email_id=str(uuid4()),
            message_id="msg_date_test",
            thread_id="thread_date",
            from_email="test@test.com",
            subject="Test Date",
            date=test_date,
            status="fetched",
        )

        async_session.add(email)
        await async_session.commit()

        result = await async_session.execute(
            select(Email).where(Email.message_id == "msg_date_test")
        )
        saved_email = result.scalar_one()

        assert saved_email.date == test_date


class TestFeedbackModel:
    """Tests for Feedback SQLAlchemy model."""

    @pytest.mark.asyncio
    async def test_feedback_records_approval(self, async_session, email_factory):
        """Test that feedback model records user approval."""
        from src.models import Feedback, Email

        # Create email first
        email = email_factory(
            email_id="email-for-feedback",
            message_id="msg_feedback_test",
            status="pending_approval",
        )
        async_session.add(email)
        await async_session.commit()

        feedback = Feedback(
            email_id="email-for-feedback",
            user_action="approved",
            proposed_category="Professional/Work",
            final_category="Professional/Work",
        )
        async_session.add(feedback)
        await async_session.commit()

        result = await async_session.execute(
            select(Feedback).where(Feedback.email_id == "email-for-feedback")
        )
        saved_feedback = result.scalar_one()

        assert saved_feedback.user_action == "approved"
        assert saved_feedback.proposed_category == "Professional/Work"

    @pytest.mark.asyncio
    async def test_feedback_records_correction(self, async_session, email_factory):
        """Test that feedback model records category correction."""
        from src.models import Feedback

        email = email_factory(
            email_id="email-for-correction",
            message_id="msg_correction_test",
            status="pending_approval",
        )
        async_session.add(email)
        await async_session.commit()

        feedback = Feedback(
            email_id="email-for-correction",
            user_action="corrected",
            proposed_category="Marketing/Promotions",
            final_category="Newsletters/Subscriptions",
        )
        async_session.add(feedback)
        await async_session.commit()

        result = await async_session.execute(
            select(Feedback).where(Feedback.email_id == "email-for-correction")
        )
        saved_feedback = result.scalar_one()

        assert saved_feedback.user_action == "corrected"
        assert saved_feedback.proposed_category == "Marketing/Promotions"
        assert saved_feedback.final_category == "Newsletters/Subscriptions"


class TestProcessingLogModel:
    """Tests for ProcessingLog SQLAlchemy model."""

    @pytest.mark.asyncio
    async def test_processing_log_records_action(self, async_session):
        """Test that processing log records processing actions."""
        from src.models import ProcessingLog

        log = ProcessingLog(
            email_id="email-processed",
            agent="categorization",
            action="categorized",
            status="success",
        )
        async_session.add(log)
        await async_session.commit()

        result = await async_session.execute(
            select(ProcessingLog).where(ProcessingLog.email_id == "email-processed")
        )
        saved_log = result.scalar_one()

        assert saved_log.action == "categorized"
        assert saved_log.agent == "categorization"
        assert saved_log.status == "success"

    @pytest.mark.asyncio
    async def test_processing_log_timestamp_is_set(self, async_session):
        """Test that processing log timestamp is automatically set."""
        from src.models import ProcessingLog

        log = ProcessingLog(
            email_id="email-timestamp-test",
            agent="labeling",
            action="labeled",
            status="success",
        )
        async_session.add(log)
        await async_session.commit()

        result = await async_session.execute(
            select(ProcessingLog).where(
                ProcessingLog.email_id == "email-timestamp-test"
            )
        )
        saved_log = result.scalar_one()

        assert saved_log.timestamp is not None
