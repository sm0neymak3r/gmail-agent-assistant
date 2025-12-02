"""Importance Agent for multi-factor urgency scoring.

Uses multiple signals to determine email importance:
- Sender authority (VIP list, domain matching)
- Urgency keywords detection
- Deadline/date extraction
- Financial signals
- Thread activity
- Recipient position (TO vs CC)
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Optional

import yaml

from src.config import get_config
from src.services.anthropic_client import AnthropicClient
from src.services.gmail_client import GmailClient
from src.workflows.state import EmailState

logger = logging.getLogger(__name__)


# Factor weights for importance scoring
IMPORTANCE_WEIGHTS = {
    "sender_authority": 0.25,
    "urgency_keywords": 0.20,
    "deadline_detection": 0.20,
    "financial_signals": 0.15,
    "thread_activity": 0.10,
    "recipient_position": 0.10,
}

# Urgency keywords to detect
URGENCY_KEYWORDS = [
    "urgent", "asap", "immediately", "deadline", "action required",
    "time sensitive", "critical", "important", "priority", "respond",
    "by today", "by tomorrow", "end of day", "eod", "cob",
    "final notice", "last chance", "expiring", "expires",
]

# Financial signal keywords
FINANCIAL_KEYWORDS = [
    "invoice", "payment", "contract", "agreement", "quote", "proposal",
    "purchase order", "po #", "amount due", "balance", "overdue",
    "wire transfer", "ach", "payable", "receivable", "billing",
    "$", "usd", "eur", "gbp",
]


@dataclass
class VIPSender:
    """VIP sender configuration."""
    pattern: str
    name: Optional[str] = None
    boost: float = 0.3


def load_vip_config() -> tuple[list[VIPSender], list[dict]]:
    """Load VIP sender configuration from YAML file.

    Returns:
        Tuple of (vip_senders list, vip_domains list)
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "vip_senders.yaml"

    if not config_path.exists():
        logger.warning(f"VIP config not found at {config_path}")
        return [], []

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        vip_senders = [
            VIPSender(
                pattern=s["pattern"],
                name=s.get("name"),
                boost=s.get("boost", 0.3)
            )
            for s in (config.get("vip_senders") or [])
        ]

        vip_domains = config.get("vip_domains") or []

        return vip_senders, vip_domains

    except Exception as e:
        logger.error(f"Error loading VIP config: {e}")
        return [], []


class ImportanceAgent:
    """Agent for scoring email importance using multiple factors.

    Implements multi-factor scoring:
    - Sender authority (0.25): VIP list, domain matching
    - Urgency keywords (0.20): Detect urgent language
    - Deadline detection (0.20): Extract and evaluate dates
    - Financial signals (0.15): Money, invoices, contracts
    - Thread activity (0.10): Multiple replies indicate importance
    - Recipient position (0.10): Direct TO vs CC'd
    """

    def __init__(
        self,
        gmail_client: Optional[GmailClient] = None,
        anthropic_client: Optional[AnthropicClient] = None,
    ):
        """Initialize importance agent.

        Args:
            gmail_client: Gmail client for thread lookups
            anthropic_client: Anthropic client for action item extraction
        """
        self.gmail = gmail_client
        self.anthropic = anthropic_client or AnthropicClient()
        self.vip_senders, self.vip_domains = load_vip_config()

    def check_importance(self, state: EmailState) -> EmailState:
        """Score email importance and update state.

        Args:
            state: Current email processing state

        Returns:
            Updated state with importance scoring
        """
        logger.info(f"Checking importance for: {state['subject'][:50]}...")

        factors = {}

        # Score each factor
        factors["sender_authority"] = self._score_sender_authority(state)
        factors["urgency_keywords"] = self._score_urgency_keywords(state)
        factors["deadline_detection"] = self._score_deadline_detection(state)
        factors["financial_signals"] = self._score_financial_signals(state)
        factors["thread_activity"] = self._score_thread_activity(state)
        factors["recipient_position"] = self._score_recipient_position(state)

        # Calculate weighted score
        total_score = sum(
            factors[factor] * weight
            for factor, weight in IMPORTANCE_WEIGHTS.items()
        )

        # Determine importance level
        importance_level = self._score_to_level(total_score)

        # Extract action items using LLM
        action_items = self._extract_action_items(state)

        # Update state
        state["importance_score"] = total_score
        state["importance_level"] = importance_level
        state["importance_factors"] = factors
        state["action_items"] = action_items
        state["processing_step"] = "importance_checked"

        logger.info(
            f"Importance: {importance_level} (score: {total_score:.2f}), "
            f"factors: {factors}"
        )

        return state

    def _score_sender_authority(self, state: EmailState) -> float:
        """Score based on sender VIP status and domain.

        Args:
            state: Email state

        Returns:
            Score 0.0-1.0
        """
        from_email = state.get("from_email", "").lower()

        # Check VIP senders (exact or pattern match)
        for vip in self.vip_senders:
            pattern = vip.pattern.lower()
            if "%" in pattern:
                # Convert SQL LIKE pattern to regex
                regex_pattern = "^" + pattern.replace("%", ".*") + "$"
                if re.match(regex_pattern, from_email):
                    return min(1.0, 0.7 + vip.boost)
            elif from_email == pattern:
                return min(1.0, 0.7 + vip.boost)

        # Check VIP domains
        for domain_config in self.vip_domains:
            domain = domain_config.get("domain", "").lower()
            if from_email.endswith(f"@{domain}"):
                boost = domain_config.get("boost", 0.2)
                return min(1.0, 0.5 + boost)

        # No VIP match
        return 0.3

    def _score_urgency_keywords(self, state: EmailState) -> float:
        """Score based on urgency keywords in subject and body.

        Args:
            state: Email state

        Returns:
            Score 0.0-1.0
        """
        text = f"{state.get('subject', '')} {state.get('body', '')[:2000]}".lower()

        matches = sum(1 for kw in URGENCY_KEYWORDS if kw in text)

        if matches == 0:
            return 0.0
        elif matches == 1:
            return 0.5
        elif matches == 2:
            return 0.7
        else:
            return min(1.0, 0.8 + (matches - 2) * 0.1)

    def _score_deadline_detection(self, state: EmailState) -> float:
        """Score based on deadline proximity.

        Args:
            state: Email state

        Returns:
            Score 0.0-1.0
        """
        text = f"{state.get('subject', '')} {state.get('body', '')[:3000]}".lower()

        # Look for date-related patterns
        today_patterns = [
            r"\btoday\b", r"\bby today\b", r"\bend of day\b", r"\beod\b"
        ]
        tomorrow_patterns = [
            r"\btomorrow\b", r"\bby tomorrow\b"
        ]
        week_patterns = [
            r"\bthis week\b", r"\bby friday\b", r"\bby monday\b",
            r"\bwithin \d+ days?\b", r"\bin \d+ days?\b"
        ]

        for pattern in today_patterns:
            if re.search(pattern, text):
                return 1.0

        for pattern in tomorrow_patterns:
            if re.search(pattern, text):
                return 0.8

        for pattern in week_patterns:
            if re.search(pattern, text):
                return 0.5

        # Look for specific dates
        date_pattern = r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"
        if re.search(date_pattern, text):
            return 0.4

        return 0.0

    def _score_financial_signals(self, state: EmailState) -> float:
        """Score based on financial content.

        Args:
            state: Email state

        Returns:
            Score 0.0-1.0
        """
        text = f"{state.get('subject', '')} {state.get('body', '')[:2000]}".lower()

        matches = sum(1 for kw in FINANCIAL_KEYWORDS if kw in text)

        # Look for currency amounts
        currency_pattern = r"[$£€]\s*[\d,]+\.?\d*"
        currency_matches = len(re.findall(currency_pattern, text))

        total_signals = matches + currency_matches

        if total_signals == 0:
            return 0.0
        elif total_signals <= 2:
            return 0.5
        elif total_signals <= 4:
            return 0.7
        else:
            return 0.9

    def _score_thread_activity(self, state: EmailState) -> float:
        """Score based on thread activity (reply count).

        Args:
            state: Email state

        Returns:
            Score 0.0-1.0
        """
        thread_id = state.get("thread_id")
        if not thread_id or not self.gmail:
            return 0.3  # Default score when we can't check

        try:
            # Fetch thread to count messages
            thread = self.gmail.service.users().threads().get(
                userId="me",
                id=thread_id,
                format="minimal"
            ).execute()

            message_count = len(thread.get("messages", []))

            if message_count <= 1:
                return 0.2
            elif message_count <= 3:
                return 0.5
            elif message_count <= 5:
                return 0.7
            else:
                return 0.9

        except Exception as e:
            logger.warning(f"Error fetching thread {thread_id}: {e}")
            return 0.3

    def _score_recipient_position(self, state: EmailState) -> float:
        """Score based on recipient position (TO vs CC).

        Args:
            state: Email state

        Returns:
            Score 0.0-1.0
        """
        headers = state.get("headers", {})
        to_field = headers.get("to", "").lower()
        cc_field = headers.get("cc", "").lower()

        # Check if user's email appears to be in TO or CC
        # Note: In a real implementation, you'd check against the user's actual email
        # For now, we assume being in TO is more important

        # If there's a TO field and no CC, likely direct recipient
        if to_field and not cc_field:
            return 0.8

        # If there's a CC field, check relative size
        if to_field and cc_field:
            to_count = len(to_field.split(","))
            cc_count = len(cc_field.split(","))

            # If TO has few recipients, more personal/important
            if to_count <= 2:
                return 0.7
            elif to_count <= 5:
                return 0.5
            else:
                return 0.3

        return 0.5

    def _score_to_level(
        self, score: float
    ) -> Literal["critical", "high", "normal", "low"]:
        """Convert numerical score to importance level.

        Args:
            score: Numerical importance score (0.0-1.0)

        Returns:
            Importance level string
        """
        if score >= 0.9:
            return "critical"
        elif score >= 0.7:
            return "high"
        elif score >= 0.4:
            return "normal"
        else:
            return "low"

    def _extract_action_items(self, state: EmailState) -> list[str]:
        """Extract action items from email using LLM.

        Args:
            state: Email state

        Returns:
            List of action item strings
        """
        # Only extract if importance seems high enough
        if state.get("importance_score", 0) < 0.4:
            return []

        try:
            system_prompt = """You are an expert at extracting action items from emails.
Extract specific, actionable tasks from the email. Each action item should be:
- Clear and specific
- Actionable (something the recipient needs to do)
- Include any deadlines mentioned

Respond with ONLY a JSON array of strings. If no action items, respond with [].

Example response: ["Review and sign contract by Friday", "Schedule meeting with team"]"""

            user_prompt = f"""Extract action items from this email:

Subject: {state.get('subject', '')}
From: {state.get('from_email', '')}

Body:
{state.get('body', '')[:3000]}

Respond with ONLY a JSON array of action items."""

            response = self.anthropic.client.messages.create(
                model=self.anthropic.config.fast_model,
                max_tokens=300,
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
            )

            content = response.content[0].text.strip()

            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            action_items = json.loads(content)

            if isinstance(action_items, list):
                return [str(item) for item in action_items[:5]]  # Limit to 5 items

            return []

        except Exception as e:
            logger.warning(f"Error extracting action items: {e}")
            return []


# Standalone function for LangGraph node
def check_importance(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node function for importance checking.

    Args:
        state: Email state dictionary

    Returns:
        Updated state dictionary

    Raises:
        Exception: Re-raises any exception to trigger workflow retry
    """
    try:
        # Create Gmail client for thread lookups
        gmail_client = GmailClient()
        agent = ImportanceAgent(gmail_client=gmail_client)
        return agent.check_importance(state)
    except Exception as e:
        logger.error(f"Importance agent failed: {e}")
        # Re-raise to trigger workflow retry per user requirement
        raise
