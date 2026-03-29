"""
Scrape Amazon bestsellers from high-commission categories and add to top-1000.csv.

Amazon Associates commission rates by category (2024):
  Luxury Beauty:        10%
  Amazon Games:         20% (digital only, excluded)
  Kitchen:              4.5%
  Books:                4.5%
  Apparel/Fashion:      4%
  Beauty:               4%
  Health & Personal:    4%
  Music/Physical:       3%
  Toys & Games:         3%
  Musical Instruments:  3%
"""

import csv
import random
import re
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

AFFILIATE_TAG = "hotproduct033-20"
CSV_PATH = Path(__file__).parent / "products" / "top-1000.csv"

# Categories sorted by commission rate (highest first)
TARGET_CATEGORIES = [
    ("Luxury Beauty",         "luxury-beauty",          10),
    ("Kitchen",               "kitchen",                 4),  # 4.5 rounded for Affiliate Potential score
    ("Books",                 "books",                   4),
    ("Beauty",                "beauty",                  4),
    ("Health & Personal Care","health-personal-care",    4),
    ("Apparel",               "apparel",                 4),
    ("Toys & Games",          "toys-and-games",          3),
    ("Musical Instruments",   "musical-instruments",     3),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xhtml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
    "DNT": "1",
}


def affiliate_url(asin: str) -> str:
    return f"https://www.amazon.com/dp/{asin}?tag={AFFILIATE_TAG}"


def fetch_page(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [!] HTTP {resp.status_code} for {url}")
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"  [!] Request error: {e}")
        return None


def extract_asin(url_or_text: str) -> str | None:
    match = re.search(r"/dp/([A-Z0-9]{10})", url_or_text)
    return match.group(1) if match else None


def scrape_bestsellers(slug: str, category_name: str, max_items: int = 5) -> list[dict]:
    url = f"https://www.amazon.com/gp/bestsellers/{slug}/"
    print(f"  Fetching: {url}")
    soup = fetch_page(url)
    if not soup:
        return []

    products = []

    # Amazon bestseller grid items
    items = soup.select("div[data-asin]")
    if not items:
        # Fallback selector
        items = soup.select(".zg-grid-general-faceout, .p13n-asin")

    rank = 1
    for item in items:
        if len(products) >= max_items:
            break

        asin = item.get("data-asin", "")
        if not asin or len(asin) != 10:
            # Try extracting from a link
            link = item.select_one("a[href*='/dp/']")
            if link:
                asin = extract_asin(link.get("href", "")) or ""
        if not asin:
            continue

        # Title
        title_el = item.select_one(
            "._cDEzb_p13n-sc-css-line-clamp-3_g3dy1, "
            ".p13n-sc-truncated, "
            "span.a-truncate-cut, "
            "div.p13n-sc-product-link span"
        )
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            title_el = item.select_one("a img")
            title = title_el.get("alt", "").strip() if title_el else ""
        if not title:
            continue

        # Price
        price_el = item.select_one("span.p13n-sc-price, span._cDEzb_p13n-sc-price_3mJ9Z")
        price_text = price_el.get_text(strip=True) if price_el else ""
        price_range = _format_price(price_text)

        # Rating
        rating_el = item.select_one("span.a-icon-alt")
        rating_text = rating_el.get_text(strip=True) if rating_el else ""
        rating = _parse_rating(rating_text)

        # Review count
        reviews_el = item.select_one("span.a-size-small")
        review_text = reviews_el.get_text(strip=True) if reviews_el else "0"
        review_count = _parse_int(review_text)

        products.append({
            "asin": asin,
            "title": title,
            "category": category_name,
            "price_range": price_range,
            "review_count": review_count,
            "rating": rating,
            "bsr_rank": rank,
            "url": affiliate_url(asin),
        })
        rank += 1

    print(f"  Found {len(products)} products in {category_name}")
    return products


def _format_price(price_text: str) -> str:
    if not price_text:
        return "N/A"
    # Remove currency symbols and clean up
    price_text = re.sub(r"[^\d\.\-]", "", price_text)
    try:
        val = float(price_text)
        low = round(val * 0.9)
        high = round(val * 1.1)
        return f"${low}-{high}"
    except ValueError:
        return f"${price_text}" if price_text else "N/A"


def _parse_rating(text: str) -> float:
    match = re.search(r"(\d+\.?\d*)", text)
    return float(match.group(1)) if match else 0.0


def _parse_int(text: str) -> int:
    text = text.replace(",", "").replace(".", "")
    match = re.search(r"\d+", text)
    return int(match.group()) if match else 0


def load_existing_asins() -> set[str]:
    """Extract existing ASINs from the CSV to avoid duplicates."""
    asins: set[str] = set()
    if not CSV_PATH.exists():
        return asins
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("Amazon URL", "")
            asin = extract_asin(url)
            if asin:
                asins.add(asin)
    return asins


def commission_score(commission_rate: int, rating: float, review_count: int, bsr_rank: int) -> float:
    """Score to rank products: higher commission + popularity wins."""
    popularity = min(review_count / 10000, 1.0)  # normalize to 0-1
    rank_score = max(0, (100 - bsr_rank) / 100)   # lower rank = higher score
    return (commission_rate * 2) + (rating * 1.5) + (popularity * 3) + (rank_score * 2)


def append_to_csv(new_rows: list[dict]) -> int:
    """Append new products to the CSV. Returns count of rows added."""
    fieldnames = [
        "Product Name", "Category", "Price Range", "Review Count",
        "Rating", "BSR", "Affiliate Potential", "Amazon URL", "Refreshed Date"
    ]
    today = date.today().isoformat()
    added = 0

    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        for row in new_rows:
            writer.writerow({
                "Product Name":     row["title"],
                "Category":         row["category"],
                "Price Range":      row["price_range"],
                "Review Count":     row["review_count"],
                "Rating":           row["rating"],
                "BSR":              f"#{row['bsr_rank']}",
                "Affiliate Potential": row["commission_rate"],
                "Amazon URL":       row["url"],
                "Refreshed Date":   today,
            })
            added += 1

    return added


def main() -> None:
    print("=" * 60)
    print("Amazon Bestseller Affiliate Scraper")
    print("=" * 60)

    existing_asins = load_existing_asins()
    print(f"Existing products in CSV: {len(existing_asins)}")

    all_candidates: list[dict] = []

    for category_name, slug, commission_rate in TARGET_CATEGORIES:
        print(f"\n[{commission_rate}%] {category_name}")
        products = scrape_bestsellers(slug, category_name, max_items=8)
        for p in products:
            if p["asin"] not in existing_asins:
                p["commission_rate"] = commission_rate
                p["score"] = commission_score(
                    commission_rate, p["rating"], p["review_count"], p["bsr_rank"]
                )
                all_candidates.append(p)
        # Be polite — delay between category requests
        time.sleep(random.uniform(2.0, 4.0))

    if not all_candidates:
        print("\n[!] No new products found. Amazon may be blocking requests.")
        print("    Consider using the Amazon Product Advertising API instead.")
        return

    # Sort by score, take top 20
    all_candidates.sort(key=lambda x: x["score"], reverse=True)
    top_20 = all_candidates[:20]

    print(f"\n{'=' * 60}")
    print(f"Top 20 candidates (by affiliate score):")
    print(f"{'=' * 60}")
    for i, p in enumerate(top_20, 1):
        print(f"{i:2}. [{p['commission_rate']}%] {p['title'][:55]:<55} | {p['category']}")

    count = append_to_csv(top_20)
    print(f"\n✓ Added {count} products to {CSV_PATH}")


if __name__ == "__main__":
    main()
