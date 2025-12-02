"""CLI for reviewing and executing unsubscribe recommendations.

Provides batch review of detected unsubscribe options:
- View pending unsubscribe recommendations grouped by sender domain
- Execute one-click unsubscribe (opens in browser for confirmation)
- Skip or dismiss recommendations
- View sender statistics

Usage:
    # First, set up SSH tunnel to bastion
    gcloud compute ssh gmail-agent-bastion-dev \
        --zone=us-central1-a \
        --tunnel-through-iap \
        -- -L 5432:<DB_PRIVATE_IP>:5432 -N &

    # Then run the CLI
    python -m src.cli.unsubscribe
"""

import webbrowser
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from sqlalchemy import select, update, func

from src.config import get_config
from src.models import UnsubscribeQueue, Email, get_sync_session


class UnsubscribeCLI:
    """Terminal interface for reviewing unsubscribe recommendations.

    Provides keyboard-driven workflow:
    - [U]nsubscribe: Open unsubscribe link in browser
    - [S]kip: Skip for now (keep in queue)
    - [D]ismiss: Remove from queue permanently
    - [V]iew: View related email details
    - [Q]uit: Exit the CLI
    """

    def __init__(self):
        """Initialize the CLI."""
        self.console = Console()
        self.config = get_config()
        self.Session = get_sync_session()

    def run(self):
        """Run the unsubscribe review CLI loop."""
        self.console.clear()
        self.console.print(
            Panel.fit(
                "[bold blue]Gmail Agent - Unsubscribe Manager[/bold blue]\n"
                "Review and execute unsubscribe recommendations",
                border_style="blue",
            )
        )

        while True:
            try:
                # Show summary first
                self._show_summary()

                # Ask for action
                action = Prompt.ask(
                    "\n[bold]Options[/bold]",
                    choices=["review", "stats", "quit"],
                    default="review",
                )

                if action == "quit":
                    break
                elif action == "stats":
                    self._show_stats()
                elif action == "review":
                    self._review_queue()

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted[/yellow]")
                break
            except Exception as e:
                self.console.print(f"\n[red]Error: {e}[/red]")
                if not Confirm.ask("Continue?", default=True):
                    break

    def _show_summary(self):
        """Display summary of pending unsubscribe recommendations."""
        with self.Session() as session:
            # Count by status
            result = session.execute(
                select(
                    UnsubscribeQueue.status,
                    func.count(UnsubscribeQueue.queue_id)
                )
                .group_by(UnsubscribeQueue.status)
            )
            status_counts = dict(result.all())

            # Count unique senders
            result = session.execute(
                select(func.count(func.distinct(UnsubscribeQueue.sender)))
                .where(UnsubscribeQueue.status == "pending")
            )
            unique_senders = result.scalar() or 0

        pending = status_counts.get("pending", 0)
        executed = status_counts.get("executed", 0)
        skipped = status_counts.get("skipped", 0)

        table = Table(title="Unsubscribe Queue Summary", show_header=False)
        table.add_column("Status")
        table.add_column("Count", justify="right")

        table.add_row("[yellow]Pending[/yellow]", str(pending))
        table.add_row("[green]Executed[/green]", str(executed))
        table.add_row("[dim]Skipped[/dim]", str(skipped))
        table.add_row("", "")
        table.add_row("[bold]Unique Senders[/bold]", str(unique_senders))

        self.console.print(table)

    def _show_stats(self):
        """Show statistics by sender domain."""
        with self.Session() as session:
            result = session.execute(
                select(
                    UnsubscribeQueue.sender,
                    func.count(UnsubscribeQueue.queue_id).label("count"),
                    func.min(UnsubscribeQueue.created_at).label("first_seen"),
                )
                .where(UnsubscribeQueue.status == "pending")
                .group_by(UnsubscribeQueue.sender)
                .order_by(func.count(UnsubscribeQueue.queue_id).desc())
                .limit(20)
            )
            rows = result.all()

        if not rows:
            self.console.print("[dim]No pending unsubscribe recommendations[/dim]")
            return

        table = Table(title="Top Senders with Unsubscribe Options")
        table.add_column("Sender", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("First Seen")

        for sender, count, first_seen in rows:
            date_str = first_seen.strftime("%Y-%m-%d") if first_seen else "Unknown"
            table.add_row(sender, str(count), date_str)

        self.console.print(table)
        Prompt.ask("\nPress Enter to continue")

    def _review_queue(self):
        """Review pending unsubscribe recommendations."""
        while True:
            # Fetch pending items grouped by sender
            pending = self._get_pending_by_sender()

            if not pending:
                self.console.print("\n[green]No pending unsubscribe recommendations![/green]")
                break

            self.console.print(f"\n[bold]Found {len(pending)} senders with pending recommendations[/bold]\n")

            # Process each sender
            for idx, (sender, items) in enumerate(pending.items(), 1):
                self.console.clear()
                action = self._show_sender_review(sender, items, idx, len(pending))

                if action == "quit":
                    return
                elif action == "unsubscribe":
                    self._execute_unsubscribe(items)
                elif action == "dismiss":
                    self._dismiss_items(items)
                elif action == "skip":
                    continue

            self.console.print("\n[green]All pending recommendations reviewed![/green]")
            if not Confirm.ask("Check for more?", default=False):
                break

    def _get_pending_by_sender(self) -> dict[str, list[UnsubscribeQueue]]:
        """Fetch pending items grouped by sender."""
        with self.Session() as session:
            result = session.execute(
                select(UnsubscribeQueue)
                .where(UnsubscribeQueue.status == "pending")
                .order_by(UnsubscribeQueue.sender, UnsubscribeQueue.created_at.desc())
                .limit(100)
            )
            items = list(result.scalars().all())

        # Group by sender
        grouped = {}
        for item in items:
            sender = item.sender
            if sender not in grouped:
                grouped[sender] = []
            grouped[sender].append(item)

        return grouped

    def _show_sender_review(
        self,
        sender: str,
        items: list[UnsubscribeQueue],
        idx: int,
        total: int,
    ) -> str:
        """Display review prompt for a sender.

        Args:
            sender: Sender email/domain
            items: Unsubscribe queue items for this sender
            idx: Current index
            total: Total sender count

        Returns:
            Action: "unsubscribe", "dismiss", "skip", "quit"
        """
        # Get the first item with a valid unsubscribe link
        item = items[0]
        for i in items:
            if i.unsubscribe_link:
                item = i
                break

        # Header
        self.console.print(
            Panel(
                f"[bold]Sender {idx}/{total}[/bold]",
                style="blue",
            )
        )

        # Sender details table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Sender:", sender)
        table.add_row("Emails:", str(len(items)))
        table.add_row("Method:", f"[cyan]{item.method}[/cyan]" if item.method else "Unknown")

        if item.unsubscribe_link:
            link_display = item.unsubscribe_link[:80] + "..." if len(item.unsubscribe_link) > 80 else item.unsubscribe_link
            table.add_row("Link:", link_display)

        self.console.print(table)

        # Method explanation
        method_info = {
            "one-click": "[green]RFC 8058 one-click unsubscribe - Most reliable[/green]",
            "mailto": "[yellow]Email-based unsubscribe - Sends an email[/yellow]",
            "http": "[yellow]HTTP link unsubscribe - Opens in browser[/yellow]",
        }
        if item.method in method_info:
            self.console.print(f"\n{method_info[item.method]}")

        # Action prompt
        self.console.print()
        action = Prompt.ask(
            "[bold][U]nsubscribe [D]ismiss [S]kip [V]iew [Q]uit[/bold]",
            choices=["u", "d", "s", "v", "q"],
            default="s",
        ).lower()

        if action == "u":
            return "unsubscribe"
        elif action == "d":
            return "dismiss"
        elif action == "s":
            return "skip"
        elif action == "v":
            self._view_email(item)
            return self._show_sender_review(sender, items, idx, total)
        elif action == "q":
            return "quit"

        return "skip"

    def _view_email(self, item: UnsubscribeQueue):
        """View the associated email."""
        with self.Session() as session:
            email = session.execute(
                select(Email).where(Email.email_id == item.email_id)
            ).scalar_one_or_none()

        self.console.clear()

        if email:
            self.console.print(
                Panel(
                    f"[bold]Email Details[/bold]\n"
                    f"From: {email.from_email}\n"
                    f"Subject: {email.subject}\n"
                    f"Date: {email.date}",
                    border_style="blue",
                )
            )
            if email.body:
                preview = email.body[:500] + "..." if len(email.body) > 500 else email.body
                self.console.print(Panel(preview, title="Preview"))
        else:
            self.console.print("[dim]Email not found in database[/dim]")

        Prompt.ask("\nPress Enter to continue")

    def _execute_unsubscribe(self, items: list[UnsubscribeQueue]):
        """Execute unsubscribe for sender.

        Opens the unsubscribe link in the browser for user confirmation.
        """
        # Find the best item with a link
        item = None
        for i in items:
            if i.unsubscribe_link:
                item = i
                break

        if not item or not item.unsubscribe_link:
            self.console.print("[red]No valid unsubscribe link found[/red]")
            return

        link = item.unsubscribe_link

        if item.method == "mailto":
            # Handle mailto links
            self.console.print(f"\n[yellow]This is an email-based unsubscribe.[/yellow]")
            self.console.print(f"Send email to: {link}")
            if Confirm.ask("Open email client?", default=True):
                webbrowser.open(f"mailto:{link}?subject=Unsubscribe")
        else:
            # Handle HTTP links (including one-click)
            self.console.print(f"\n[yellow]Opening unsubscribe link in browser...[/yellow]")
            self.console.print(f"Link: {link[:100]}...")
            if Confirm.ask("Open in browser?", default=True):
                webbrowser.open(link)

        # Mark as executed after user confirms
        if Confirm.ask("\nDid you complete the unsubscribe?", default=True):
            with self.Session() as session:
                for i in items:
                    session.execute(
                        update(UnsubscribeQueue)
                        .where(UnsubscribeQueue.queue_id == i.queue_id)
                        .values(
                            status="executed",
                            user_action="unsubscribed",
                            executed_at=datetime.utcnow(),
                        )
                    )
                session.commit()
            self.console.print("[green]Marked as unsubscribed![/green]")
        else:
            self.console.print("[yellow]Keeping in queue for later[/yellow]")

    def _dismiss_items(self, items: list[UnsubscribeQueue]):
        """Dismiss items from the queue."""
        with self.Session() as session:
            for item in items:
                session.execute(
                    update(UnsubscribeQueue)
                    .where(UnsubscribeQueue.queue_id == item.queue_id)
                    .values(
                        status="skipped",
                        user_action="dismissed",
                    )
                )
            session.commit()
        self.console.print("[dim]Dismissed from queue[/dim]")


def main():
    """Entry point for CLI."""
    cli = UnsubscribeCLI()
    cli.run()


if __name__ == "__main__":
    main()
