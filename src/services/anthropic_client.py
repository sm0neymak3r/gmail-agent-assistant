"""Anthropic Claude API client for email classification.

Provides a unified interface for Claude models with model selection
based on task complexity.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import get_config, AnthropicConfig

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of email classification."""
    category: str
    confidence: float
    reasoning: str
    key_phrases: list[str]
    model_used: str
    input_tokens: int
    output_tokens: int


class AnthropicClient:
    """Anthropic Claude API client.

    Provides model selection based on task:
    - Claude Haiku: Fast/cheap for initial categorization
    - Claude Sonnet: Quality for complex tasks or low-confidence escalation
    """

    def __init__(self, config: Optional[AnthropicConfig] = None):
        """Initialize Anthropic client.

        Args:
            config: Anthropic configuration. If None, loads from environment.
        """
        self.config = config or get_config().anthropic
        self._client = None

    @property
    def client(self) -> anthropic.Anthropic:
        """Get or create Anthropic client."""
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.config.api_key)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(anthropic.RateLimitError),
    )
    def classify_email(
        self,
        subject: str,
        from_email: str,
        body: str,
        categories: dict[str, dict],
        use_quality_model: bool = False,
    ) -> ClassificationResult:
        """Classify an email into a category.

        Args:
            subject: Email subject line
            from_email: Sender email address
            body: Email body (truncated to ~10k chars)
            categories: Dictionary of available categories with descriptions
            use_quality_model: If True, use Claude Sonnet instead of Haiku

        Returns:
            ClassificationResult with category, confidence, and reasoning
        """
        model = self.config.quality_model if use_quality_model else self.config.fast_model

        # Build category list for prompt
        category_descriptions = "\n".join(
            f"- {name}: {info.get('description', 'No description')}"
            for name, info in categories.items()
        )

        system_prompt = """You are an expert email classifier. Your job is to categorize emails accurately and explain your reasoning.

You must respond with ONLY a valid JSON object in this exact format:
{
  "category": "<exact category name from the list>",
  "confidence": <number between 0.0 and 1.0>,
  "reasoning": "<brief explanation of why this category was chosen>",
  "key_phrases": ["<phrase1>", "<phrase2>"]
}

Confidence guidelines:
- 0.9-1.0: Very certain (clear domain match, obvious keywords)
- 0.7-0.9: Confident (good keyword/pattern match)
- 0.5-0.7: Uncertain (ambiguous, could fit multiple categories)
- Below 0.5: Low confidence (no clear signals)

Be conservative with confidence scores. If unsure, use a lower score."""

        user_prompt = f"""Classify this email into exactly ONE of these categories:

{category_descriptions}

Email to classify:
From: {from_email}
Subject: {subject}
Body:
{body[:10000]}

Respond with ONLY a JSON object, no other text."""

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=500,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                system=system_prompt,
            )

            # Parse response
            content = response.content[0].text.strip()

            # Handle potential markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)

            logger.info(
                f"Classified email as {result['category']} "
                f"(confidence: {result['confidence']:.2f}) using {model}"
            )

            return ClassificationResult(
                category=result["category"],
                confidence=float(result["confidence"]),
                reasoning=result["reasoning"],
                key_phrases=result.get("key_phrases", []),
                model_used=model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification response: {e}")
            # Return low-confidence result for human review
            return ClassificationResult(
                category="Uncategorized",
                confidence=0.0,
                reasoning=f"Failed to parse model response: {str(e)[:100]}",
                key_phrases=[],
                model_used=model,
                input_tokens=0,
                output_tokens=0,
            )

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def classify_with_escalation(
        self,
        subject: str,
        from_email: str,
        body: str,
        categories: dict[str, dict],
        confidence_threshold: float = 0.7,
    ) -> ClassificationResult:
        """Classify email with automatic escalation to quality model.

        First tries the fast model (Haiku). If confidence is below threshold,
        escalates to quality model (Sonnet).

        Args:
            subject: Email subject line
            from_email: Sender email address
            body: Email body
            categories: Available categories
            confidence_threshold: Below this, escalate to quality model

        Returns:
            ClassificationResult from either fast or quality model
        """
        # First attempt with fast model
        result = self.classify_email(
            subject=subject,
            from_email=from_email,
            body=body,
            categories=categories,
            use_quality_model=False,
        )

        # Escalate if confidence is low
        if result.confidence < confidence_threshold:
            logger.info(
                f"Escalating classification from {result.model_used} "
                f"(confidence {result.confidence:.2f}) to quality model"
            )
            result = self.classify_email(
                subject=subject,
                from_email=from_email,
                body=body,
                categories=categories,
                use_quality_model=True,
            )

        return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(anthropic.RateLimitError),
    )
    def check_importance(
        self,
        subject: str,
        from_email: str,
        body: str,
    ) -> dict:
        """Check email importance level.

        Args:
            subject: Email subject line
            from_email: Sender email address
            body: Email body

        Returns:
            Dictionary with importance_level, score, and action_items
        """
        system_prompt = """You are an email importance analyzer. Evaluate emails for urgency and action requirements.

Respond with ONLY a valid JSON object:
{
  "importance_level": "<critical|high|normal|low>",
  "score": <number 0.0-1.0>,
  "action_items": ["<action1>", "<action2>"],
  "reasoning": "<brief explanation>"
}

Importance criteria:
- critical (0.9-1.0): Immediate action needed, deadlines today, interview scheduling
- high (0.7-0.9): Important but not immediate, requires response within days
- normal (0.4-0.7): Standard communication, no urgency
- low (0.0-0.4): FYI only, newsletters, promotions"""

        user_prompt = f"""Analyze importance of this email:

From: {from_email}
Subject: {subject}
Body:
{body[:5000]}

Respond with ONLY a JSON object."""

        try:
            response = self.client.messages.create(
                model=self.config.fast_model,
                max_tokens=300,
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
            )

            content = response.content[0].text.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            return json.loads(content)

        except (json.JSONDecodeError, anthropic.APIError) as e:
            logger.error(f"Importance check failed: {e}")
            return {
                "importance_level": "normal",
                "score": 0.5,
                "action_items": [],
                "reasoning": f"Analysis failed: {str(e)[:50]}",
            }
