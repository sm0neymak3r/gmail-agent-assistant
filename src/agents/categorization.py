"""Categorization agent for email classification.

Uses Claude models to classify emails with confidence-based escalation.
"""

import logging
from typing import Any

from src.config import get_config, CATEGORIES
from src.services.anthropic_client import AnthropicClient, ClassificationResult
from src.workflows.state import EmailState

logger = logging.getLogger(__name__)


class CategorizationAgent:
    """Agent for categorizing emails using Claude models.

    Implements a two-tier model strategy:
    1. Fast model (Haiku) for initial classification
    2. Quality model (Sonnet) for low-confidence escalation
    """

    def __init__(self, anthropic_client: AnthropicClient | None = None):
        """Initialize categorization agent.

        Args:
            anthropic_client: Anthropic client instance. If None, creates one.
        """
        self.client = anthropic_client or AnthropicClient()
        self.categories = CATEGORIES

    def categorize(self, state: EmailState) -> EmailState:
        """Categorize an email and update state.

        This is the main node function for LangGraph workflow.

        Args:
            state: Current email processing state

        Returns:
            Updated state with category, confidence, and reasoning
        """
        config = get_config()

        logger.info(f"Categorizing email: {state['subject'][:50]}...")

        # Use the escalation strategy: fast model first, escalate if uncertain
        result = self.client.classify_with_escalation(
            subject=state["subject"],
            from_email=state["from_email"],
            body=state["body"],
            categories=self.categories,
            confidence_threshold=0.7,  # Escalate below this
        )

        # Update state with results
        state["category"] = result.category
        state["confidence"] = result.confidence
        state["reasoning"] = result.reasoning
        state["processing_step"] = "categorized"

        # Mark for human approval if confidence is below threshold
        state["needs_human_approval"] = result.confidence < config.confidence_threshold
        if state["needs_human_approval"]:
            state["approval_type"] = "categorization"
            logger.info(
                f"Email marked for human approval: {result.category} "
                f"(confidence: {result.confidence:.2f})"
            )

        return state

    def recategorize_with_feedback(
        self,
        state: EmailState,
        suggested_category: str | None = None,
    ) -> EmailState:
        """Re-categorize email with optional human feedback.

        Used when human reviewer suggests a different category.

        Args:
            state: Current email state
            suggested_category: Human-suggested category, if any

        Returns:
            Updated state with new classification
        """
        if suggested_category:
            # Human provided category directly
            state["category"] = suggested_category
            state["confidence"] = 1.0  # Human-verified
            state["reasoning"] = "Category set by human reviewer"
            state["needs_human_approval"] = False
        else:
            # Re-run classification with quality model
            result = self.client.classify_email(
                subject=state["subject"],
                from_email=state["from_email"],
                body=state["body"],
                categories=self.categories,
                use_quality_model=True,
            )
            state["category"] = result.category
            state["confidence"] = result.confidence
            state["reasoning"] = result.reasoning

        state["processing_step"] = "recategorized"
        return state


# Standalone function for LangGraph node
def categorize_email(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node function for email categorization.

    Args:
        state: Email state dictionary

    Returns:
        Updated state dictionary
    """
    agent = CategorizationAgent()
    return agent.categorize(state)
