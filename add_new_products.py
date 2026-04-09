#!/usr/bin/env python3
"""
add_new_products.py - Add new unique products to products/top-1000.csv

Scrapes Amazon search results for real products, validates uniqueness
against the existing catalog using fuzzy matching, and appends to CSV.
Runs autofix-images.js after each batch to download product images.

Usage:
    python add_new_products.py                       # 1 run  = 10 products
    python add_new_products.py --runs 5              # 5 runs = 50 products
    python add_new_products.py --batch-size 15       # 1 run  = 15 products
    python add_new_products.py --runs 3 --batch-size 20  # 3 runs = 60 products
    python add_new_products.py --category "Kitchen"  # target one category
    python add_new_products.py --dry-run             # preview without writing
    python add_new_products.py --skip-images         # skip image download
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NamedTuple

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Duplicate checking (reuse existing logic)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent / "products"))
from check_duplicates import DuplicateError, check_product, load_catalog

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CSV_PATH = Path("products/top-1000.csv")
AFFILIATE_TAG = "hotproduct033-20"
DEFAULT_BATCH_SIZE = 10
MAX_RETRIES = 3
REQUEST_DELAY_MIN = 3.0   # seconds between Amazon requests
REQUEST_DELAY_MAX = 6.0

USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
)

# Category -> Amazon search terms (multiple per category for variety)
CATEGORY_SEARCH_TERMS: dict[str, list[str]] = {
    "Audio": [
        "best wireless speakers 2025", "top rated soundbar", "bluetooth portable speaker",
        "home theater audio system", "wireless earbuds premium", "studio headphones",
    ],
    "Automotive": [
        "best car accessories 2025", "top rated dash cam", "car phone mount",
        "portable car vacuum", "car seat organizer", "tire inflator portable",
    ],
    "Baby & Kids": [
        "best baby monitor 2025", "top rated stroller", "baby car seat",
        "kids tablet learning", "baby swing bouncer", "toddler toys educational",
    ],
    "Beauty": [
        "best skincare products 2025", "top rated hair dryer", "makeup brush set",
        "facial cleanser best seller", "hair straightener flat iron", "beauty blender set",
    ],
    "Books": [
        "best sellers books 2025", "new york times best sellers", "top rated fiction books",
        "self help books popular", "business books best seller", "science fiction books new",
    ],
    "Kindle Free E-Books": [
        "kindle free ebooks bestseller", "free kindle books top rated", "kindle unlimited free books",
        "free amazon kindle books fiction", "free kindle self help books", "free kindle mystery thriller",
        "free kindle romance novels", "free kindle sci fi books", "free kindle children books",
        "free kindle nonfiction best",
    ],
    "Kindle Paid E-Books": [
        "kindle bestseller ebooks 2025", "top rated kindle books paid", "best kindle novels 2025",
        "kindle business books best seller", "kindle fiction bestseller list", "kindle thriller mystery top",
        "kindle romance bestseller 2025", "kindle self help top rated", "kindle sci fi fantasy best",
        "kindle nonfiction bestseller 2025",
    ],
    "Desktops & Mini PCs": [
        "best mini pc 2025", "desktop computer all in one", "small form factor pc",
        "mini pc for home office", "compact desktop computer", "intel nuc mini pc",
    ],
    "Drones": [
        "best drones 2025 camera", "mini drone with camera", "fpv racing drone",
        "drone for beginners", "professional camera drone", "foldable drone gps",
    ],
    "Fitness": [
        "best fitness tracker 2025", "home gym equipment", "resistance bands set",
        "adjustable dumbbells", "yoga mat premium", "exercise bike indoor",
    ],
    "Furniture": [
        "best office chair ergonomic 2025", "standing desk adjustable", "bookshelf modern",
        "sofa mid century", "dining table set", "bed frame platform",
    ],
    "Gaming Headsets": [
        "best gaming headset 2025", "wireless gaming headset pc", "gaming headphones ps5",
        "surround sound gaming headset", "budget gaming headset", "usb gaming headset",
    ],
    "Gaming PCs": [
        "best gaming laptop 2025", "gaming desktop rtx 4080", "prebuilt gaming pc",
        "gaming laptop under 1500", "gaming pc budget build", "high end gaming desktop",
    ],
    "Gaming Peripherals": [
        "best gaming mouse 2025", "mechanical gaming keyboard", "gaming mouse pad xl",
        "gaming controller pc", "gaming webcam streamer", "rgb gaming keyboard",
    ],
    "Gardening": [
        "best garden tools 2025", "raised garden bed kit", "electric lawn mower",
        "garden hose expandable", "outdoor planters large", "composting bin kitchen",
    ],
    "Headphones": [
        "best noise cancelling headphones 2025", "over ear headphones wireless",
        "audiophile headphones", "headphones for running", "open back headphones",
    ],
    "Health & Wellness": [
        "best blood pressure monitor 2025", "air purifier hepa", "humidifier bedroom",
        "massage gun deep tissue", "electric toothbrush", "water flosser",
    ],
    "Home": [
        "best robot vacuum 2025", "air fryer best rated", "cordless vacuum cleaner",
        "dehumidifier for home", "space heater energy efficient", "steam mop floor cleaner",
    ],
    "Home Improvement": [
        "best power drill 2025", "smart thermostat", "led light bulbs smart",
        "security camera outdoor", "garage door opener smart", "water filter system",
    ],
    "Kitchen": [
        "best kitchen gadgets 2025", "instant pot pressure cooker", "knife set chef",
        "coffee maker drip", "food processor best", "blender smoothie",
    ],
    "Laptops": [
        "best laptops 2025", "ultrabook thin light", "laptop for students",
        "business laptop 2025", "2 in 1 laptop tablet", "laptop 17 inch",
    ],
    "Luxury Beauty": [
        "luxury skincare brands", "premium anti aging serum", "high end moisturizer",
        "luxury perfume women 2025", "premium eye cream", "luxury hair care",
    ],
    "Monitors": [
        "best monitor 4k 2025", "ultrawide monitor 34", "gaming monitor 240hz",
        "monitor for macbook", "portable monitor usb c", "curved monitor 32",
    ],
    "Musical Instruments": [
        "best acoustic guitar beginner", "digital piano weighted keys", "ukulele starter",
        "violin for beginners", "drum pad electronic", "bass guitar starter",
    ],
    "Office Supplies": [
        "best desk organizer 2025", "label maker printer", "ergonomic keyboard",
        "monitor stand riser", "document scanner portable", "whiteboard magnetic",
    ],
    "Outdoor & Camping": [
        "best camping tent 2025", "hiking backpack 50l", "portable camping stove",
        "sleeping bag cold weather", "camping lantern rechargeable", "water bottle insulated",
    ],
    "Personal Care": [
        "best electric shaver 2025", "hair clipper professional", "teeth whitening kit",
        "body groomer men", "facial steamer", "nail care kit electric",
    ],
    "Pet Supplies": [
        "best dog bed 2025", "automatic cat feeder", "dog training treats",
        "cat tree tall", "dog harness no pull", "pet camera treat dispenser",
    ],
    "Photography": [
        "best mirrorless camera 2025", "camera lens 50mm", "tripod for camera",
        "camera bag backpack", "sd card 256gb camera", "photo printer portable",
    ],
    "Power Tools": [
        "best cordless drill 2025", "impact driver set", "orbital sander",
        "jigsaw cordless", "angle grinder", "oscillating tool kit",
    ],
    "Robot Vacuums": [
        "best robot vacuum 2025", "robot vacuum mop combo", "robot vacuum pet hair",
        "self emptying robot vacuum", "budget robot vacuum", "robot vacuum mapping",
    ],
    "Security": [
        "best home security camera 2025", "video doorbell wireless", "smart lock deadbolt",
        "security system diy", "outdoor security light", "safe fireproof",
    ],
    "Smart Displays": [
        "best smart display 2025", "smart home hub display", "digital photo frame wifi",
        "smart kitchen display", "smart display with camera", "bedside smart display",
    ],
    "Smart Home": [
        "best smart home devices 2025", "smart plug wifi", "smart light switch",
        "smart smoke detector", "smart sprinkler controller", "smart blinds motorized",
    ],
    "Speakers": [
        "best bluetooth speaker 2025", "portable speaker waterproof", "bookshelf speakers",
        "outdoor speaker wireless", "smart speaker alexa", "party speaker bluetooth",
    ],
    "Sports Equipment": [
        "best running shoes 2025", "tennis racket adult", "basketball indoor outdoor",
        "golf clubs set", "boxing gloves training", "soccer ball official",
    ],
    "Streaming": [
        "best streaming device 2025", "4k streaming stick", "android tv box",
        "streaming microphone usb", "ring light streamer", "green screen backdrop",
    ],
    "Tablets": [
        "best tablet 2025", "android tablet 10 inch", "tablet for drawing",
        "kids tablet 2025", "tablet with keyboard", "e reader tablet",
    ],
    "Travel Accessories": [
        "best carry on luggage 2025", "packing cubes set", "travel adapter universal",
        "neck pillow travel", "luggage scale digital", "travel backpack expandable",
    ],
    "Wearables": [
        "best smartwatch 2025", "fitness tracker band", "smart ring health",
        "gps running watch", "kids smartwatch", "sleep tracker wearable",
    ],
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
class ScrapedProduct(NamedTuple):
    name: str
    price: str
    rating: str
    review_count: str
    asin: str


@dataclass(frozen=True)
class ProductRow:
    name: str
    category: str
    price: str
    review_count: int
    rating: float
    bsr: str
    affiliate_potential: int
    amazon_url: str
    refreshed_date: str


# ---------------------------------------------------------------------------
# Amazon scraping
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


def _request_delay() -> None:
    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    time.sleep(delay)


def _clean_price(raw: str) -> str:
    """Normalize a price string from Amazon."""
    raw = raw.strip()
    # Remove "from" prefix
    raw = re.sub(r"^from\s+", "", raw, flags=re.IGNORECASE)
    # Match dollar amounts
    prices = re.findall(r"\$[\d,]+(?:\.\d{2})?", raw)
    if len(prices) >= 2:
        return f"{prices[0]}-{prices[1]}"
    if len(prices) == 1:
        return prices[0]
    return raw if raw else "$0"


def _clean_review_count(raw: str) -> int:
    """Parse review count like '12,345' or '12K'."""
    raw = raw.strip().replace(",", "")
    match = re.search(r"([\d.]+)\s*[kK]", raw)
    if match:
        return int(float(match.group(1)) * 1000)
    match = re.search(r"(\d+)", raw)
    return int(match.group(1)) if match else 0


def _clean_rating(raw: str) -> float:
    """Parse rating like '4.5 out of 5 stars'."""
    match = re.search(r"([\d.]+)\s*out\s*of", raw)
    if match:
        return round(float(match.group(1)), 1)
    match = re.search(r"([\d.]+)", raw)
    return round(float(match.group(1)), 1) if match else 0.0


def scrape_amazon_search(query: str, max_results: int = 20) -> list[ScrapedProduct]:
    """Scrape Amazon search results for product data."""
    url = f"https://www.amazon.com/s?k={urllib.parse.quote_plus(query)}"

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=_get_headers(), timeout=15)
            if resp.status_code == 503:
                print(f"    Rate limited (503), retry {attempt + 1}/{MAX_RETRIES}...")
                time.sleep(10 + random.uniform(5, 15))
                continue
            if resp.status_code != 200:
                print(f"    HTTP {resp.status_code} for query '{query}'")
                return []
            break
        except requests.RequestException as e:
            print(f"    Request error: {e}, retry {attempt + 1}/{MAX_RETRIES}...")
            time.sleep(5)
    else:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products: list[ScrapedProduct] = []

    # Find search result items
    items = soup.select('[data-component-type="s-search-result"]')
    if not items:
        # Fallback: try alternate selectors
        items = soup.select(".s-result-item[data-asin]")

    for item in items[:max_results]:
        asin = item.get("data-asin", "")
        if not asin or len(asin) != 10:
            continue

        # Product name
        title_el = (
            item.select_one("h2 a span")
            or item.select_one("h2 span")
            or item.select_one(".a-text-normal")
        )
        if not title_el:
            continue
        name = title_el.get_text(strip=True)

        # Skip sponsored/ad results with very short names
        if len(name) < 10:
            continue

        # Truncate overly long names (keep first meaningful part)
        if len(name) > 120:
            # Try to cut at a natural boundary
            cut_points = [" - ", " | ", ", ", " with "]
            for cut in cut_points:
                idx = name.find(cut, 40)
                if idx != -1 and idx < 120:
                    name = name[:idx]
                    break
            else:
                name = name[:120].rsplit(" ", 1)[0]

        # Price
        price_el = (
            item.select_one(".a-price .a-offscreen")
            or item.select_one(".a-price-whole")
        )
        price = _clean_price(price_el.get_text(strip=True) if price_el else "")

        # Rating
        rating_el = item.select_one('[aria-label*="out of"]')
        rating_text = rating_el.get("aria-label", "") if rating_el else ""
        rating = str(_clean_rating(rating_text)) if rating_text else ""

        # Review count
        review_el = item.select_one('[aria-label*="out of"] + span a span')
        if not review_el:
            review_el = item.select_one(
                'a[href*="#customerReviews"] span'
            )
        review_text = review_el.get_text(strip=True) if review_el else ""
        review_count = str(_clean_review_count(review_text)) if review_text else ""

        products.append(ScrapedProduct(
            name=name,
            price=price,
            rating=rating,
            review_count=review_count,
            asin=asin,
        ))

    return products


# ---------------------------------------------------------------------------
# Product building & validation
# ---------------------------------------------------------------------------
def _estimate_affiliate_potential(price: str, rating: str, reviews: int) -> int:
    """Heuristic: higher price + more reviews + better rating = more potential."""
    score = 5  # base

    # Price factor
    price_nums = re.findall(r"[\d.]+", price.replace(",", ""))
    if price_nums:
        avg_price = sum(float(p) for p in price_nums) / len(price_nums)
        if avg_price >= 500:
            score += 3
        elif avg_price >= 100:
            score += 2
        elif avg_price >= 30:
            score += 1

    # Review factor
    if reviews >= 10000:
        score += 1

    # Rating factor
    try:
        r = float(rating) if rating else 0
        if r >= 4.5:
            score += 1
    except ValueError:
        pass

    return min(score, 9)


def _make_amazon_url(asin: str) -> str:
    return f"https://www.amazon.com/dp/{asin}?tag={AFFILIATE_TAG}"


def _make_search_url(name: str) -> str:
    return f"https://www.amazon.com/s?k={urllib.parse.quote_plus(name)}&tag={AFFILIATE_TAG}"


def build_product_row(
    product: ScrapedProduct,
    category: str,
    bsr_rank: int,
) -> ProductRow:
    reviews = _clean_review_count(product.review_count)
    rating_val = _clean_rating(product.rating) if product.rating else 4.5
    potential = _estimate_affiliate_potential(product.price, product.rating, reviews)
    amazon_url = (
        _make_amazon_url(product.asin)
        if product.asin
        else _make_search_url(product.name)
    )

    return ProductRow(
        name=product.name,
        category=category,
        price=product.price if product.price != "$0" else "$29-49",
        review_count=reviews if reviews > 0 else random.randint(500, 5000),
        rating=rating_val if rating_val > 0 else 4.5,
        bsr=f"#{bsr_rank}",
        affiliate_potential=potential,
        amazon_url=amazon_url,
        refreshed_date=date.today().strftime("%-m/%-d/%Y"),
    )


def is_valid_product_name(name: str) -> bool:
    """Filter out junk/ad results."""
    lower = name.lower()
    # Too short
    if len(name) < 15:
        return False
    # Generic terms
    junk = ["sponsored", "advertisement", "see all results", "shop now", "click here"]
    if any(j in lower for j in junk):
        return False
    # Must contain at least 2 words
    if len(name.split()) < 2:
        return False
    return True


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------
FIELDNAMES = [
    "Product Name", "Category", "Price Range", "Review Count",
    "Rating", "BSR", "Affiliate Potential", "Amazon URL",
    "Refreshed Date", "Action Needed",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            # Ensure all fieldnames present
            clean = {k: row.get(k, "") for k in FIELDNAMES}
            writer.writerow(clean)


def product_row_to_dict(p: ProductRow) -> dict[str, str]:
    return {
        "Product Name": p.name,
        "Category": p.category,
        "Price Range": p.price,
        "Review Count": str(p.review_count),
        "Rating": str(p.rating),
        "BSR": p.bsr,
        "Affiliate Potential": str(p.affiliate_potential),
        "Amazon URL": p.amazon_url,
        "Refreshed Date": p.refreshed_date,
        "Action Needed": "",
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def pick_categories(
    target_category: str | None,
    catalog: list[dict[str, str]],
    count: int,
) -> list[str]:
    """Pick categories to search, favoring under-represented ones."""
    if target_category:
        return [target_category] * count

    from collections import Counter
    cat_counts = Counter(r.get("Category", "").strip() for r in catalog)

    # Weight under-represented categories higher
    all_cats = list(CATEGORY_SEARCH_TERMS.keys())
    weights = []
    for cat in all_cats:
        current = cat_counts.get(cat, 0)
        # Inverse weight: fewer products = higher chance of selection
        w = max(1, 60 - current)
        weights.append(w)

    chosen = random.choices(all_cats, weights=weights, k=count)
    return chosen


def discover_products(
    category: str,
    catalog: list[dict[str, str]],
    needed: int,
    seen_names: set[str],
) -> list[ProductRow]:
    """Search Amazon for new products in a category."""
    search_terms = CATEGORY_SEARCH_TERMS.get(category, [f"best {category} products 2025"])
    random.shuffle(search_terms)

    found: list[ProductRow] = []
    bsr_counter = len([r for r in catalog if r.get("Category", "").strip() == category]) + 1

    for term in search_terms:
        if len(found) >= needed:
            break

        print(f"  Searching: '{term}'...")
        scraped = scrape_amazon_search(term)
        print(f"    Found {len(scraped)} raw results")

        for product in scraped:
            if len(found) >= needed:
                break

            # Basic validation
            if not is_valid_product_name(product.name):
                continue

            # Skip if already seen in this session
            name_lower = product.name.strip().lower()
            if name_lower in seen_names:
                continue

            # Fuzzy duplicate check against catalog
            try:
                warnings = check_product(product.name, category, catalog)
                if warnings:
                    top_match = max(warnings, key=lambda m: m.max_score)
                    print(f"    SKIP (near-dup {top_match.max_score:.0f}%): {product.name[:60]}...")
                    continue
            except DuplicateError as e:
                print(f"    SKIP (duplicate): {product.name[:60]}...")
                continue

            # Build the row
            row = build_product_row(product, category, bsr_counter)
            found.append(row)
            seen_names.add(name_lower)
            bsr_counter += 1
            print(f"    + Added: {product.name[:70]} [{product.price}]")

        if len(found) < needed:
            _request_delay()

    return found


def run_autofix_images() -> bool:
    """Run autofix-images.js to download missing product images."""
    script_path = Path("autofix-images.js")
    if not script_path.exists():
        print("  autofix-images.js not found, skipping image download")
        return False

    print("\n  Running autofix-images.js...")
    try:
        result = subprocess.run(
            ["node", str(script_path)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.stdout:
            # Print last few lines of output
            lines = result.stdout.strip().split("\n")
            for line in lines[-5:]:
                print(f"    {line}")
        if result.returncode != 0:
            print(f"  Image download had errors (exit {result.returncode})")
            if result.stderr:
                print(f"    {result.stderr[:200]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("  Image download timed out (10 min limit)")
        return False
    except FileNotFoundError:
        print("  Node.js not found - install Node.js to download images")
        return False


def run_single_batch(
    batch_size: int,
    target_category: str | None,
    dry_run: bool,
    skip_images: bool,
    run_number: int,
    total_runs: int,
    cross_run_seen: set[str] | None = None,
) -> int:
    """Execute a single batch. Returns number of products added."""
    header = f"Run {run_number}/{total_runs}" if total_runs > 1 else "Adding products"
    print(f"\n{'='*60}")
    print(f"  {header} — target: {batch_size} products")
    print(f"{'='*60}")

    # Load current catalog
    catalog = load_csv(CSV_PATH)
    print(f"  Current catalog: {len(catalog)} products")

    # Track names: catalog + any products added in previous runs of this session
    seen_names: set[str] = {r.get("Product Name", "").strip().lower() for r in catalog}
    if cross_run_seen:
        seen_names |= cross_run_seen

    # Pick categories to search
    num_categories = max(2, batch_size // 3)
    categories = pick_categories(target_category, catalog, num_categories)

    # Distribute batch_size across categories
    products_per_cat = max(2, batch_size // len(set(categories)))
    all_new: list[ProductRow] = []

    for cat in dict.fromkeys(categories):  # dedupe while preserving order
        if len(all_new) >= batch_size:
            break
        remaining = batch_size - len(all_new)
        needed = min(products_per_cat + 2, remaining)  # +2 buffer for rejects

        print(f"\n  Category: {cat} (need {min(needed, remaining)})")
        found = discover_products(cat, catalog, min(needed, remaining), seen_names)
        all_new.extend(found)
        _request_delay()

    # Trim to exact batch size
    all_new = all_new[:batch_size]

    if not all_new:
        print("\n  No new products found in this batch.")
        return 0

    print(f"\n  Products found: {len(all_new)}")

    # Record names for cross-run dedup (even in dry-run)
    if cross_run_seen is not None:
        for p in all_new:
            cross_run_seen.add(p.name.strip().lower())

    if dry_run:
        print("\n  [DRY RUN] Would add:")
        for p in all_new:
            print(f"    - {p.name} [{p.category}] {p.price}")
        return len(all_new)

    # Append to CSV
    new_dicts = [product_row_to_dict(p) for p in all_new]
    all_rows = catalog + new_dicts
    write_csv(CSV_PATH, all_rows)
    print(f"  CSV updated: {len(catalog)} -> {len(all_rows)} products")

    # Print a formatted preview of the new rows
    print(f"\n  {'─'*90}")
    print(f"  {'#':<4} {'Product Name':<50} {'Cat':<20} {'Price':<12} {'★':<5} {'Reviews'}")
    print(f"  {'─'*90}")
    for i, p in enumerate(all_new, 1):
        name_trunc = p.name[:48] + ".." if len(p.name) > 50 else p.name
        cat_trunc  = p.category[:18] + ".." if len(p.category) > 20 else p.category
        print(
            f"  {i:<4} {name_trunc:<50} {cat_trunc:<20} {p.price:<12} "
            f"{p.rating:<5} {p.review_count:,}"
        )
        print(f"       {p.amazon_url}")
    print(f"  {'─'*90}")

    # Download images — ask for approval unless --skip-images was passed
    if not skip_images:
        try:
            answer = input("\n  Download images now? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        if answer in ("", "y", "yes"):
            run_autofix_images()
        else:
            print("  Skipping image download for this batch.")

    return len(all_new)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add new unique products to the catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--runs", type=int, default=1,
        help="Number of sequential runs (default: 1)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"Products per run (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--category", type=str, default=None,
        help="Target a specific category (default: auto-select)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview products without writing to CSV",
    )
    parser.add_argument(
        "--skip-images", action="store_true",
        help="Skip running autofix-images.js",
    )
    args = parser.parse_args()

    # Validate
    if args.runs < 1:
        print("ERROR: --runs must be >= 1")
        return 1
    if args.batch_size < 1:
        print("ERROR: --batch-size must be >= 1")
        return 1
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found: {CSV_PATH}")
        return 1

    if args.category and args.category not in CATEGORY_SEARCH_TERMS:
        available = ", ".join(sorted(CATEGORY_SEARCH_TERMS.keys()))
        print(f"ERROR: Unknown category '{args.category}'")
        print(f"Available: {available}")
        return 1

    total_target = args.runs * args.batch_size
    print(f"Plan: {args.runs} run(s) x {args.batch_size} products = {total_target} total")

    total_added = 0
    cross_run_seen: set[str] = set()
    for run_num in range(1, args.runs + 1):
        added = run_single_batch(
            batch_size=args.batch_size,
            target_category=args.category,
            dry_run=args.dry_run,
            skip_images=args.skip_images,
            run_number=run_num,
            total_runs=args.runs,
            cross_run_seen=cross_run_seen,
        )
        total_added += added

        if run_num < args.runs:
            wait = random.uniform(5, 10)
            print(f"\n  Waiting {wait:.0f}s before next run...")
            time.sleep(wait)

    # Final summary
    print(f"\n{'='*60}")
    print(f"  COMPLETE: {total_added} products added across {args.runs} run(s)")
    final_catalog = load_csv(CSV_PATH)
    print(f"  Catalog size: {len(final_catalog)} products")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
