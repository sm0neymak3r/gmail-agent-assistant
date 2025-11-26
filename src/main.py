"""FastAPI application for Gmail Agent.

Provides HTTP endpoints for:
- Health checks
- Scheduled email processing (called by Cloud Scheduler)
- Manual processing triggers
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from src.config import get_config
from src.models import get_async_session, Email
from src.services.gmail_client import GmailClient
from src.services.anthropic_client import AnthropicClient
from src.workflows.email_processor import EmailProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Gmail Agent starting up...")
    config = get_config()
    logger.info(f"Environment: {config.environment}")
    logger.info(f"Project ID: {config.project_id}")
    yield
    logger.info("Gmail Agent shutting down...")


app = FastAPI(
    title="Gmail Agent",
    description="Multi-agent Gmail inbox management system",
    version="0.1.0",
    lifespan=lifespan,
)


# Request/Response models
class ProcessRequest(BaseModel):
    """Request body for /process endpoint."""
    trigger: str = "manual"  # "scheduled" or "manual"
    mode: str = "batch"  # "batch" or "single"
    query: str = "is:unread"  # Gmail search query
    max_emails: int = 100


class ProcessResponse(BaseModel):
    """Response body for /process endpoint."""
    status: str
    processed: int
    categorized: int
    pending_approval: int
    labeled: int
    errors: int
    duration_seconds: float
    error_details: list[dict[str, Any]] = []


class HealthResponse(BaseModel):
    """Response body for /health endpoint."""
    status: str
    service: str
    version: str
    environment: str
    checks: dict[str, str]


@app.get("/", response_model=dict)
async def root():
    """Root endpoint with basic service info."""
    config = get_config()
    return {
        "service": "gmail-agent",
        "version": "0.1.0",
        "environment": config.environment,
        "status": "running",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.

    Verifies:
    - Database connectivity
    - Gmail API credentials present
    - Anthropic API key configured
    """
    config = get_config()
    checks = {}

    # Check database
    try:
        async_session = get_async_session()
        async with async_session() as session:
            await session.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = f"error: {str(e)[:50]}"

    # Check Gmail credentials
    if config.gmail.oauth_client and config.gmail.user_token:
        checks["gmail_oauth"] = "configured"
    else:
        checks["gmail_oauth"] = "missing"

    # Check Anthropic API key
    if config.anthropic.api_key:
        checks["anthropic"] = "configured"
    else:
        checks["anthropic"] = "missing"

    # Determine overall status
    all_ok = all(
        v in ["ok", "configured"]
        for v in checks.values()
    )

    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        service="gmail-agent",
        version="0.1.0",
        environment=config.environment,
        checks=checks,
    )


@app.post("/process", response_model=ProcessResponse)
async def process_emails(
    request: ProcessRequest,
    background_tasks: BackgroundTasks,
):
    """Process emails endpoint.

    Called by Cloud Scheduler (hourly) or manually.

    Args:
        request: Processing parameters
        background_tasks: FastAPI background task manager

    Returns:
        Processing results summary
    """
    start_time = datetime.utcnow()
    logger.info(
        f"Processing triggered: trigger={request.trigger}, "
        f"mode={request.mode}, query='{request.query}'"
    )

    try:
        processor = EmailProcessor()
        results = await processor.process_batch(
            query=request.query,
            max_emails=request.max_emails,
        )

        duration = (datetime.utcnow() - start_time).total_seconds()

        return ProcessResponse(
            status="completed",
            processed=results["processed"],
            categorized=results["categorized"],
            pending_approval=results["pending_approval"],
            labeled=results["labeled"],
            errors=results["errors"],
            duration_seconds=duration,
            error_details=results.get("error_details", []),
        )

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        duration = (datetime.utcnow() - start_time).total_seconds()

        return ProcessResponse(
            status="failed",
            processed=0,
            categorized=0,
            pending_approval=0,
            labeled=0,
            errors=1,
            duration_seconds=duration,
            error_details=[{"error": str(e)}],
        )


@app.get("/pending")
async def get_pending_approvals():
    """Get emails pending human approval.

    Returns list of emails with confidence below threshold
    that need human review.
    """
    try:
        async_session = get_async_session()
        async with async_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Email)
                .where(Email.status == "pending_approval")
                .order_by(Email.date.desc())
                .limit(50)
            )
            emails = result.scalars().all()

            return {
                "count": len(emails),
                "emails": [
                    {
                        "email_id": e.email_id,
                        "message_id": e.message_id,
                        "from": e.from_email,
                        "subject": e.subject,
                        "date": e.date.isoformat() if e.date else None,
                        "proposed_category": e.category,
                        "confidence": e.confidence,
                    }
                    for e in emails
                ],
            }

    except Exception as e:
        logger.error(f"Failed to fetch pending approvals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/approve/{email_id}")
async def approve_categorization(
    email_id: str,
    category: str | None = None,
):
    """Approve or correct email categorization.

    Args:
        email_id: Email to approve
        category: Optional corrected category (if None, approves proposed)

    Returns:
        Updated email status
    """
    try:
        async_session = get_async_session()
        async with async_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Email).where(Email.email_id == email_id)
            )
            email = result.scalar_one_or_none()

            if not email:
                raise HTTPException(status_code=404, detail="Email not found")

            # Update category if provided
            if category:
                email.category = category

            email.status = "labeled"
            email.confidence = 1.0  # Human-verified
            email.processed_at = datetime.utcnow()

            # Apply Gmail label
            try:
                gmail = GmailClient()
                label_name = f"Agent/{email.category}"
                gmail.apply_label(email.message_id, label_name)
            except Exception as e:
                logger.error(f"Failed to apply Gmail label: {e}")

            # Record feedback
            from src.models import Feedback

            feedback = Feedback(
                email_id=email_id,
                user_action="approved" if not category else "corrected",
                proposed_category=email.category if not category else None,
                final_category=category or email.category,
            )
            session.add(feedback)

            await session.commit()

            return {
                "status": "approved",
                "email_id": email_id,
                "category": email.category,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Run with uvicorn when called directly
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
