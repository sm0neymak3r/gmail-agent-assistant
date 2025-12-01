"""CLI approval interface for email categorization review.

Uses Rich library for terminal UI. Connects to PostgreSQL via
SSH tunnel through the bastion host.

Usage:
    # First, set up SSH tunnel to bastion
    gcloud compute ssh gmail-agent-bastion-dev \
        --zone=us-central1-a \
        --tunnel-through-iap \
        -- -L 5432:<DB_PRIVATE_IP>:5432 -N &

    # Then run the CLI
    python -m src.cli.approval
"""

import sys
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from sqlalchemy import select, update

from src.config import get_config, CATEGORIES
from src.models import Email, Feedback, get_sync_session
from src.services.gmail_client import GmailClient


class ApprovalCLI:
    """Terminal interface for approving email categorizations.

    Provides keyboard-driven approval workflow:
    - [A]pprove: Accept proposed category
    - [D]eny: Reject and provide correct category
    - [S]kip: Skip for now
    - [V]iew: View full email content
    - [Q]uit: Exit the CLI
    """

    def __init__(self):
        """Initialize the CLI."""
        self.console = Console()
        self.config = get_config()
        self.Session = get_sync_session()
        self._gmail = None

    @property
    def gmail(self) -> GmailClient:
        """Lazy-load Gmail client."""
        if self._gmail is None:
            self._gmail = GmailClient()
        return self._gmail

    def run(self):
        """Run the approval CLI loop."""
        self.console.clear()
        self.console.print(
            Panel.fit(
                "[bold blue]Gmail Agent - Approval Interface[/bold blue]\n"
                "Review and approve email categorizations",
                border_style="blue",
            )
        )

        while True:
            try:
                # Fetch pending approvals
                pending = self._get_pending_approvals()

                if not pending:
                    self.console.print("\n[green]No pending approvals![/green]")
                    if not Confirm.ask("Check again?", default=False):
                        break
                    continue

                self.console.print(f"\n[bold]Found {len(pending)} pending approvals[/bold]\n")

                # Process each approval
                for idx, email in enumerate(pending, 1):
                    self.console.clear()
                    action = self._show_approval(email, idx, len(pending))

                    if action == "quit":
                        return
                    elif action == "approve":
                        self._approve(email)
                    elif action == "deny":
                        self._deny(email)
                    elif action == "skip":
                        continue

                self.console.print("\n[green]All pending approvals reviewed![/green]")
                if not Confirm.ask("Check for more?", default=False):
                    break

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted[/yellow]")
                break
            except Exception as e:
                self.console.print(f"\n[red]Error: {e}[/red]")
                if not Confirm.ask("Continue?", default=True):
                    break

    def _get_pending_approvals(self) -> list[Email]:
        """Fetch emails pending approval from database."""
        with self.Session() as session:
            result = session.execute(
                select(Email)
                .where(Email.status == "pending_approval")
                .order_by(Email.date.desc())
                .limit(50)
            )
            return list(result.scalars().all())

    def _show_approval(self, email: Email, idx: int, total: int) -> str:
        """Display approval prompt for an email.

        Args:
            email: Email to review
            idx: Current index
            total: Total pending count

        Returns:
            Action: "approve", "deny", "skip", "quit"
        """
        # Header
        self.console.print(
            Panel(
                f"[bold]Approval {idx}/{total}[/bold]",
                style="blue",
            )
        )

        # Email details table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("From:", email.from_email or "Unknown")
        table.add_row("Subject:", email.subject or "(No subject)")
        table.add_row(
            "Date:",
            email.date.strftime("%Y-%m-%d %H:%M") if email.date else "Unknown",
        )
        table.add_row("", "")
        table.add_row(
            "Proposed Category:",
            f"[yellow]{email.category or 'Unknown'}[/yellow]",
        )
        table.add_row(
            "Confidence:",
            self._format_confidence(email.confidence),
        )

        self.console.print(table)

        # Snippet
        if email.body:
            snippet = email.body[:300] + "..." if len(email.body) > 300 else email.body
            self.console.print(
                Panel(
                    snippet,
                    title="Preview",
                    border_style="dim",
                )
            )

        # Action prompt
        self.console.print()
        action = Prompt.ask(
            "[bold][A]pprove [D]eny [S]kip [V]iew [Q]uit[/bold]",
            choices=["a", "d", "s", "v", "q"],
            default="a",
        ).lower()

        if action == "a":
            return "approve"
        elif action == "d":
            return "deny"
        elif action == "s":
            return "skip"
        elif action == "v":
            self._view_full(email)
            return self._show_approval(email, idx, total)  # Re-prompt after viewing
        elif action == "q":
            return "quit"

        return "skip"

    def _format_confidence(self, confidence: Optional[float]) -> str:
        """Format confidence score with color."""
        if confidence is None:
            return "[dim]Unknown[/dim]"

        if confidence >= 0.8:
            color = "green"
        elif confidence >= 0.6:
            color = "yellow"
        else:
            color = "red"

        return f"[{color}]{confidence:.1%}[/{color}]"

    def _view_full(self, email: Email):
        """Display full email content."""
        self.console.clear()
        self.console.print(
            Panel(
                f"[bold]Full Email Content[/bold]\n"
                f"From: {email.from_email}\n"
                f"Subject: {email.subject}\n"
                f"Date: {email.date}",
                border_style="blue",
            )
        )

        if email.body:
            self.console.print(Panel(email.body, title="Body"))
        else:
            self.console.print("[dim]No body content[/dim]")

        Prompt.ask("\nPress Enter to continue")

    def _approve(self, email: Email):
        """Approve the proposed categorization."""
        with self.Session() as session:
            # Update email status
            session.execute(
                update(Email)
                .where(Email.email_id == email.email_id)
                .values(
                    status="labeled",
                    confidence=1.0,  # Human-verified
                    processed_at=datetime.utcnow(),
                )
            )

            # Record feedback
            feedback = Feedback(
                email_id=email.email_id,
                user_action="approved",
                proposed_category=email.category,
                final_category=email.category,
            )
            session.add(feedback)
            session.commit()

        # Apply Gmail label
        try:
            label_name = f"Agent/{email.category}"
            self.gmail.apply_label(email.message_id, label_name)
            self.console.print(f"[green]Approved and labeled as {email.category}[/green]")
        except Exception as e:
            self.console.print(f"[yellow]Approved but label failed: {e}[/yellow]")

    def _deny(self, email: Email):
        """Deny proposed category and get correct one."""
        # Show available categories
        self.console.print("\n[bold]Available categories:[/bold]")
        for idx, category in enumerate(CATEGORIES.keys(), 1):
            self.console.print(f"  {idx}. {category}")

        # Get correct category
        choice = Prompt.ask(
            "Enter category name or number",
            default=list(CATEGORIES.keys())[0],
        )

        # Handle numeric input
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(CATEGORIES):
                correct_category = list(CATEGORIES.keys())[idx]
            else:
                correct_category = choice
        except ValueError:
            correct_category = choice

        with self.Session() as session:
            # Update email
            session.execute(
                update(Email)
                .where(Email.email_id == email.email_id)
                .values(
                    category=correct_category,
                    status="labeled",
                    confidence=1.0,  # Human-verified
                    processed_at=datetime.utcnow(),
                )
            )

            # Record feedback
            feedback = Feedback(
                email_id=email.email_id,
                user_action="corrected",
                proposed_category=email.category,
                final_category=correct_category,
            )
            session.add(feedback)
            session.commit()

        # Apply Gmail label
        try:
            label_name = f"Agent/{correct_category}"
            self.gmail.apply_label(email.message_id, label_name)
            self.console.print(f"[green]Corrected to {correct_category}[/green]")
        except Exception as e:
            self.console.print(f"[yellow]Corrected but label failed: {e}[/yellow]")


def main():
    """Entry point for CLI."""
    cli = ApprovalCLI()
    cli.run()


if __name__ == "__main__":
    main()
