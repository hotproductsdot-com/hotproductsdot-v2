#!/usr/bin/env python3
"""
Generate a content calendar for Amazon affiliate posting.

Picks N products from the top-1000 CSV, creates a posting plan with hooks, CTAs,
and platform assignments (Instagram vs TikTok). Outputs JSON to a file.

Usage:
    python generate_content_calendar.py [--days 7] [--output PATH]

Options:
    --days N         Number of days to plan (default: 7)
    --output PATH    Override output path
                     (default: marketing-campaigns/content_calendar.json)

Example:
    python generate_content_calendar.py --days 14 --output my_calendar.json
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables for ANTHROPIC_API_KEY
load_dotenv(override=True)

# Import from post_daily
sys.path.insert(0, str(Path(__file__).parent))
from post_daily import load_top_products

# Import AI tools
from instagram import affiliate_tools

logger = logging.getLogger(__name__)


def main() -> None:
    """Generate content calendar and write to JSON file."""
    parser = argparse.ArgumentParser(
        description="Generate a content calendar for Amazon affiliate posting."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to plan (default: 7)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: marketing-campaigns/content_calendar.json)",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).parent / "marketing-campaigns" / "content_calendar.json"

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.days}-day content calendar...")
    print(f"Output: {output_path}")
    print()

    # Load products
    try:
        products = load_top_products()
        if not products:
            print("ERROR: No products loaded from CSV. Check products/top-1000.csv")
            sys.exit(1)
        print(f"Loaded {len(products)} products from top-1000.csv")
    except Exception as exc:
        print(f"ERROR: Failed to load products: {exc}")
        sys.exit(1)

    # Generate calendar
    try:
        calendar = affiliate_tools.generate_content_calendar(
            products=products,
            days=args.days,
        )
        print(f"Generated calendar with {len(calendar['entries'])} days")
    except Exception as exc:
        print(f"ERROR: Calendar generation failed: {exc}")
        sys.exit(1)

    # Write to file
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(calendar, f, indent=2)
        print(f"✓ Wrote calendar to {output_path}")
    except Exception as exc:
        print(f"ERROR: Failed to write output: {exc}")
        sys.exit(1)

    # Print summary
    print()
    print("Content Calendar Summary:")
    print("─" * 60)
    for entry in calendar["entries"]:
        day = entry["day"]
        date_str = entry["date"]
        platform = entry["platform"].upper()
        product_name = entry["product"]["name"][:40]
        hook = entry["hook"][:30]
        print(f"Day {day:2d} ({date_str}) [{platform:8s}] {product_name:40s}")
        print(f"          Hook: {hook}")
    print()
    print(f"Generated at: {calendar['generated_at']}")


if __name__ == "__main__":
    main()
