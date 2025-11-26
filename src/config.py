"""Configuration management for Gmail Agent.

Loads configuration from environment variables (set by Cloud Run from Secret Manager).
"""

import os
import json
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL database configuration."""
    host: str
    name: str
    user: str
    password: str
    port: int = 5432

    @property
    def connection_string(self) -> str:
        """SQLAlchemy async connection string."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_connection_string(self) -> str:
        """SQLAlchemy sync connection string (for CLI/migrations)."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass(frozen=True)
class GmailConfig:
    """Gmail OAuth configuration."""
    oauth_client: dict  # OAuth client credentials (app identity)
    user_token: dict    # User's access/refresh tokens

    @classmethod
    def from_env(cls) -> "GmailConfig":
        """Load Gmail config from environment variables."""
        oauth_client_json = os.environ.get("GMAIL_OAUTH_CLIENT", "{}")
        user_token_json = os.environ.get("GMAIL_USER_TOKEN", "{}")

        return cls(
            oauth_client=json.loads(oauth_client_json),
            user_token=json.loads(user_token_json),
        )


@dataclass(frozen=True)
class AnthropicConfig:
    """Anthropic API configuration."""
    api_key: str
    # Model selection for different tasks
    fast_model: str = "claude-3-haiku-20240307"      # Fast/cheap for categorization
    quality_model: str = "claude-sonnet-4-20250514"  # Quality for complex tasks

    @classmethod
    def from_env(cls) -> "AnthropicConfig":
        """Load Anthropic config from environment variables."""
        return cls(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )


@dataclass(frozen=True)
class AppConfig:
    """Main application configuration."""
    project_id: str
    environment: str
    database: DatabaseConfig
    gmail: GmailConfig
    anthropic: AnthropicConfig

    # Processing settings
    batch_size: int = 100
    confidence_threshold: float = 0.8  # Below this requires human approval

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load full configuration from environment variables."""
        return cls(
            project_id=os.environ.get("PROJECT_ID", "gmail-agent-prod"),
            environment=os.environ.get("ENVIRONMENT", "dev"),
            database=DatabaseConfig(
                host=os.environ.get("DATABASE_HOST", "localhost"),
                name=os.environ.get("DATABASE_NAME", "email_agent"),
                user=os.environ.get("DATABASE_USER", "agent_user"),
                password=os.environ.get("DATABASE_PASSWORD", ""),
                port=int(os.environ.get("DATABASE_PORT", "5432")),
            ),
            gmail=GmailConfig.from_env(),
            anthropic=AnthropicConfig.from_env(),
        )


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Get cached application configuration.

    Returns:
        AppConfig instance loaded from environment variables.
    """
    return AppConfig.from_env()


# Email categories for Phase 1 (simplified hierarchy)
CATEGORIES = {
    "Important": {
        "description": "Time-sensitive or critical emails requiring immediate attention",
        "keywords": ["urgent", "deadline", "interview", "offer", "critical", "action required", "ASAP"],
    },
    "Personal/Friends": {
        "description": "Emails from friends with informal tone",
        "domains": ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"],
    },
    "Personal/Family": {
        "description": "Emails from family members",
        "keywords": ["family", "mom", "dad", "sister", "brother", "reunion"],
    },
    "Professional/Recruiters": {
        "description": "Job-related emails from recruiters",
        "domains": ["linkedin.com", "greenhouse.io", "lever.co"],
        "keywords": ["opportunity", "position", "interview", "role", "hiring", "candidate"],
    },
    "Professional/Work": {
        "description": "Work-related professional correspondence",
        "keywords": ["meeting", "project", "deadline", "deliverable", "report"],
    },
    "Purchases/Orders": {
        "description": "Order confirmations and shipping notifications",
        "domains": ["amazon.com", "etsy.com", "ebay.com", "shopify.com"],
        "keywords": ["order", "shipped", "delivery", "tracking", "receipt"],
    },
    "Newsletters/Subscriptions": {
        "description": "Newsletter and subscription emails",
        "domains": ["substack.com"],
        "keywords": ["unsubscribe", "newsletter", "digest", "weekly"],
    },
    "Marketing/Promotions": {
        "description": "Promotional and marketing emails",
        "keywords": ["sale", "discount", "promo", "offer", "deal", "limited time"],
    },
}
