#!/usr/bin/env python3
"""
add_product_by_asin.py - Add a specific Amazon product to the catalog by ASIN.

Fetches product details directly from the Amazon product page, then appends
the product to products/top-1000.csv and runs autofix-images.js.

Usage:
    python add_product_by_asin.py B0FWKB7W3X
    python add_product_by_asin.py B0FWKB7W3X --category "Health & Wellness"
    python add_product_by_asin.py B0FWKB7W3X --dry-run
    python add_product_by_asin.py B0FWKB7W3X --skip-images
    python add_product_by_asin.py B0FWKB7W3X --name "Bebas Lumbar Support Pillow" --category "Health & Wellness"
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import time
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NamedTuple

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CSV_PATH = Path("products/top-1000.csv")
AFFILIATE_TAG = "hotproduct033-20"
MAX_RETRIES = 3
REQUEST_DELAY_MIN = 2.0
REQUEST_DELAY_MAX = 5.0

FIELDNAMES = [
    "Product Name", "Category", "Price Range", "Review Count",
    "Rating", "BSR", "Affiliate Potential", "Amazon URL",
    "Refreshed Date", "Action Needed",
]

KNOWN_CATEGORIES = [
    "Audio", "Automotive", "Baby & Kids", "Beauty", "Books",
    "Desktops & Mini PCs", "Drones", "Fitness", "Furniture",
    "Gaming Headsets", "Gaming PCs", "Gaming Peripherals", "Gardening",
    "Headphones", "Health & Wellness", "Home", "Home Improvement",
    "Kitchen", "Laptops", "Luxury Beauty", "Monitors",
    "Musical Instruments", "Office Supplies", "Outdoor & Camping",
    "Personal Care", "Pet Supplies", "Photography", "Power Tools",
    "Robot Vacuums", "Security", "Smart Displays", "Smart Home",
    "Speakers", "Sports Equipment", "Streaming", "Tablets",
    "Travel Accessories", "Wearables",
]

USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
class ScrapedProduct(NamedTuple):
    name: str
    price: str
    rating: str
    review_count: str
    asin: str


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _get_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def _fetch_url(url: str) -> str | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=_get_headers(), timeout=20)
            if resp.status_code == 503:
                wait = 10 + random.uniform(5, 15)
                print(f"  Rate limited (503), waiting {wait:.0f}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                print(f"  HTTP {resp.status_code} for {url}")
                return None
            return resp.text
        except requests.RequestException as e:
            print(f"  Request error: {e}, retry {attempt + 1}/{MAX_RETRIES}...")
            time.sleep(5)
    return None


# ---------------------------------------------------------------------------
# Amazon product page scraping
# ---------------------------------------------------------------------------
def _clean_price(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^from\s+", "", raw, flags=re.IGNORECASE)
    prices = re.findall(r"\$[\d,]+(?:\.\d{2})?", raw)
    if len(prices) >= 2:
        return f"{prices[0]}-{prices[1]}"
    if len(prices) == 1:
        return prices[0]
    return raw if raw else "$0"


def _clean_review_count(raw: str) -> int:
    raw = raw.strip().replace(",", "")
    match = re.search(r"([\d.]+)\s*[kK]", raw)
    if match:
        return int(float(match.group(1)) * 1000)
    match = re.search(r"(\d+)", raw)
    return int(match.group(1)) if match else 0


def _clean_rating(raw: str) -> float:
    match = re.search(r"([\d.]+)\s*out\s*of", raw)
    if match:
        return round(float(match.group(1)), 1)
    match = re.search(r"([\d.]+)", raw)
    return round(float(match.group(1)), 1) if match else 0.0


def scrape_product_page(asin: str) -> ScrapedProduct | None:
    """Fetch an Amazon product page and extract key fields."""
    url = f"https://www.amazon.com/dp/{asin}"
    print(f"  Fetching: {url}")

    html = _fetch_url(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # --- Product name ---
    name = ""
    title_el = (
        soup.find(id="productTitle")
        or soup.find(id="title")
        or soup.select_one("h1.a-size-large span")
        or soup.select_one("h1 span#productTitle")
    )
    if title_el:
        name = title_el.get_text(strip=True)
    if not name:
        print("  WARNING: Could not find product title on page.")
        return None

    # Trim overly long names
    if len(name) > 120:
        for cut in [" - ", " | ", ", ", " with "]:
            idx = name.find(cut, 40)
            if 40 < idx < 120:
                name = name[:idx]
                break
        else:
            name = name[:120].rsplit(" ", 1)[0]

    # --- Price ---
    price = ""
    price_el = (
        soup.select_one("#priceblock_ourprice")
        or soup.select_one("#priceblock_dealprice")
        or soup.select_one(".a-price .a-offscreen")
        or soup.select_one("#price_inside_buybox")
        or soup.select_one(".priceToPay .a-offscreen")
        or soup.select_one("[data-asin-price]")
    )
    if price_el:
        price = _clean_price(price_el.get_text(strip=True))

    # --- Rating ---
    rating = ""
    rating_el = (
        soup.select_one("#acrPopover")
        or soup.select_one('[data-hook="rating-out-of-text"]')
        or soup.select_one(".a-icon-alt")
    )
    if rating_el:
        rating_text = rating_el.get("title", "") or rating_el.get_text(strip=True)
        rating = str(_clean_rating(rating_text)) if rating_text else ""

    # --- Review count ---
    review_count = ""
    review_el = (
        soup.select_one("#acrCustomerReviewText")
        or soup.select_one('[data-hook="total-review-count"]')
        or soup.find(id="acrCustomerReviewLink")
    )
    if review_el:
        review_text = review_el.get_text(strip=True)
        count = _clean_review_count(review_text)
        review_count = str(count) if count > 0 else ""

    return ScrapedProduct(
        name=name,
        price=price,
        rating=rating,
        review_count=review_count,
        asin=asin,
    )


# ---------------------------------------------------------------------------
# Product row building
# ---------------------------------------------------------------------------
def _estimate_affiliate_potential(price: str, rating: str, reviews: int) -> int:
    score = 5
    price_nums = re.findall(r"[\d.]+", price.replace(",", ""))
    if price_nums:
        avg_price = sum(float(p) for p in price_nums) / len(price_nums)
        if avg_price >= 500:
            score += 3
        elif avg_price >= 100:
            score += 2
        elif avg_price >= 30:
            score += 1
    if reviews >= 10000:
        score += 1
    try:
        if float(rating) >= 4.5:
            score += 1
    except (ValueError, TypeError):
        pass
    return min(score, 9)


def _next_bsr_for_category(catalog: list[dict[str, str]], category: str) -> str:
    count = sum(1 for r in catalog if r.get("Category", "").strip() == category)
    return f"#{count + 1}"


def build_row(
    product: ScrapedProduct,
    category: str,
    catalog: list[dict[str, str]],
) -> dict[str, str]:
    reviews = _clean_review_count(product.review_count)
    rating_val = _clean_rating(product.rating) if product.rating else 4.5
    potential = _estimate_affiliate_potential(product.price, product.rating, reviews)
    bsr = _next_bsr_for_category(catalog, category)
    amazon_url = f"https://www.amazon.com/dp/{product.asin}?tag={AFFILIATE_TAG}"

    return {
        "Product Name": product.name,
        "Category": category,
        "Price Range": product.price if product.price and product.price != "$0" else "",
        "Review Count": str(reviews) if reviews > 0 else "",
        "Rating": str(rating_val) if rating_val > 0 else "",
        "BSR": bsr,
        "Affiliate Potential": str(potential),
        "Amazon URL": amazon_url,
        "Refreshed Date": date.today().strftime("%-m/%-d/%Y"),
        "Action Needed": "",
    }


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------
def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_to_csv(path: Path, row: dict[str, str]) -> None:
    existing = load_csv(path)
    rows = existing + [row]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in FIELDNAMES})


# ---------------------------------------------------------------------------
# Duplicate check
# ---------------------------------------------------------------------------
def check_duplicate(name: str, catalog: list[dict[str, str]]) -> str | None:
    """Return the existing product name if it looks like a duplicate."""
    name_lower = name.lower()
    for row in catalog:
        existing = row.get("Product Name", "").strip().lower()
        if existing == name_lower:
            return row.get("Product Name", "")
        # Check if ASIN already appears in any URL
    return None


def asin_already_in_catalog(asin: str, catalog: list[dict[str, str]]) -> bool:
    for row in catalog:
        url = row.get("Amazon URL", "")
        if asin in url:
            return True
    return False


# ---------------------------------------------------------------------------
# Image runner
# ---------------------------------------------------------------------------
def run_autofix_images() -> None:
    script_path = Path("autofix-images.js")
    if not script_path.exists():
        print("  autofix-images.js not found, skipping image download")
        return

    print("\n  Running autofix-images.js...")
    try:
        result = subprocess.run(
            ["node", str(script_path)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        lines = result.stdout.strip().split("\n") if result.stdout else []
        for line in lines[-5:]:
            print(f"    {line}")
        if result.returncode != 0:
            print(f"  Image download had errors (exit {result.returncode})")
    except subprocess.TimeoutExpired:
        print("  Image download timed out")
    except FileNotFoundError:
        print("  Node.js not found - skipping image download")


# ---------------------------------------------------------------------------
# Category selection
# ---------------------------------------------------------------------------
def select_category(suggested: str | None) -> str:
    if suggested:
        if suggested in KNOWN_CATEGORIES:
            return suggested
        # Case-insensitive match
        for cat in KNOWN_CATEGORIES:
            if cat.lower() == suggested.lower():
                return cat
        print(f"  WARNING: '{suggested}' is not a known category.")
        print(f"  Known categories: {', '.join(KNOWN_CATEGORIES)}")
        print(f"  Using '{suggested}' anyway.")
        return suggested

    print("\n  Available categories:")
    for i, cat in enumerate(KNOWN_CATEGORIES, 1):
        print(f"    {i:2}. {cat}")
    while True:
        try:
            choice = input("\n  Enter category number or name: ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(KNOWN_CATEGORIES):
                    return KNOWN_CATEGORIES[idx]
                print("  Invalid number, try again.")
            else:
                # Partial match
                matches = [c for c in KNOWN_CATEGORIES if choice.lower() in c.lower()]
                if len(matches) == 1:
                    return matches[0]
                if len(matches) > 1:
                    print(f"  Ambiguous — matches: {', '.join(matches)}")
                else:
                    # Accept free-form input
                    confirm = input(f"  Use '{choice}' as custom category? [y/N] ").strip().lower()
                    if confirm == "y":
                        return choice
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add a specific Amazon product to the catalog by ASIN",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("asin", help="Amazon ASIN (e.g. B0FWKB7W3X)")
    parser.add_argument("--category", "-c", default=None, help="Product category")
    parser.add_argument("--name", "-n", default=None, help="Override product name")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--skip-images", action="store_true", help="Skip image download")
    args = parser.parse_args()

    asin = args.asin.strip().upper()
    if not re.match(r"^[A-Z0-9]{10}$", asin):
        print(f"ERROR: '{asin}' does not look like a valid ASIN (10 alphanumeric characters).")
        return 1

    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found: {CSV_PATH}")
        return 1

    print(f"\nAdding product: ASIN {asin}")
    print("=" * 60)

    # Load catalog
    catalog = load_csv(CSV_PATH)
    print(f"  Catalog size: {len(catalog)} products")

    # Duplicate ASIN check
    if asin_already_in_catalog(asin, catalog):
        print(f"  ERROR: ASIN {asin} is already in the catalog.")
        return 1

    # Scrape the product page
    product = scrape_product_page(asin)
    if not product:
        print("  ERROR: Could not fetch product data from Amazon.")
        print("  You can override the name with --name and try again.")
        return 1

    # Override name if requested
    if args.name:
        product = product._replace(name=args.name)

    print(f"\n  Name:    {product.name}")
    print(f"  Price:   {product.price or '(not found)'}")
    print(f"  Rating:  {product.rating or '(not found)'}")
    print(f"  Reviews: {product.review_count or '(not found)'}")

    # Duplicate name check
    dup = check_duplicate(product.name, catalog)
    if dup:
        print(f"\n  WARNING: A product with this name already exists: '{dup}'")
        try:
            confirm = input("  Add anyway? [y/N] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return 1
        if confirm != "y":
            return 1

    # Category selection
    category = select_category(args.category)
    print(f"\n  Category: {category}")

    # Build row
    row = build_row(product, category, catalog)

    if args.dry_run:
        print("\n  [DRY RUN] Would add:")
        for k, v in row.items():
            if v:
                print(f"    {k}: {v}")
        return 0

    # Write to CSV
    append_to_csv(CSV_PATH, row)
    print(f"\n  CSV updated: {len(catalog)} -> {len(catalog) + 1} products")
    print(f"  URL: {row['Amazon URL']}")

    # Download images
    if not args.skip_images:
        run_autofix_images()

    print("\n" + "=" * 60)
    print(f"  Done! Added: {product.name}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
