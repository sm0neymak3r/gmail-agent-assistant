"""LangGraph workflows for email processing."""

from src.workflows.state import EmailState
from src.workflows.email_processor import EmailProcessor, create_workflow

__all__ = ["EmailState", "EmailProcessor", "create_workflow"]
