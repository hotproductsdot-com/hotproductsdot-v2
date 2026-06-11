#!/usr/bin/env python3
"""
CLI tool for affiliate content generation.

Provides interactive CLI interface for:
- Hook Writer: Generate scroll-stopping opening lines
- CTA Builder: Platform-specific call-to-action text
- Content Calendar: Plan N days of posts with products, hooks, and CTAs
- Bio Optimizer: Generate optimized Instagram/TikTok bios

Usage:
    python affiliate_cli.py hooks --product "Wireless Earbuds" --category "Electronics"
    python affiliate_cli.py cta --product "Wireless Earbuds" --price "$49.99" --platform instagram
    python affiliate_cli.py calendar --days 7
    python affiliate_cli.py bio --platform instagram --niche "Amazon trending products"
    python affiliate_cli.py interactive  # interactive mode
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows to prevent UnicodeEncodeError with emoji
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

# Load environment
load_dotenv(override=True)

from instagram import affiliate_tools
from post_daily import load_top_products

logger = logging.getLogger(__name__)


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging."""
    level = logging.WARNING if quiet else (logging.DEBUG if verbose else logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_hooks(args: argparse.Namespace) -> None:
    """Generate hooks for a product."""
    product = {
        "name": args.product,
        "category": args.category,
        "rating": args.rating,
        "reviews": args.reviews,
        "price": args.price,
    }

    logger.info(f"Generating {args.count} hooks for {args.product}...")
    hooks = affiliate_tools.generate_hooks(product, count=args.count)

    print("\n🎣 Generated Hooks:\n")
    for i, hook in enumerate(hooks, 1):
        print(f"  {i}. {hook}")
        print(f"     ({len(hook)} chars)\n")

    if args.json:
        print(json.dumps(hooks, indent=2))


def cmd_cta(args: argparse.Namespace) -> None:
    """Generate CTA for a product."""
    product = {
        "name": args.product,
        "price": args.price,
    }

    logger.info(f"Generating CTA for {args.product} on {args.platform}...")
    cta = affiliate_tools.build_cta(product, platform=args.platform)

    print(f"\n📢 {args.platform.upper()} CTA:\n")
    print(f"  {cta}")
    print(f"  ({len(cta)} chars)\n")

    if args.json:
        print(json.dumps({"platform": args.platform, "cta": cta}, indent=2))


def cmd_calendar(args: argparse.Namespace) -> None:
    """Generate content calendar."""
    logger.info(f"Loading products...")
    try:
        products = load_top_products()
        if not products:
            print("❌ No products loaded from CSV")
            return
    except Exception as e:
        print(f"❌ Error loading products: {e}")
        return

    logger.info(f"Generating {args.days}-day calendar from {len(products)} products...")
    calendar = affiliate_tools.generate_content_calendar(products, days=args.days)

    print(f"\n📅 {args.days}-Day Content Calendar:\n")
    print(f"Generated: {calendar['generated_at']}\n")

    for entry in calendar["entries"]:
        day = entry["day"]
        date = entry["date"]
        platform = entry["platform"].upper()
        product_name = entry["product"]["name"]
        hook = entry["hook"]
        cta = entry["cta"]
        hashtags = entry.get("hashtags", "")

        print(f"Day {day} ({date}) | {platform}")
        print(f"  📦 Product: {product_name}")
        print(f"  🎣 Hook: {hook}")
        print(f"  📢 CTA: {cta}")
        print(f"  #️⃣  Tags: {hashtags}")
        print()

    if args.json:
        output_file = f"content_calendar_{calendar['generated_at'][:10]}.json"
        with open(output_file, "w") as f:
            json.dump(calendar, f, indent=2)
        print(f"📥 Calendar saved to {output_file}")


def cmd_bio(args: argparse.Namespace) -> None:
    """Generate bio."""
    logger.info(f"Generating {args.platform} bio for niche: {args.niche}...")
    bio = affiliate_tools.generate_bio(platform=args.platform, niche=args.niche)

    limits = {"instagram": 150, "tiktok": 500}
    limit = limits.get(args.platform.lower(), 150)

    print(f"\n✨ {args.platform.upper()} Bio:\n")
    print(f"  {bio}")
    print(f"\n  ({len(bio)}/{limit} chars)\n")

    if args.json:
        print(json.dumps({"platform": args.platform, "bio": bio}, indent=2))


def cmd_interactive() -> None:
    """Interactive mode."""
    print("\n🛒 HotProducts Affiliate Content Generator (Interactive Mode)\n")

    while True:
        print("Choose a tool:")
        print("  1. 🎣 Hook Writer")
        print("  2. 📢 CTA Builder")
        print("  3. 📅 Content Calendar")
        print("  4. ✨ Bio Optimizer")
        print("  5. ❌ Exit\n")

        choice = input("Select (1-5): ").strip()

        if choice == "1":
            product_name = input("Product name: ").strip()
            category = input("Category: ").strip()
            rating = float(input("Rating (0-5, default 4.8): ").strip() or "4.8")
            reviews = int(input("Number of reviews (default 1200): ").strip() or "1200")
            price = input("Price (e.g. $49.99): ").strip()
            count = int(input("Number of hooks (default 5): ").strip() or "5")

            product = {
                "name": product_name,
                "category": category,
                "rating": rating,
                "reviews": reviews,
                "price": price,
            }

            hooks = affiliate_tools.generate_hooks(product, count=count)
            print("\n✨ Generated Hooks:\n")
            for i, hook in enumerate(hooks, 1):
                print(f"  {i}. {hook}")
            print()

        elif choice == "2":
            product_name = input("Product name: ").strip()
            price = input("Price: ").strip()
            platform = input("Platform (instagram/tiktok): ").strip().lower()

            product = {"name": product_name, "price": price}
            cta = affiliate_tools.build_cta(product, platform=platform)

            print(f"\n📢 {platform.upper()} CTA:\n  {cta}\n")

        elif choice == "3":
            days = int(input("Number of days to plan (default 7): ").strip() or "7")

            try:
                products = load_top_products()
                if products:
                    calendar = affiliate_tools.generate_content_calendar(products, days=days)

                    print(f"\n📅 {days}-Day Calendar:\n")
                    for entry in calendar["entries"]:
                        day = entry["day"]
                        date = entry["date"]
                        platform = entry["platform"].upper()
                        product_name = entry["product"]["name"]

                        print(f"Day {day} ({date}) | {platform}: {product_name}")
                    print()
            except Exception as e:
                print(f"❌ Error: {e}\n")

        elif choice == "4":
            platform = input("Platform (instagram/tiktok): ").strip().lower()
            niche = input("Niche (default 'Amazon affiliate'): ").strip() or "Amazon affiliate"

            bio = affiliate_tools.generate_bio(platform=platform, niche=niche)

            limits = {"instagram": 150, "tiktok": 500}
            limit = limits.get(platform, 150)

            print(f"\n✨ {platform.upper()} Bio:\n  {bio}")
            print(f"\n  ({len(bio)}/{limit} chars)\n")

        elif choice == "5":
            print("Goodbye! 👋\n")
            break

        else:
            print("❌ Invalid choice. Please select 1-5.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HotProducts Affiliate Content Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python affiliate_cli.py hooks --product "Wireless Earbuds" --category Electronics
  python affiliate_cli.py cta --product "Wireless Earbuds" --price "$49.99" --platform instagram
  python affiliate_cli.py calendar --days 7
  python affiliate_cli.py bio --platform instagram --niche "Amazon trending"
  python affiliate_cli.py interactive
        """,
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet mode",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Hook Writer
    hooks_parser = subparsers.add_parser("hooks", help="Generate hooks")
    hooks_parser.add_argument("--product", required=True, help="Product name")
    hooks_parser.add_argument("--category", required=True, help="Product category")
    hooks_parser.add_argument("--rating", type=float, default=4.8, help="Rating (0-5)")
    hooks_parser.add_argument("--reviews", type=int, default=1200, help="Number of reviews")
    hooks_parser.add_argument("--price", default="$49.99", help="Product price")
    hooks_parser.add_argument("--count", type=int, default=5, help="Number of hooks to generate")
    hooks_parser.add_argument("--json", action="store_true", help="Output as JSON")
    hooks_parser.set_defaults(func=cmd_hooks)

    # CTA Builder
    cta_parser = subparsers.add_parser("cta", help="Generate CTA")
    cta_parser.add_argument("--product", required=True, help="Product name")
    cta_parser.add_argument("--price", required=True, help="Product price")
    cta_parser.add_argument("--platform", required=True, choices=["instagram", "tiktok"], help="Platform")
    cta_parser.add_argument("--json", action="store_true", help="Output as JSON")
    cta_parser.set_defaults(func=cmd_cta)

    # Content Calendar
    calendar_parser = subparsers.add_parser("calendar", help="Generate content calendar")
    calendar_parser.add_argument("--days", type=int, default=7, help="Number of days")
    calendar_parser.add_argument("--json", action="store_true", help="Save as JSON file")
    calendar_parser.set_defaults(func=cmd_calendar)

    # Bio Optimizer
    bio_parser = subparsers.add_parser("bio", help="Generate bio")
    bio_parser.add_argument("--platform", required=True, choices=["instagram", "tiktok"], help="Platform")
    bio_parser.add_argument("--niche", default="Amazon affiliate", help="Niche")
    bio_parser.add_argument("--json", action="store_true", help="Output as JSON")
    bio_parser.set_defaults(func=cmd_bio)

    # Interactive Mode
    interactive_parser = subparsers.add_parser("interactive", help="Interactive mode")
    interactive_parser.set_defaults(func=lambda args: cmd_interactive())

    args = parser.parse_args()
    configure_logging(args.verbose, args.quiet)

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
