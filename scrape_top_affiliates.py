#!/usr/bin/env python3
"""
scrape_top_affiliates.py — Add high-commission products to products/top-1000.csv

Combines he best of both approaches:
  - Oxylabs API for reliable data (falls back to direct scraping)
  - Fuzzy duplicate detection via check_duplicates.py (from add_new_products)
  - 37 categories with weighted selection for under-represented ones
  - Commission-rate-aware, revenue-weighted affiliate scoring
  - Product name validation + smart truncation
  - Automatic image download after each batch

Data sources (tried in order):
  1. Oxylabs Web Scraper API  (if OXYLABS_USERNAME is set in .env)
  2. Direct HTTP scraping      (fallback — unreliable due to Amazon anti-bot)

Usage:
  python scrape_top_affiliates.py                         # 1 run = 10 products
  python scrape_top_affiliates.py --runs 5                # 5 runs = 50 products
  python scrape_top_affiliates.py --batch-size 15         # 1 run = 15 products
  python scrape_top_affiliates.py --category "Kitchen"    # target one category
  python scrape_top_affiliates.py --dry-run               # preview without writing
  python scrape_top_affiliates.py --skip-images           # skip image download
"""
from __future__ import annotations

import argparse
import csv
import logging
import math
import os
import random
import re
import subprocess
import sys
import time
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NamedTuple

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from scrapling.fetchers import FetcherSession

# ── Duplicate checking (reuse from add_new_products) ─────────────────────────
sys.path.insert(0, str(Path(__file__).parent / "products"))
from check_duplicates import DuplicateError, check_product, load_catalog

# ── Configuration ────────────────────────────────────────────────────────────

load_dotenv(Path(__file__).parent / ".env")

AFFILIATE_TAG = "hotproduct033-20"
CSV_PATH = Path(__file__).parent / "products" / "top-1000.csv"
DEFAULT_BATCH_SIZE = 10
MAX_RETRIES = 3
REQUEST_DELAY_MIN = 3.0
REQUEST_DELAY_MAX = 6.0

CSV_FIELDNAMES = [
    "Product Name", "Category", "Price Range", "Review Count",
    "Rating", "BSR", "Affiliate Potential", "Amazon URL",
    "Refreshed Date", "Action Needed",
]

# ── Commission rates by category ─────────────────────────────────────────────
# Categories with their Amazon Associates commission rate (%)
COMMISSION_RATES: dict[str, float] = {
    "Luxury Beauty":       10.0,
    "Beauty":               4.0,
    "Kitchen":              4.5,
    "Books":                4.5,
    "Health & Personal Care": 4.0,
    "Health & Wellness":    4.0,
    "Personal Care":        4.0,
    "Apparel":              4.0,
    "Toys & Games":         3.0,
    "Musical Instruments":  3.0,
    # Default for unlisted categories
}
DEFAULT_COMMISSION = 2.5

# ── Category → Amazon search terms (from add_new_products.py) ────────────────
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

# ── Logging ──────────────────────────────────────────────────────────────────

log = logging.getLogger("scrape_affiliates")


# ── Data types ───────────────────────────────────────────────────────────────

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


# ── Data source detection ────────────────────────────────────────────────────

def _get_data_source() -> str:
    if os.getenv("OXYLABS_USERNAME") and os.getenv("OXYLABS_PASSWORD"):
        return "oxylabs"
    return "direct"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_commission(category: str) -> float:
    """Get commission rate for a category."""
    return COMMISSION_RATES.get(category, DEFAULT_COMMISSION)


def _affiliate_url(asin: str) -> str:
    return f"https://www.amazon.com/dp/{asin}?tag={AFFILIATE_TAG}"


def _search_url(name: str) -> str:
    return f"https://www.amazon.com/s?k={urllib.parse.quote_plus(name)}&tag={AFFILIATE_TAG}"


def _request_delay(source: str = "direct") -> None:
    if source == "direct":
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    else:
        delay = random.uniform(0.5, 1.5)
    time.sleep(delay)


def extract_asin(url_or_text: str) -> str | None:
    match = re.search(r"/dp/([A-Z0-9]{10})", url_or_text)
    return match.group(1) if match else None


# ── Price / rating / review parsing (from add_new_products) ──────────────────

def _clean_price(raw: str) -> str:
    """Normalize a price string from Amazon."""
    raw = raw.strip()
    raw = re.sub(r"^from\s+", "", raw, flags=re.IGNORECASE)
    prices = re.findall(r"\$[\d,]+(?:\.\d{2})?", raw)
    if len(prices) >= 2:
        return f"{prices[0]}-{prices[1]}"
    if len(prices) == 1:
        return prices[0]
    return raw if raw else "$0"


def _extract_price_value(price_text: str) -> float:
    """Extract a float dollar value from a price string for scoring."""
    if not price_text or price_text in ("N/A", "$0"):
        return 0.0
    cleaned = re.sub(r"[^\d.,]", "", price_text.split("-")[0])
    try:
        return float(cleaned.replace(",", ""))
    except ValueError:
        return 0.0


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


# ── Product name validation (from add_new_products) ──────────────────────────

def is_valid_product_name(name: str) -> bool:
    """Filter out junk/ad results."""
    lower = name.lower()
    if len(name) < 15:
        return False
    junk = ["sponsored", "advertisement", "see all results", "shop now", "click here"]
    if any(j in lower for j in junk):
        return False
    if len(name.split()) < 2:
        return False
    return True


def _truncate_name(name: str, max_len: int = 120) -> str:
    """Truncate overly long product names at natural boundaries."""
    if len(name) <= max_len:
        return name
    cut_points = [" - ", " | ", ", ", " with "]
    for cut in cut_points:
        idx = name.find(cut, 40)
        if idx != -1 and idx < max_len:
            return name[:idx]
    return name[:max_len].rsplit(" ", 1)[0]


# ── CAPTCHA / block detection ────────────────────────────────────────────────

def _is_blocked(soup: BeautifulSoup) -> bool:
    """Detect Amazon CAPTCHA / bot-block pages."""
    if not soup:
        return True
    page_text = soup.get_text(strip=True).lower()
    block_signals = [
        "sorry, we just need to make sure you're not a robot",
        "enter the characters you see below",
        "type the characters you see in this image",
        "to discuss automated access",
        "api-services-support@amazon.com",
    ]
    return any(signal in page_text for signal in block_signals)


# ── Affiliate scoring (revenue-weighted) ─────────────────────────────────────

def affiliate_score(
    commission_rate: float,
    price_value: float,
    rating: float,
    review_count: int,
) -> int:
    """
    Revenue-weighted affiliate potential score (1-10 scale).

    Factors:
      - Estimated commission per sale (price × rate)
      - Rating quality
      - Popularity (log-scaled review count)
    """
    score = 5  # base

    # Commission revenue factor (price × commission rate)
    est_commission = (price_value * commission_rate / 100) if price_value > 0 else 0
    if est_commission >= 20:
        score += 3
    elif est_commission >= 5:
        score += 2
    elif est_commission >= 1:
        score += 1

    # Review popularity factor
    if review_count >= 10000:
        score += 1

    # Rating factor
    if rating >= 4.5:
        score += 1

    return min(score, 10)


# ── Oxylabs API scraping ─────────────────────────────────────────────────────

def scrape_via_oxylabs(query: str, max_results: int = 20) -> list[ScrapedProduct]:
    """
    Use Oxylabs Web Scraper API to search Amazon.

    Matches the payload format used by the working oxylabs-amazon-product.sh:
      - source: "amazon_search" (search results) or "amazon_product" (single ASIN)
      - query:  plain search keywords (NOT a URL)
      - domain: "com"
      - geo_location: ZIP code for localized results
      - parse:  true for structured JSON
    """
    username = os.getenv("OXYLABS_USERNAME")
    password = os.getenv("OXYLABS_PASSWORD")

    log.info(f"    Oxylabs search: {query}")

    # Match the working shell script format — use 'query' with plain
    # search terms, NOT 'url' with a full Amazon URL
    payload = {
        "source": "amazon_search",
        "query": query,
        "domain": "com",
        "geo_location": "90210",
        "parse": True,
        "pages": 1,
    }

    try:
        resp = requests.post(
            "https://realtime.oxylabs.io/v1/queries",
            json=payload,
            auth=(username, password),
            timeout=60,
        )
        if resp.status_code != 200:
            # Log the response body for debugging
            try:
                error_body = resp.json()
                log.warning(f"    [!] Oxylabs HTTP {resp.status_code}: {error_body}")
            except Exception:
                log.warning(f"    [!] Oxylabs HTTP {resp.status_code}: {resp.text[:200]}")
            return []

        data = resp.json()
        results = data.get("results", [{}])
        if not results:
            return []

        content = results[0].get("content", {})

        # Oxylabs amazon_search returns results under "results.organic"
        # (parsed mode). Try multiple known keys.
        organic = (
            content.get("results", {}).get("organic", [])  # parsed: content.results.organic
            if isinstance(content.get("results"), dict)
            else content.get("results", content.get("organic", []))  # flat list fallback
        )

        products = []
        for item in organic[:max_results]:
            asin = item.get("asin", "")
            title = item.get("title", "")
            if not asin or len(asin) != 10 or not title:
                continue

            # Name validation
            if not is_valid_product_name(title):
                continue
            title = _truncate_name(title)

            price = item.get("price_upper", item.get("price", 0))
            price_str = f"${price}" if price else "$0"
            rating = str(float(item.get("rating", 0) or 0))
            reviews = str(int(item.get("reviews_count", item.get("ratings_count", 0)) or 0))

            products.append(ScrapedProduct(
                name=title,
                price=_clean_price(price_str),
                rating=rating,
                review_count=reviews,
                asin=asin,
            ))

        log.info(f"    Found {len(products)} products via Oxylabs")
        return products

    except requests.RequestException as e:
        log.error(f"    [!] Oxylabs request failed: {e}")
        return []


# ── Direct scraping (fallback) ───────────────────────────────────────────────

def scrape_amazon_search(query: str, max_results: int = 20) -> list[ScrapedProduct]:
    """Scrape Amazon search results via Scrapling (TLS fingerprint impersonation)."""
    url = f"https://www.amazon.com/s?k={urllib.parse.quote_plus(query)}"
    _fetcher = FetcherSession()

    resp = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = _fetcher.get(url, timeout=15, retries=1)
            if resp.status == 503:
                log.warning(f"    Rate limited (503), retry {attempt + 1}/{MAX_RETRIES}...")
                time.sleep(10 + random.uniform(5, 15))
                resp = None
                continue
            if resp.status != 200:
                log.warning(f"    HTTP {resp.status} for query '{query}'")
                return []
            break
        except Exception as e:
            log.warning(f"    Request error: {e}, retry {attempt + 1}/{MAX_RETRIES}...")
            time.sleep(5)

    if resp is None:
        return []

    soup = BeautifulSoup(resp.body, "html.parser")

    if _is_blocked(soup):
        log.warning("    [!] Amazon returned a CAPTCHA/block page")
        log.warning("        Configure Oxylabs API in .env for reliable scraping")
        return []

    products: list[ScrapedProduct] = []

    # Search result items (from add_new_products — proven selectors)
    items = soup.select('[data-component-type="s-search-result"]')
    if not items:
        items = soup.select(".s-result-item[data-asin]")

    for item in items[:max_results]:
        asin = item.get("data-asin", "")
        if not asin or len(asin) != 10:
            continue

        # Product name (from add_new_products — stable selectors)
        title_el = (
            item.select_one("h2 a span")
            or item.select_one("h2 span")
            or item.select_one(".a-text-normal")
        )
        if not title_el:
            continue
        name = title_el.get_text(strip=True)

        if not is_valid_product_name(name):
            continue
        name = _truncate_name(name)

        # Price (from add_new_products — stable selectors)
        price_el = (
            item.select_one(".a-price .a-offscreen")
            or item.select_one(".a-price-whole")
        )
        price = _clean_price(price_el.get_text(strip=True) if price_el else "")

        # Rating (from add_new_products — aria-label based, very stable)
        rating_el = item.select_one('[aria-label*="out of"]')
        rating_text = rating_el.get("aria-label", "") if rating_el else ""
        rating = str(_clean_rating(rating_text)) if rating_text else ""

        # Review count
        review_el = item.select_one('[aria-label*="out of"] + span a span')
        if not review_el:
            review_el = item.select_one('a[href*="#customerReviews"] span')
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


# ── Product building ─────────────────────────────────────────────────────────

def build_product_row(
    product: ScrapedProduct,
    category: str,
    bsr_rank: int,
) -> ProductRow:
    """Build a validated ProductRow from scraped data."""
    reviews = _clean_review_count(product.review_count)
    rating_val = _clean_rating(product.rating) if product.rating else 4.5
    commission = _get_commission(category)
    price_value = _extract_price_value(product.price)
    potential = affiliate_score(commission, price_value, rating_val, reviews)

    amazon_url = (
        _affiliate_url(product.asin)
        if product.asin
        else _search_url(product.name)
    )

    return ProductRow(
        name=product.name,
        category=category,
        price=product.price,
        review_count=reviews,
        rating=rating_val,
        bsr=f"#{bsr_rank}",
        affiliate_potential=potential,
        amazon_url=amazon_url,
        refreshed_date=f"{date.today().month}/{date.today().day}/{date.today().year}",
    )


# ── CSV I/O ──────────────────────────────────────────────────────────────────

def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Full rewrite of CSV — safe because we always have the complete dataset."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            clean = {k: row.get(k, "") for k in CSV_FIELDNAMES}
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


# ── Category selection (weighted toward under-represented) ───────────────────

def pick_categories(
    target_category: str | None,
    catalog: list[dict[str, str]],
    count: int,
) -> list[str]:
    """Pick categories to search, favoring under-represented ones."""
    if target_category:
        return [target_category] * count

    cat_counts = Counter(r.get("Category", "").strip() for r in catalog)
    all_cats = list(CATEGORY_SEARCH_TERMS.keys())

    # Weight under-represented categories higher
    weights = []
    for cat in all_cats:
        current = cat_counts.get(cat, 0)
        # Boost for high-commission categories
        commission_boost = _get_commission(cat) / DEFAULT_COMMISSION
        w = max(1, 60 - current) * commission_boost
        weights.append(w)

    return random.choices(all_cats, weights=weights, k=count)


# ── Image download ───────────────────────────────────────────────────────────

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
        print("  Node.js not found — install Node.js to download images")
        return False


# ── Product discovery pipeline ───────────────────────────────────────────────

def discover_products(
    category: str,
    catalog: list[dict[str, str]],
    needed: int,
    seen_names: set[str],
    source: str,
) -> list[ProductRow]:
    """
    Search Amazon for new products in a category.

    Uses fuzzy duplicate detection from check_duplicates.py.
    """
    search_terms = CATEGORY_SEARCH_TERMS.get(category, [f"best {category} products 2025"])
    random.shuffle(search_terms)

    found: list[ProductRow] = []
    bsr_counter = len([r for r in catalog if r.get("Category", "").strip() == category]) + 1

    for term in search_terms:
        if len(found) >= needed:
            break

        print(f"  Searching: '{term}'...")

        # Use Oxylabs or direct scraping based on data source
        if source == "oxylabs":
            scraped = scrape_via_oxylabs(term)
        else:
            scraped = scrape_amazon_search(term)

        print(f"    Found {len(scraped)} raw results")

        for product in scraped:
            if len(found) >= needed:
                break

            # Skip if already seen in this session
            name_lower = product.name.strip().lower()
            if name_lower in seen_names:
                continue

            # Skip products with missing/zero price — refuse to fabricate data
            if _extract_price_value(product.price) <= 0:
                print(f"    SKIP (no price): {product.name[:60]}...")
                continue

            # Fuzzy duplicate check against catalog (from add_new_products)
            try:
                warnings = check_product(product.name, category, catalog, asin=product.asin)
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

            commission = _get_commission(category)
            print(
                f"    + Added: {product.name[:65]} [{product.price}] "
                f"[{commission}% commission] [score={row.affiliate_potential}]"
            )

        if len(found) < needed:
            _request_delay(source)

    return found


# ── Single batch execution ───────────────────────────────────────────────────

def run_single_batch(
    batch_size: int,
    target_category: str | None,
    dry_run: bool,
    skip_images: bool,
    run_number: int,
    total_runs: int,
    source: str,
    cross_run_seen: set[str] | None = None,
) -> int:
    """Execute a single batch. Returns number of products added."""
    header = f"Run {run_number}/{total_runs}" if total_runs > 1 else "Adding products"
    print(f"\n{'='*60}")
    print(f"  {header} — target: {batch_size} products")
    print(f"  Data source: {source.upper()}")
    print(f"{'='*60}")

    # Load current catalog
    catalog = load_csv(CSV_PATH)
    print(f"  Current catalog: {len(catalog)} products")

    # Track names: catalog + any products added in previous runs
    seen_names: set[str] = {r.get("Product Name", "").strip().lower() for r in catalog}
    if cross_run_seen:
        seen_names |= cross_run_seen

    # Pick categories (weighted toward under-represented + high-commission)
    num_categories = max(2, batch_size // 3)
    categories = pick_categories(target_category, catalog, num_categories)

    # Distribute batch_size across categories
    products_per_cat = max(2, batch_size // len(set(categories)))
    all_new: list[ProductRow] = []

    for cat in dict.fromkeys(categories):  # dedupe while preserving order
        if len(all_new) >= batch_size:
            break
        remaining = batch_size - len(all_new)
        needed = min(products_per_cat + 2, remaining)

        commission = _get_commission(cat)
        print(f"\n  Category: {cat} ({commission}% commission, need {min(needed, remaining)})")
        found = discover_products(cat, catalog, min(needed, remaining), seen_names, source)
        all_new.extend(found)
        _request_delay(source)

    # Trim to exact batch size
    all_new = all_new[:batch_size]

    if not all_new:
        print("\n  No new products found in this batch.")
        if source == "direct":
            print("  Amazon may be blocking requests. Configure Oxylabs API in .env")
        return 0

    print(f"\n  Products found: {len(all_new)}")

    # Record names for cross-run dedup
    if cross_run_seen is not None:
        for p in all_new:
            cross_run_seen.add(p.name.strip().lower())

    if dry_run:
        print("\n  [DRY RUN] Would add:")
        for p in all_new:
            commission = _get_commission(p.category)
            print(f"    - {p.name[:65]} [{p.category}] {p.price} [{commission}%] score={p.affiliate_potential}")
        return len(all_new)

    # Append to CSV (full rewrite for safety)
    new_dicts = [product_row_to_dict(p) for p in all_new]
    all_rows = catalog + new_dicts
    write_csv(CSV_PATH, all_rows)
    print(f"  CSV updated: {len(catalog)} → {len(all_rows)} products")

    # Formatted preview
    print(f"\n  {'─'*95}")
    print(f"  {'#':<4} {'Product Name':<50} {'Cat':<18} {'Price':<12} {'★':<5} {'Com%':<5} {'Score'}")
    print(f"  {'─'*95}")
    for i, p in enumerate(all_new, 1):
        name_trunc = p.name[:48] + ".." if len(p.name) > 50 else p.name
        cat_trunc = p.category[:16] + ".." if len(p.category) > 18 else p.category
        commission = _get_commission(p.category)
        print(
            f"  {i:<4} {name_trunc:<50} {cat_trunc:<18} {p.price:<12} "
            f"{p.rating:<5} {commission:<5} {p.affiliate_potential}"
        )
        print(f"       {p.amazon_url}")
    print(f"  {'─'*95}")

    # Download images
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


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape Amazon for high-commission affiliate products",
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
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

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

    source = _get_data_source()
    total_target = args.runs * args.batch_size

    print("=" * 60)
    print("  Amazon Affiliate Product Scraper")
    print(f"  Data source:   {source.upper()}")
    print(f"  Affiliate tag: {AFFILIATE_TAG}")
    print(f"  Plan:          {args.runs} run(s) × {args.batch_size} products = {total_target} total")
    print(f"  Dry run:       {args.dry_run}")
    print("=" * 60)

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
            source=source,
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
