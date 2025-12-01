#!/usr/bin/env python3
"""Test harness for Gmail Agent batch processing.

This script provides a safe way to test the email processing pipeline:
1. Dry-run mode: Fetch and analyze emails without processing
2. Sample mode: Process a small sample of emails
3. Full mode: Process all matching emails

Usage:
    # Dry run - just count and analyze emails
    python scripts/test_batch.py --query "after:2024/11/01 before:2025/02/01" --dry-run

    # Process a sample of 10 emails
    python scripts/test_batch.py --query "after:2024/11/01 before:2025/02/01" --sample 10

    # Process all (use with caution!)
    python scripts/test_batch.py --query "after:2024/11/01 before:2025/02/01" --process-all
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.gmail_client import GmailClient, GmailConfig
from src.services.anthropic_client import AnthropicClient
from src.config import get_config, CATEGORIES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Anthropic pricing (as of 2024) - approximate
PRICING = {
    "claude-3-haiku-20240307": {
        "input": 0.25 / 1_000_000,   # $0.25 per 1M input tokens
        "output": 1.25 / 1_000_000,  # $1.25 per 1M output tokens
    },
    "claude-sonnet-4-20250514": {
        "input": 3.00 / 1_000_000,   # $3.00 per 1M input tokens
        "output": 15.00 / 1_000_000, # $15.00 per 1M output tokens
    },
}

# Estimate tokens per email (rough approximation)
AVG_INPUT_TOKENS = 1500   # Subject + body + prompt
AVG_OUTPUT_TOKENS = 150   # JSON response


def estimate_cost(email_count: int, escalation_rate: float = 0.3) -> dict:
    """Estimate Anthropic API cost for processing emails.

    Args:
        email_count: Number of emails to process
        escalation_rate: Estimated rate of escalation to Sonnet (0.0-1.0)

    Returns:
        Cost breakdown dictionary
    """
    haiku_calls = email_count
    sonnet_calls = int(email_count * escalation_rate)

    haiku_pricing = PRICING["claude-3-haiku-20240307"]
    sonnet_pricing = PRICING["claude-sonnet-4-20250514"]

    haiku_input_cost = haiku_calls * AVG_INPUT_TOKENS * haiku_pricing["input"]
    haiku_output_cost = haiku_calls * AVG_OUTPUT_TOKENS * haiku_pricing["output"]

    sonnet_input_cost = sonnet_calls * AVG_INPUT_TOKENS * sonnet_pricing["input"]
    sonnet_output_cost = sonnet_calls * AVG_OUTPUT_TOKENS * sonnet_pricing["output"]

    return {
        "email_count": email_count,
        "haiku_calls": haiku_calls,
        "sonnet_calls": sonnet_calls,
        "haiku_cost": haiku_input_cost + haiku_output_cost,
        "sonnet_cost": sonnet_input_cost + sonnet_output_cost,
        "total_cost": (haiku_input_cost + haiku_output_cost +
                      sonnet_input_cost + sonnet_output_cost),
        "escalation_rate": escalation_rate,
    }


def analyze_emails(emails: list) -> dict:
    """Analyze a batch of emails for insights.

    Args:
        emails: List of EmailMessage objects

    Returns:
        Analysis dictionary
    """
    if not emails:
        return {"count": 0}

    # Date distribution
    dates = [e.date.date() for e in emails if e.date]
    date_counts = Counter(dates)

    # Month distribution
    months = [e.date.strftime("%Y-%m") for e in emails if e.date]
    month_counts = Counter(months)

    # Sender domains
    domains = []
    for e in emails:
        if "@" in e.from_email:
            domain = e.from_email.split("@")[-1].strip(">").lower()
            domains.append(domain)
    domain_counts = Counter(domains)

    # Subject length stats
    subject_lengths = [len(e.subject) for e in emails]
    body_lengths = [len(e.body) for e in emails if e.body]

    return {
        "count": len(emails),
        "date_range": {
            "earliest": min(dates).isoformat() if dates else None,
            "latest": max(dates).isoformat() if dates else None,
        },
        "by_month": dict(sorted(month_counts.items())),
        "top_domains": dict(domain_counts.most_common(20)),
        "subject_length": {
            "min": min(subject_lengths) if subject_lengths else 0,
            "max": max(subject_lengths) if subject_lengths else 0,
            "avg": sum(subject_lengths) / len(subject_lengths) if subject_lengths else 0,
        },
        "body_length": {
            "min": min(body_lengths) if body_lengths else 0,
            "max": max(body_lengths) if body_lengths else 0,
            "avg": sum(body_lengths) / len(body_lengths) if body_lengths else 0,
        },
    }


def process_sample(
    emails: list,
    anthropic_client: AnthropicClient,
    sample_size: int,
) -> list[dict]:
    """Process a sample of emails through categorization.

    Args:
        emails: List of EmailMessage objects
        anthropic_client: Anthropic client instance
        sample_size: Number of emails to process

    Returns:
        List of processing results
    """
    results = []
    sample = emails[:sample_size]

    logger.info(f"Processing sample of {len(sample)} emails...")

    for i, email in enumerate(sample, 1):
        logger.info(f"[{i}/{len(sample)}] Processing: {email.subject[:50]}...")

        try:
            result = anthropic_client.classify_with_escalation(
                subject=email.subject,
                from_email=email.from_email,
                body=email.body,
                categories=CATEGORIES,
                confidence_threshold=0.7,
            )

            results.append({
                "message_id": email.message_id,
                "subject": email.subject[:80],
                "from": email.from_email,
                "date": email.date.isoformat() if email.date else None,
                "category": result.category,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "model_used": result.model_used,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "needs_approval": result.confidence < 0.8,
            })

            logger.info(
                f"  -> {result.category} (confidence: {result.confidence:.2f}, "
                f"model: {result.model_used})"
            )

        except Exception as e:
            logger.error(f"  -> Error: {e}")
            results.append({
                "message_id": email.message_id,
                "subject": email.subject[:80],
                "error": str(e),
            })

    return results


def print_summary(analysis: dict, cost_estimate: dict, results: list = None):
    """Print a formatted summary."""
    print("\n" + "=" * 60)
    print("GMAIL AGENT TEST HARNESS - SUMMARY")
    print("=" * 60)

    print(f"\n📧 EMAIL ANALYSIS")
    print(f"   Total emails: {analysis['count']}")
    if analysis.get("date_range", {}).get("earliest"):
        print(f"   Date range: {analysis['date_range']['earliest']} to {analysis['date_range']['latest']}")

    if analysis.get("by_month"):
        print(f"\n   By month:")
        for month, count in analysis["by_month"].items():
            print(f"      {month}: {count} emails")

    if analysis.get("top_domains"):
        print(f"\n   Top sender domains:")
        for domain, count in list(analysis["top_domains"].items())[:10]:
            print(f"      {domain}: {count}")

    print(f"\n💰 COST ESTIMATE (Anthropic API)")
    print(f"   Emails to process: {cost_estimate['email_count']}")
    print(f"   Haiku calls: {cost_estimate['haiku_calls']}")
    print(f"   Sonnet calls (est. {cost_estimate['escalation_rate']*100:.0f}% escalation): {cost_estimate['sonnet_calls']}")
    print(f"   Haiku cost: ${cost_estimate['haiku_cost']:.4f}")
    print(f"   Sonnet cost: ${cost_estimate['sonnet_cost']:.4f}")
    print(f"   TOTAL ESTIMATED COST: ${cost_estimate['total_cost']:.4f}")

    if results:
        print(f"\n🔬 SAMPLE PROCESSING RESULTS")
        print(f"   Processed: {len(results)}")

        successful = [r for r in results if "category" in r]
        errors = [r for r in results if "error" in r]

        if successful:
            categories = Counter(r["category"] for r in successful)
            print(f"\n   Categories:")
            for cat, count in categories.most_common():
                print(f"      {cat}: {count}")

            needs_approval = sum(1 for r in successful if r.get("needs_approval"))
            print(f"\n   Needs human approval: {needs_approval}/{len(successful)} ({needs_approval/len(successful)*100:.1f}%)")

            avg_confidence = sum(r["confidence"] for r in successful) / len(successful)
            print(f"   Average confidence: {avg_confidence:.2f}")

            haiku_count = sum(1 for r in successful if "haiku" in r.get("model_used", "").lower())
            sonnet_count = sum(1 for r in successful if "sonnet" in r.get("model_used", "").lower())
            print(f"   Model usage: Haiku={haiku_count}, Sonnet={sonnet_count}")

            total_input = sum(r.get("input_tokens", 0) for r in successful)
            total_output = sum(r.get("output_tokens", 0) for r in successful)
            print(f"   Tokens used: {total_input} input, {total_output} output")

        if errors:
            print(f"\n   Errors: {len(errors)}")
            for e in errors[:5]:
                print(f"      - {e.get('subject', 'Unknown')[:40]}: {e.get('error', 'Unknown error')[:50]}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Test harness for Gmail Agent batch processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run - analyze emails without processing
  python scripts/test_batch.py --query "after:2024/11/01 before:2025/02/01" --dry-run

  # Process a sample of 10 emails
  python scripts/test_batch.py --query "after:2024/11/01 before:2025/02/01" --sample 10

  # Show only first 50 emails in analysis
  python scripts/test_batch.py --query "is:unread" --dry-run --max-fetch 50
        """,
    )

    parser.add_argument(
        "--query", "-q",
        required=True,
        help="Gmail search query (e.g., 'after:2024/11/01 before:2025/02/01')",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Only fetch and analyze emails, don't process",
    )
    parser.add_argument(
        "--sample", "-s",
        type=int,
        default=0,
        help="Process a sample of N emails (default: 0 = none)",
    )
    parser.add_argument(
        "--max-fetch", "-m",
        type=int,
        default=500,
        help="Maximum emails to fetch for analysis (default: 500)",
    )
    parser.add_argument(
        "--escalation-rate", "-e",
        type=float,
        default=0.3,
        help="Estimated escalation rate for cost calculation (default: 0.3)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output results to JSON file",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate environment
    print("Checking environment...")

    required_vars = ["GMAIL_OAUTH_CLIENT", "GMAIL_USER_TOKEN"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"\n❌ Missing required environment variables: {', '.join(missing)}")
        print("\nSet these variables before running:")
        print("  export GMAIL_OAUTH_CLIENT='<oauth-client-json>'")
        print("  export GMAIL_USER_TOKEN='<user-token-json>'")
        sys.exit(1)

    if args.sample > 0 and not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n❌ Missing ANTHROPIC_API_KEY for sample processing")
        print("Set this variable to process emails:")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    print("✓ Environment configured")

    # Initialize Gmail client
    print(f"\nConnecting to Gmail API...")
    try:
        gmail = GmailClient()
        # Test connection by listing 1 message
        gmail.list_messages(query=args.query, max_results=1)
        print("✓ Gmail API connection successful")
    except Exception as e:
        print(f"\n❌ Gmail API error: {e}")
        sys.exit(1)

    # Fetch messages
    print(f"\nFetching emails matching: {args.query}")
    print(f"(max: {args.max_fetch})")

    try:
        message_list = gmail.list_messages(query=args.query, max_results=args.max_fetch)
        print(f"✓ Found {len(message_list)} emails")
    except Exception as e:
        print(f"\n❌ Error fetching email list: {e}")
        sys.exit(1)

    if not message_list:
        print("\nNo emails found matching query.")
        sys.exit(0)

    # Fetch full messages for analysis
    print(f"\nFetching full message details...")
    try:
        message_ids = [m["id"] for m in message_list]
        emails = gmail.batch_get_messages(message_ids)
        print(f"✓ Fetched {len(emails)} emails")
    except Exception as e:
        print(f"\n❌ Error fetching messages: {e}")
        sys.exit(1)

    # Analyze
    analysis = analyze_emails(emails)
    cost_estimate = estimate_cost(len(emails), args.escalation_rate)

    # Process sample if requested
    results = None
    if args.sample > 0:
        print(f"\nInitializing Anthropic client...")
        try:
            anthropic = AnthropicClient()
            print("✓ Anthropic client ready")
            results = process_sample(emails, anthropic, args.sample)
        except Exception as e:
            print(f"\n❌ Error initializing Anthropic: {e}")
            sys.exit(1)

    # Print summary
    print_summary(analysis, cost_estimate, results)

    # Save results if requested
    if args.output:
        output_data = {
            "query": args.query,
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
            "cost_estimate": cost_estimate,
            "sample_results": results,
        }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2, default=str)
        print(f"\n📁 Results saved to: {args.output}")


if __name__ == "__main__":
    main()
