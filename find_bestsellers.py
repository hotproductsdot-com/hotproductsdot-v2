#!/usr/bin/env python3
"""
find_bestsellers.py — Discover high-volume Amazon products via Oxylabs.

Hits Amazon's Best Sellers pages directly (via the Oxylabs `amazon_bestsellers`
source) for each major category, applies quality filters, dedupes against the
existing catalog, and writes a JSON candidate list to
products/discovery/bestsellers-YYYY-MM-DD.json.

This is a *discovery* tool. It does not ingest. Review the JSON output, then
feed approved ASINs into `add_product_by_asin.py` (manually or via a follow-up
automation step).

Why this exists:
    `add_new_products.py` searches Amazon by keyword strings ("kitchen gadgets
    bestsellers" etc.) which returns relevance-ranked results biased by paid
    placement. That's not the same as actual best sellers. This script hits the
    BSR-ranked pages directly, surfacing products with measurable sales volume
    rather than search-engine-friendly ones.

Quality filters (sales-volume proxies):
    - Rating >= 4.5         (audience won't trust lower)
    - Review count >= 1000  (proxy for cumulative sales — sub-1000 is too niche)
    - Price $30 - $500      (affiliate sweet spot — too cheap = small commission;
                             too expensive = low conversion)
    - BSR within top 100    (Amazon ranks ~1M products per category; top-100
                             typically clears 5,000-50,000 units/month)

Usage:
    # First-time discovery, dry-run (no API calls — uses fixture data):
    python find_bestsellers.py --dry-run

    # Real run, default filters, all categories:
    python find_bestsellers.py

    # Tune filters:
    python find_bestsellers.py --min-rating 4.7 --min-reviews 5000 --max-bsr 25

    # Limit categories (faster, fewer API calls):
    python find_bestsellers.py --categories Kitchen,Beauty,Electronics

    # Custom output path:
    python find_bestsellers.py --output products/discovery/test.json

Env vars (read from .env via python-dotenv):
    OXYLABS_USERNAME — Oxylabs API user
    OXYLABS_PASSWORD — Oxylabs API password
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent
EXISTING_CSV = REPO_ROOT / "products" / "top-1000.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "products" / "discovery"
OXYLABS_ENDPOINT = "https://realtime.oxylabs.io/v1/queries"

# Amazon Best Sellers category slugs. Oxylabs `amazon_bestsellers` source accepts
# either a category node ID (numeric) or a slug. Slugs are more durable across
# Amazon's category-tree refactors than node IDs, so we use slugs.
#
# Map: human-readable name -> Amazon best-sellers slug (the part after
# /Best-Sellers- in the URL: amazon.com/Best-Sellers-{slug}/zgbs/{slug}).
CATEGORIES: dict[str, str] = {
    "Kitchen":       "kitchen",
    "Beauty":        "beauty",
    "Electronics":   "electronics",
    "Home & Garden": "garden",
    "Tools":         "hi",                 # "hi" = Tools & Home Improvement
    "Toys & Games":  "toys-and-games",
    "Health":        "hpc",                # health-personal-care
    "Sports":        "sporting-goods",
    "Office":        "office-products",
    "Pet Supplies":  "pet-supplies",
}

# Filter defaults. Override via CLI flags.
DEFAULTS = {
    "min_rating":  4.5,
    "min_reviews": 1000,
    "min_price":   30.0,
    "max_price":   500.0,
    "max_bsr":     100,
    "per_category": 25,   # take top-N from each category before filtering
}


@dataclass
class Candidate:
    """One bestseller candidate, post-filter."""
    asin: str
    title: str
    category: str
    bsr: int
    rating: float
    review_count: int
    price: float
    url: str
    image: str
    in_existing_catalog: bool


# ─── Oxylabs API ─────────────────────────────────────────────────────────────

def fetch_bestsellers(
    category_slug: str,
    *,
    username: str,
    password: str,
    timeout: int = 60,
) -> list[dict]:
    """Fetch one Amazon Best Sellers page via Oxylabs `amazon_bestsellers`.

    Returns the raw `results` list from the parsed response. Each item has at
    least: asin, title, price, rating, reviews_count, best_seller_rank, url,
    image. Returns [] on failure (logged) so the caller can continue with
    remaining categories.
    """
    payload = {
        "source": "amazon_bestsellers",
        "query": category_slug,
        "domain": "com",
        "geo_location": "90210",
        "parse": True,
    }
    try:
        resp = requests.post(
            OXYLABS_ENDPOINT,
            json=payload,
            auth=(username, password),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.warning("Oxylabs request failed for %s: %s", category_slug, exc)
        return []

    if resp.status_code != 200:
        try:
            body = resp.json()
        except ValueError:
            body = resp.text[:300]
        logger.warning("Oxylabs HTTP %s for %s: %s", resp.status_code, category_slug, body)
        return []

    data = resp.json()
    results = data.get("results") or []
    if not results:
        logger.warning("Oxylabs returned no results for %s", category_slug)
        return []

    # parse=True nests parsed content under results[0].content
    content = results[0].get("content", {}) or {}
    # Oxylabs `amazon_bestsellers` puts parsed items under content.results
    items = content.get("results") or content.get("organic") or []
    if isinstance(items, dict):
        # Some response shapes wrap items under a sub-key; flatten if needed.
        items = items.get("organic", []) or list(items.values())[0] if items else []
    logger.info("Fetched %d items from Best Sellers > %s", len(items), category_slug)
    return items


# ─── Parsing + filtering ─────────────────────────────────────────────────────

_BSR_RE = re.compile(r"#?(\d+)")


def _parse_bsr(raw: Any) -> int | None:
    """Extract a BSR rank from various shapes Oxylabs returns ('1', '#1', '#1,234')."""
    if isinstance(raw, int):
        return raw
    if not raw:
        return None
    m = _BSR_RE.search(str(raw).replace(",", ""))
    return int(m.group(1)) if m else None


def _parse_price(raw: Any) -> float:
    """Coerce Oxylabs price field (number, string, or '$X.YY') to float dollars."""
    if isinstance(raw, (int, float)):
        return float(raw)
    if not raw:
        return 0.0
    m = re.search(r"[\d,]+\.?\d*", str(raw))
    if not m:
        return 0.0
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return 0.0


def parse_item(item: dict, category: str) -> Candidate | None:
    """Convert one Oxylabs-returned dict to a Candidate, or None if unparseable.

    No filtering here — that happens in `apply_filters`. This function's job is
    only to normalize field names and types, since Oxylabs occasionally varies
    the response shape (e.g., `reviews_count` vs `ratings_total`).
    """
    asin = (item.get("asin") or "").strip()
    if not asin or len(asin) != 10:
        return None
    title = (item.get("title") or item.get("name") or "").strip()
    if not title:
        return None

    rating       = float(item.get("rating") or item.get("stars") or 0)
    review_count = int(item.get("reviews_count") or item.get("ratings_total") or 0)
    price        = _parse_price(item.get("price") or item.get("price_upper"))
    bsr          = _parse_bsr(item.get("best_seller_rank") or item.get("bsr") or item.get("rank"))
    url          = item.get("url") or f"https://www.amazon.com/dp/{asin}"
    image        = item.get("image") or item.get("url_image") or ""

    return Candidate(
        asin=asin,
        title=title,
        category=category,
        bsr=bsr or 0,
        rating=rating,
        review_count=review_count,
        price=price,
        url=url,
        image=image,
        in_existing_catalog=False,  # filled in by caller
    )


def apply_filters(cand: Candidate, *, min_rating: float, min_reviews: int,
                  min_price: float, max_price: float, max_bsr: int) -> bool:
    """True iff the candidate passes all quality filters.

    Logged at DEBUG level on failure so a `-v` run shows exactly why each
    candidate was rejected — important when tuning filter thresholds.
    """
    if cand.rating < min_rating:
        logger.debug("REJECT %s: rating %.2f < %.2f", cand.asin, cand.rating, min_rating)
        return False
    if cand.review_count < min_reviews:
        logger.debug("REJECT %s: reviews %d < %d", cand.asin, cand.review_count, min_reviews)
        return False
    if cand.price < min_price or cand.price > max_price:
        logger.debug("REJECT %s: price $%.2f outside [$%.0f, $%.0f]",
                     cand.asin, cand.price, min_price, max_price)
        return False
    if cand.bsr and cand.bsr > max_bsr:
        logger.debug("REJECT %s: BSR #%d > #%d", cand.asin, cand.bsr, max_bsr)
        return False
    return True


# ─── Existing catalog dedup ──────────────────────────────────────────────────

def load_existing_asins(csv_path: Path = EXISTING_CSV) -> set[str]:
    """Pull all ASINs already in `products/top-1000.csv`.

    The Amazon URL column has the canonical ASIN as its `/dp/<asin>` segment.
    We don't trust product-name fuzzy matching for dedup at this layer —
    `add_product_by_asin.py` already handles that downstream.
    """
    asins: set[str] = set()
    if not csv_path.exists():
        logger.warning("Catalog CSV not found: %s — every candidate will be 'new'", csv_path)
        return asins
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            url = row.get("Amazon URL") or ""
            m = re.search(r"/dp/([A-Z0-9]{10})", url)
            if m:
                asins.add(m.group(1))
    return asins


# ─── Dry-run fixture (no API call) ───────────────────────────────────────────

_FIXTURE_RESPONSE: dict[str, list[dict]] = {
    "kitchen": [
        {"asin": "B07VGRJDFY", "title": "Ninja AF101 Air Fryer 4 Quart",
         "price": 99.99, "rating": 4.7, "reviews_count": 89234,
         "best_seller_rank": 1, "url": "https://amazon.com/dp/B07VGRJDFY",
         "image": "https://example.com/img.jpg"},
        {"asin": "B08GC6PL3F", "title": "Stanley Quencher H2.0 FlowState 40 oz",
         "price": 44.95, "rating": 4.6, "reviews_count": 412905,
         "best_seller_rank": 2, "url": "https://amazon.com/dp/B08GC6PL3F",
         "image": "https://example.com/img2.jpg"},
        {"asin": "B0LOWQUAL", "title": "Cheap Spatula 99 cents",
         "price": 0.99, "rating": 3.2, "reviews_count": 12,
         "best_seller_rank": 50, "url": "https://amazon.com/dp/B0LOWQUAL",
         "image": ""},   # rejected: rating, reviews, price
    ],
    "beauty": [
        {"asin": "B07PBXXMKW", "title": "CeraVe Daily Moisturizing Lotion",
         "price": 17.78, "rating": 4.8, "reviews_count": 178432,
         "best_seller_rank": 1, "url": "https://amazon.com/dp/B07PBXXMKW",
         "image": ""},   # rejected: price ($17.78 < $30 default)
    ],
}


# ─── Orchestration ───────────────────────────────────────────────────────────

def discover(
    *,
    categories: dict[str, str],
    username: str,
    password: str,
    min_rating: float,
    min_reviews: int,
    min_price: float,
    max_price: float,
    max_bsr: int,
    per_category: int,
    dry_run: bool,
    sleep_between: float = 1.5,
) -> list[Candidate]:
    """Fetch + parse + filter + dedup all categories. Returns kept candidates."""
    existing_asins = load_existing_asins()
    logger.info("Existing catalog has %d ASINs (used for dedup)", len(existing_asins))

    seen_asins: set[str] = set()
    kept: list[Candidate] = []
    rejected_total = 0

    for human_name, slug in categories.items():
        logger.info("─── %s (%s) ───", human_name, slug)
        if dry_run:
            raw_items = _FIXTURE_RESPONSE.get(slug, [])
            logger.info("[dry-run] using %d fixture items", len(raw_items))
        else:
            raw_items = fetch_bestsellers(slug, username=username, password=password)

        # Take top-N before filter — many bestseller lists return 100+, we don't
        # need them all. Keeping per_category small bounds Oxylabs cost and
        # downstream review effort.
        raw_items = raw_items[:per_category]

        for item in raw_items:
            cand = parse_item(item, human_name)
            if cand is None:
                continue
            if cand.asin in seen_asins:
                # Cross-category dedup: a single product can rank in multiple
                # bestseller lists (e.g., a Stanley cup in both Kitchen and
                # Sports). Keep the first sighting.
                continue
            if not apply_filters(cand, min_rating=min_rating, min_reviews=min_reviews,
                                 min_price=min_price, max_price=max_price, max_bsr=max_bsr):
                rejected_total += 1
                continue
            cand.in_existing_catalog = cand.asin in existing_asins
            seen_asins.add(cand.asin)
            kept.append(cand)

        if not dry_run and sleep_between > 0:
            time.sleep(sleep_between)  # be polite to Oxylabs

    logger.info("Kept %d, rejected %d (across %d categories)",
                len(kept), rejected_total, len(categories))
    return kept


def write_output(candidates: list[Candidate], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    new_count = sum(1 for c in candidates if not c.in_existing_catalog)
    payload = {
        "generated_at": date.today().isoformat(),
        "total_kept": len(candidates),
        "new_to_catalog": new_count,
        "already_in_catalog": len(candidates) - new_count,
        "candidates": [asdict(c) for c in candidates],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    logger.info("Wrote %s (%d kept, %d new to catalog)",
                output_path, len(candidates), new_count)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true",
                   help="Use built-in fixture data instead of calling Oxylabs. No API charges.")
    p.add_argument("--categories", metavar="LIST",
                   help=f"Comma-separated category names. Default: all 10. "
                        f"Available: {', '.join(CATEGORIES)}")
    p.add_argument("--min-rating",  type=float, default=DEFAULTS["min_rating"])
    p.add_argument("--min-reviews", type=int,   default=DEFAULTS["min_reviews"])
    p.add_argument("--min-price",   type=float, default=DEFAULTS["min_price"])
    p.add_argument("--max-price",   type=float, default=DEFAULTS["max_price"])
    p.add_argument("--max-bsr",     type=int,   default=DEFAULTS["max_bsr"])
    p.add_argument("--per-category", type=int,  default=DEFAULTS["per_category"],
                   help="Top-N items pulled from each category before filtering")
    p.add_argument("--output", type=Path,
                   help="Output JSON path (default: products/discovery/bestsellers-YYYY-MM-DD.json)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Show DEBUG-level logs including per-candidate reject reasons")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    cats = CATEGORIES.copy()
    if args.categories:
        wanted = {c.strip() for c in args.categories.split(",") if c.strip()}
        unknown = wanted - set(cats)
        if unknown:
            print(f"Unknown categories: {sorted(unknown)}", file=sys.stderr)
            print(f"Available: {sorted(cats)}", file=sys.stderr)
            return 2
        cats = {k: v for k, v in cats.items() if k in wanted}

    if args.dry_run:
        username, password = "FIXTURE", "FIXTURE"
    else:
        username = os.environ.get("OXYLABS_USERNAME", "")
        password = os.environ.get("OXYLABS_PASSWORD", "")
        if not username or not password:
            print("OXYLABS_USERNAME and OXYLABS_PASSWORD must be set in .env (or use --dry-run).",
                  file=sys.stderr)
            return 1

    output_path = args.output or DEFAULT_OUTPUT_DIR / f"bestsellers-{date.today().isoformat()}.json"

    candidates = discover(
        categories   = cats,
        username     = username,
        password     = password,
        min_rating   = args.min_rating,
        min_reviews  = args.min_reviews,
        min_price    = args.min_price,
        max_price    = args.max_price,
        max_bsr      = args.max_bsr,
        per_category = args.per_category,
        dry_run      = args.dry_run,
    )

    write_output(candidates, output_path)

    if not candidates:
        print("\n[!] No candidates kept after filtering. Try loosening thresholds:", file=sys.stderr)
        print(f"    --min-reviews {max(100, args.min_reviews // 5)}  "
              f"--min-price {args.min_price / 2:.0f}  --max-bsr {args.max_bsr * 5}", file=sys.stderr)
        return 0

    # Print a compact preview to the terminal — first 10 candidates, sorted by
    # how strong the recommendation is (lowest BSR + most reviews).
    print("\n=== Top candidates (preview) ===")
    preview = sorted(candidates, key=lambda c: (c.bsr or 9999, -c.review_count))[:10]
    for c in preview:
        new_flag = "" if c.in_existing_catalog else "  [NEW]"
        print(f"  BSR #{c.bsr or '?':>3}  {c.category:<14}  {c.rating:.1f}* "
              f"{c.review_count:>7,} reviews  ${c.price:>7.2f}  "
              f"{c.title[:50]:<50}{new_flag}")
    print(f"\nFull JSON: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
