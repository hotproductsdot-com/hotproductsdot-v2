#!/usr/bin/env python3
"""
find_bestsellers.py — Discover high-volume Amazon products via direct HTML scrape.

Hits Amazon's Best Sellers pages (https://www.amazon.com/gp/bestsellers/<category>)
with realistic browser headers, parses the product grid with BeautifulSoup,
applies quality filters, dedupes against the existing catalog by ASIN, and
writes a JSON candidate list to products/discovery/bestsellers-YYYY-MM-DD.json.

This is a *discovery* tool. It does not ingest. Review the JSON output, then
feed approved ASINs into `add_product_by_asin.py` (manually or via a follow-up
automation step).

Why direct HTML scraping (not Oxylabs / not PA-API):
    - Oxylabs free trial running out; full sub is $49/mo for our trivial volume
    - PA-API + Creators API both require an *Approved* Associates account
      (3 qualifying sales / 180 days), which we don't have yet
    - Best Sellers pages are public, indexed, SEO-friendly — Amazon tolerates
      polite low-volume scraping of these pages even though they aggressively
      block search/detail pages
    - This codebase's `add_new_products.py` already uses the same pattern
      successfully

Quality filters (sales-volume proxies):
    - Rating >= 4.5         (audience won't trust lower)
    - Review count >= 1000  (proxy for cumulative sales — sub-1000 is too niche)
    - Price $30 - $500      (affiliate sweet spot)
    - BSR within top 100    (rank position on the page)

Usage:
    # Dry-run with built-in fixture data (no network calls — validates pipeline):
    python find_bestsellers.py --dry-run

    # Real run, default filters, all categories:
    python find_bestsellers.py

    # Tune filters:
    python find_bestsellers.py --min-rating 4.7 --min-reviews 5000 --max-bsr 25

    # Limit categories (faster, fewer requests):
    python find_bestsellers.py --categories Kitchen,Beauty,Electronics

    # Custom output path:
    python find_bestsellers.py --output products/discovery/test.json

No env vars or credentials needed.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent
EXISTING_CSV = REPO_ROOT / "products" / "top-1000.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "products" / "discovery"

# Pool of realistic browser User-Agents. Mirrors add_new_products.py's pool —
# rotating these across requests lowers the chance of pattern-based blocking.
USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
)

# Amazon Best Sellers category slugs. The /gp/bestsellers/ URL pattern accepts
# these short slugs and Amazon redirects to the canonical /Best-Sellers-X URL.
# These slugs are stable across Amazon's category-tree refactors more reliably
# than node IDs.
CATEGORIES: dict[str, str] = {
    "Kitchen":       "kitchen",
    "Beauty":        "beauty",
    "Electronics":   "electronics",
    "Home & Garden": "home-garden",
    "Tools":         "hi",                 # Tools & Home Improvement
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
    "per_category": 25,
}

REQUEST_DELAY_MIN = 2.0
REQUEST_DELAY_MAX = 5.0
REQUEST_TIMEOUT   = 30


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


# ─── HTTP fetch ──────────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    """Realistic browser headers with rotated User-Agent."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def _polite_delay() -> None:
    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))


def fetch_bestsellers_html(category_slug: str) -> str | None:
    """Fetch the raw HTML of Amazon's Best Sellers page for a category.

    Returns None on failure (logged) so the caller can continue with remaining
    categories. Two failure modes worth watching:
      - HTTP 503/429 — Amazon is throttling. Increase delays or wait it out.
      - HTTP 200 but body is captcha challenge HTML — rotate User-Agent and
        retry once; if it persists, this category is blocked for now.
    """
    url = f"https://www.amazon.com/gp/bestsellers/{category_slug}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("Fetch failed for %s: %s", category_slug, exc)
        return None

    if resp.status_code != 200:
        logger.warning("HTTP %s for %s", resp.status_code, category_slug)
        return None

    body = resp.text
    # Quick check for CAPTCHA / robot-check pages — Amazon serves these with
    # 200 OK but the body is a "Type the characters you see" challenge.
    if "Type the characters you see" in body or "Robot Check" in body:
        logger.warning("CAPTCHA challenge for %s — skipping", category_slug)
        return None

    return body


# ─── HTML parsing ────────────────────────────────────────────────────────────

_ASIN_RE     = re.compile(r"/dp/([A-Z0-9]{10})")
_RATING_RE   = re.compile(r"(\d+(?:\.\d+)?)\s+out of 5")
_REVIEWS_RE  = re.compile(r"([\d,]+)")
_RANK_RE     = re.compile(r"#?(\d+)")
_PRICE_RE    = re.compile(r"\$([\d,]+(?:\.\d+)?)")


def parse_bestsellers_html(html: str, category: str) -> list[dict]:
    """Extract one dict per product card from a Best Sellers page.

    Strategy: find all product anchors (links matching /dp/<ASIN>) on the page,
    walk up to the enclosing card element, then pull the title/rating/etc.
    from text within that card. This is more robust than relying on Amazon's
    specific class names (they change roughly every 6 months).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Each product card has a clickable anchor with /dp/<ASIN> in href. Use that
    # as the anchor for traversal.
    product_links = soup.select('a[href*="/dp/"]')
    seen_asins: set[str] = set()
    items: list[dict] = []

    for rank_position, link in enumerate(product_links, start=1):
        href = link.get("href") or ""
        asin_m = _ASIN_RE.search(href)
        if not asin_m:
            continue
        asin = asin_m.group(1)
        if asin in seen_asins:
            continue  # same product appears as both image-link and title-link
        seen_asins.add(asin)

        # Walk up to the nearest card-like container. Amazon's Best Sellers
        # cards typically have id="gridItemRoot" on a div ancestor, but fall
        # back to the link's grandparent if we can't find that.
        card = link.find_parent(id="gridItemRoot") or link.find_parent("li") or link.parent.parent

        text = card.get_text(" ", strip=True) if card else ""

        # ── Rank: explicit page position. Amazon's Best Sellers shows rank
        # numbers like "#1", "#2" inline; if we can find one, prefer it; else
        # use our own enumeration which mirrors the page order.
        rank_match = _RANK_RE.search(text[:30])  # rank usually appears early
        bsr = int(rank_match.group(1)) if rank_match else len(items) + 1

        # ── Title: usually the first prominent text. Try the link's accessible
        # name first (alt/title/aria-label/img-alt fallbacks).
        title = ""
        img = link.find("img")
        if img and img.get("alt"):
            title = img["alt"].strip()
        if not title:
            # Pull text from the card, skip rank/star strings which are short.
            for s in (card.stripped_strings if card else []):
                if len(s) > 15 and not _RATING_RE.search(s) and not s.startswith("#"):
                    title = s
                    break

        # ── Rating
        rating_match = _RATING_RE.search(text)
        rating = float(rating_match.group(1)) if rating_match else 0.0

        # ── Review count: usually the comma-formatted number that follows
        # the rating. Look for it within ~80 chars of the rating mention.
        review_count = 0
        if rating_match:
            tail = text[rating_match.end(): rating_match.end() + 80]
            rc_match = _REVIEWS_RE.search(tail)
            if rc_match:
                try:
                    review_count = int(rc_match.group(1).replace(",", ""))
                except ValueError:
                    review_count = 0

        # ── Price
        price = 0.0
        price_match = _PRICE_RE.search(text)
        if price_match:
            try:
                price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                price = 0.0

        # ── Image URL
        image = (img.get("src") if img else "") or ""

        items.append({
            "asin":              asin,
            "title":             title,
            "rating":            rating,
            "reviews_count":     review_count,
            "price":             price,
            "best_seller_rank":  bsr,
            "url":               f"https://www.amazon.com/dp/{asin}",
            "image":             image,
        })

    logger.info("Parsed %d unique products from Best Sellers > %s", len(items), category)
    return items


# ─── Filter + dedup helpers ──────────────────────────────────────────────────

def parse_item(item: dict, category: str) -> Candidate | None:
    """Convert one parsed item dict to a Candidate, or None if unparseable."""
    asin = (item.get("asin") or "").strip()
    if not asin or len(asin) != 10:
        return None
    title = (item.get("title") or "").strip()
    if not title:
        return None
    return Candidate(
        asin=asin,
        title=title,
        category=category,
        bsr=int(item.get("best_seller_rank") or 0),
        rating=float(item.get("rating") or 0),
        review_count=int(item.get("reviews_count") or 0),
        price=float(item.get("price") or 0),
        url=item.get("url") or f"https://www.amazon.com/dp/{asin}",
        image=item.get("image") or "",
        in_existing_catalog=False,
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


def load_existing_asins(csv_path: Path = EXISTING_CSV) -> set[str]:
    """Pull all ASINs already in `products/top-1000.csv`."""
    asins: set[str] = set()
    if not csv_path.exists():
        logger.warning("Catalog CSV not found: %s — every candidate will be 'new'", csv_path)
        return asins
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            url = row.get("Amazon URL") or ""
            m = _ASIN_RE.search(url)
            if m:
                asins.add(m.group(1))
    return asins


# ─── Dry-run fixture (no network) ────────────────────────────────────────────

# Same fixture data as before — the dry_run path doesn't need to mirror the
# new HTML pipeline since it's testing filter + dedup + output behaviors.
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
         "image": ""},   # rejected: invalid ASIN length (9 chars)
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
    min_rating: float,
    min_reviews: int,
    min_price: float,
    max_price: float,
    max_bsr: int,
    per_category: int,
    dry_run: bool,
) -> list[Candidate]:
    """Fetch + parse + filter + dedup all categories. Returns kept candidates."""
    existing_asins = load_existing_asins()
    logger.info("Existing catalog has %d ASINs (used for dedup)", len(existing_asins))

    seen_asins: set[str] = set()
    kept: list[Candidate] = []
    rejected_total = 0

    for human_name, slug in categories.items():
        logger.info("--- %s (%s) ---", human_name, slug)
        if dry_run:
            raw_items = _FIXTURE_RESPONSE.get(slug, [])
            logger.info("[dry-run] using %d fixture items", len(raw_items))
        else:
            html = fetch_bestsellers_html(slug)
            if html is None:
                logger.warning("Skipping %s — no HTML returned", human_name)
                continue
            raw_items = parse_bestsellers_html(html, human_name)

        # Take top-N before filter — bestseller pages return 50-100 cards;
        # we don't need them all. per_category bounds review effort.
        raw_items = raw_items[:per_category]

        for item in raw_items:
            cand = parse_item(item, human_name)
            if cand is None:
                continue
            if cand.asin in seen_asins:
                # Cross-category dedup: a single product can rank in multiple
                # bestseller lists (e.g., a Stanley cup in both Kitchen and Sports).
                continue
            if not apply_filters(cand, min_rating=min_rating, min_reviews=min_reviews,
                                 min_price=min_price, max_price=max_price, max_bsr=max_bsr):
                rejected_total += 1
                continue
            cand.in_existing_catalog = cand.asin in existing_asins
            seen_asins.add(cand.asin)
            kept.append(cand)

        if not dry_run:
            _polite_delay()  # don't hammer Amazon

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
                   help="Use built-in fixture data instead of fetching from Amazon. No network.")
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

    output_path = args.output or DEFAULT_OUTPUT_DIR / f"bestsellers-{date.today().isoformat()}.json"

    candidates = discover(
        categories   = cats,
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

    # Print a compact preview to the terminal.
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
