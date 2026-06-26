#!/usr/bin/env python3
"""fetch_daily_deals.py — daily "Limited Time Sale" batch (top 25 on-sale products).

Pipeline (hybrid discover/verify, run by cron at 8am Central — see
run_daily_deals.sh):

  1. DISCOVER  Scrape Amazon Best Sellers pages (reuses find_bestsellers.py's
               fetch/parse functions — free, no credentials).
  2. VERIFY    amazon_local_api.fetch_product per candidate ASIN (free local
               scraper, capped by --max-verify) to get the real current price,
               strikethrough list price, and "N+ bought in past month" badge.
  3. RANK      deal_score = sales_velocity × discount%. Sales velocity is the
               "bought in past month" badge number; products without a badge
               fall back to review_count / 10 (cumulative-sales proxy).
  4. SWAP      products/top-1000.csv: delete yesterday's rows flagged
               Temporary=daily-deal, clear deal columns on permanent rows,
               then write today's top 25 (new rows, or deal columns on an
               existing permanent row when the ASIN is already in the catalog).
  5. IMAGES    Download product JPGs into site/public/products/ for any new
               slug (same job autofix-images.js does for manual adds).

Consumers of the deal columns:
  - post_daily.py     posts exclusively from fresh deal rows (top 5 by score).
  - site/prebuild.js + site/app/lib/products.ts render the homepage
    "Limited Time Sale" section.

New CSV columns (appended; absent/empty on permanent rows):
  Temporary, Deal Date, List Price, Discount %, Bought Past Month

Usage:
  python fetch_daily_deals.py [--max-verify 60] [--min-discount 10]
                              [--deal-count 25] [--dry-run] [-v]

Env: AMAZON_ASSOCIATE_TAG (default hotproduct033-20). No paid credentials —
     verification uses the free local scraper (amazon_local_api).

Exit codes: 0 = catalog updated · 2 = no qualifying deals (catalog untouched)
            1 = fatal error
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import requests

import find_bestsellers as fb
from amazon_local_api import fetch_product

logger = logging.getLogger("daily_deals")

REPO_ROOT = Path(__file__).resolve().parent
CSV_PATH = REPO_ROOT / "products" / "top-1000.csv"
IMAGE_DIR = REPO_ROOT / "site" / "public" / "products"
AUDIT_DIR = REPO_ROOT / "products" / "discovery"

# Local scraper has a process-wide 1.5s request throttle, so wide concurrency
# buys nothing and only raises Amazon's block risk — keep it modest.
VERIFY_CONCURRENCY = 4

DEAL_FLAG = "daily-deal"
DEAL_COLUMNS = ("Temporary", "Deal Date", "List Price", "Discount %", "Bought Past Month")

# Looser than find_bestsellers DEFAULTS: deals trade a little review depth for
# discount freshness, but the rating floor stays at post_daily's 4.5 cutoff so
# every deal row is postable.
DISCOVER_FILTERS = {
    "min_rating": 4.5,
    "min_reviews": 500,
    "min_price": 15.0,
    "max_price": 500.0,
    "max_bsr": 100,
}

IMAGE_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_SALES_VOLUME_RE = re.compile(
    r"([\d.]+)\s*([KkMm]?)\s*\+?\s*bought", re.IGNORECASE
)


@dataclass(frozen=True)
class Deal:
    """One verified on-sale product, ready for the catalog."""
    asin: str
    title: str
    category: str
    price: float
    list_price: float
    discount_pct: int
    bought_past_month: int
    rating: float
    review_count: int
    bsr: int
    image: str
    deal_score: float


# ─── .env / credentials ──────────────────────────────────────────────────────

def load_dotenv_if_needed(path: Path = REPO_ROOT / ".env") -> None:
    """Populate os.environ from .env for vars not already exported."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# ─── Parsing helpers ─────────────────────────────────────────────────────────

def parse_sales_volume(raw: object) -> int:
    """'10K+ bought in past month' → 10000; '400+ bought…' → 400; else 0."""
    if not isinstance(raw, str):
        return 0
    m = _SALES_VOLUME_RE.search(raw)
    if not m:
        return 0
    try:
        num = float(m.group(1))
    except ValueError:
        return 0
    unit = m.group(2).lower()
    if unit == "k":
        num *= 1_000
    elif unit == "m":
        num *= 1_000_000
    return int(num)


def compute_discount_pct(price: float, list_price: float) -> int:
    """Whole-percent discount; 0 when there is no real markdown."""
    if price <= 0 or list_price <= price:
        return 0
    return round((list_price - price) / list_price * 100)


def deal_score(bought_past_month: int, review_count: int, discount_pct: int) -> float:
    """Sales-velocity × discount. Badge number when present, else reviews/10."""
    velocity = bought_past_month if bought_past_month > 0 else max(review_count, 1) / 10
    return velocity * discount_pct


def truncate_title(title: str, limit: int = 70) -> str:
    """Trim Amazon's keyword-stuffed titles at a word boundary."""
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) <= limit:
        return title
    cut = title[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:- ")


def slugify(text: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", text.lower()))


def affiliate_url(asin: str) -> str:
    tag = os.environ.get("AMAZON_ASSOCIATE_TAG", "hotproduct033-20")
    return f"https://www.amazon.com/dp/{asin}?tag={tag}"


# ─── Phase 1: discover candidates ────────────────────────────────────────────

def discover_candidates(categories: dict[str, str]) -> list[dict]:
    """Scrape Best Sellers pages and return raw item dicts that pass the
    light pre-filter. Free; failures per category are logged and skipped."""
    candidates: list[dict] = []
    seen: set[str] = set()
    for category, slug in categories.items():
        html = fb.fetch_bestsellers_html(slug)
        if not html:
            continue
        for item in fb.parse_bestsellers_html(html, category):
            cand = fb.parse_item(item, category)
            if cand is None or cand.asin in seen:
                continue
            # Price can be 0 on grid pages — the verify pass re-fetches it
            # later, so only enforce the price band when the scrape produced one.
            price_ok = cand.price == 0 or (
                DISCOVER_FILTERS["min_price"] <= cand.price <= DISCOVER_FILTERS["max_price"]
            )
            if (
                cand.rating >= DISCOVER_FILTERS["min_rating"]
                and cand.review_count >= DISCOVER_FILTERS["min_reviews"]
                and price_ok
                and cand.bsr <= DISCOVER_FILTERS["max_bsr"]
            ):
                seen.add(cand.asin)
                candidates.append({**item, "category": category})
        fb._polite_delay()
    logger.info("Discovery: %d candidates across %d categories", len(candidates), len(categories))
    return candidates


# ─── Phase 2: verify via the local Amazon scraper (free) ─────────────────────

def verify_deal(candidate: dict, *, min_discount: int) -> Deal | None:
    """Confirm a candidate is genuinely on sale via amazon_local_api (free,
    no paid API). Returns None when not on sale or the page didn't parse."""
    asin = candidate["asin"]
    product = fetch_product(asin)
    # Only a cleanly parsed product page can be a deal — listing_removed /
    # blocked / unavailable verdicts carry no usable price.
    if product.page_status != "ok" or product.price is None:
        return None

    price = float(product.price or 0)
    list_price = float(product.list_price or 0)
    discount = compute_discount_pct(price, list_price)
    if discount < min_discount:
        return None
    if not (DISCOVER_FILTERS["min_price"] <= price <= DISCOVER_FILTERS["max_price"]):
        return None
    if product.is_in_stock is False:
        return None

    try:
        rating = float(product.rating or candidate.get("rating") or 0)
    except (TypeError, ValueError):
        rating = float(candidate.get("rating") or 0)
    if rating < DISCOVER_FILTERS["min_rating"]:
        return None

    try:
        reviews = int(product.reviews_count or candidate.get("reviews_count") or 0)
    except (TypeError, ValueError):
        reviews = int(candidate.get("reviews_count") or 0)
    if reviews < DISCOVER_FILTERS["min_reviews"]:
        return None

    bought = int(product.bought_past_month or 0)
    title = truncate_title(str(product.title or candidate.get("title") or ""))
    if not title:
        return None

    # The scraper doesn't capture gallery images; reuse the Best Sellers grid
    # thumbnail the discovery pass already collected.
    image = str(candidate.get("image") or "")

    return Deal(
        asin=asin,
        title=title,
        category=str(candidate.get("category") or "Electronics"),
        price=round(price, 2),
        list_price=round(list_price, 2),
        discount_pct=discount,
        bought_past_month=bought,
        rating=rating,
        review_count=reviews,
        bsr=int(candidate.get("best_seller_rank") or 0),
        image=image,
        deal_score=deal_score(bought, reviews, discount),
    )


def verify_candidates(
    candidates: list[dict], *, max_verify: int, min_discount: int,
) -> list[Deal]:
    """Verify up to max_verify candidates concurrently; ranked best-first."""
    batch = candidates[:max_verify]
    deals: list[Deal] = []
    with ThreadPoolExecutor(max_workers=VERIFY_CONCURRENCY) as pool:
        futures = {
            pool.submit(verify_deal, c, min_discount=min_discount): c["asin"]
            for c in batch
        }
        for fut in as_completed(futures):
            deal = fut.result()
            if deal is not None:
                logger.info(
                    "DEAL %s: -%d%% ($%.2f from $%.2f), %s bought/mo, score=%.0f — %s",
                    deal.asin, deal.discount_pct, deal.price, deal.list_price,
                    deal.bought_past_month or "n/a", deal.deal_score, deal.title,
                )
                deals.append(deal)
    deals.sort(key=lambda d: d.deal_score, reverse=True)
    logger.info("Verification: %d/%d candidates are on sale ≥ threshold", len(deals), len(batch))
    return deals


# ─── Phase 3: swap deal rows in the catalog CSV ──────────────────────────────

def merge_deals_into_rows(
    rows: list[dict], fieldnames: list[str], deals: list[Deal], today_iso: str,
) -> tuple[list[dict], list[str]]:
    """Pure merge: drop old Temporary rows, clear deal columns on permanent
    rows, then apply today's deals. Returns (new_rows, new_fieldnames)."""
    out_fields = list(fieldnames)
    for col in DEAL_COLUMNS:
        if col not in out_fields:
            out_fields.append(col)

    kept: list[dict] = []
    by_asin: dict[str, dict] = {}
    asin_re = re.compile(r"/dp/([A-Z0-9]{10})", re.IGNORECASE)
    for row in rows:
        if (row.get("Temporary") or "").strip() == DEAL_FLAG:
            continue  # yesterday's batch — swapped out
        cleared = {**row, **{col: "" for col in DEAL_COLUMNS}}
        kept.append(cleared)
        m = asin_re.search(cleared.get("Amazon URL") or "")
        if m:
            by_asin[m.group(1).upper()] = cleared

    us_today = f"{int(today_iso[5:7])}/{int(today_iso[8:10])}/{today_iso[:4]}"
    result = list(kept)
    for deal in deals:
        deal_cols = {
            "Temporary": "",  # permanent rows keep their place in the catalog
            "Deal Date": today_iso,
            "List Price": f"{deal.list_price:.2f}",
            "Discount %": str(deal.discount_pct),
            "Bought Past Month": str(deal.bought_past_month),
        }
        existing = by_asin.get(deal.asin.upper())
        if existing is not None:
            # Already a permanent catalog product: refresh price + deal columns
            # in place instead of duplicating the row.
            existing.update(deal_cols)
            existing["Price Range"] = f"{deal.price:.2f}"
            existing["Refreshed Date"] = us_today
            continue
        result.append({
            **{name: "" for name in out_fields},
            "Product Name": deal.title,
            "Category": deal.category,
            "Price Range": f"{deal.price:.2f}",
            "Review Count": str(deal.review_count),
            "Rating": f"{deal.rating:g}",
            "BSR": f"#{deal.bsr}" if deal.bsr else "",
            "Affiliate Potential": "8",
            "Amazon URL": affiliate_url(deal.asin),
            "Refreshed Date": us_today,
            "Action Needed": "",
            **deal_cols,
            "Temporary": DEAL_FLAG,
        })
    return result, out_fields


def write_catalog(rows: list[dict], fieldnames: list[str], csv_path: Path = CSV_PATH) -> None:
    """Atomic utf-8-sig rewrite, matching the other catalog writers."""
    fd, tmp_path = tempfile.mkstemp(suffix=".csv", dir=str(csv_path.parent))
    os.close(fd)
    try:
        with open(tmp_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, csv_path)
    except OSError:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ─── Phase 4: product images ─────────────────────────────────────────────────

def download_images(deals: list[Deal], image_dir: Path = IMAGE_DIR) -> int:
    """Fetch <slug>.jpg for deals missing a local image (autofix-images.js
    equivalent for the cron path — no Node dependency). Best-effort."""
    image_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for deal in deals:
        slug = slugify(deal.title)
        target = image_dir / f"{slug}.jpg"
        if target.exists():
            continue
        url = deal.image or f"https://m.media-amazon.com/images/P/{deal.asin}.01._SCLZZZZZZZ_SX500_.jpg"
        try:
            resp = requests.get(url, headers={"User-Agent": IMAGE_UA}, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 2_000:
                target.write_bytes(resp.content)
                downloaded += 1
            else:
                logger.warning("Image fetch failed for %s (HTTP %s, %d bytes)",
                               slug, resp.status_code, len(resp.content))
        except Exception as exc:
            logger.warning("Image fetch error for %s: %s", slug, str(exc)[:120])
    return downloaded


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch today's top on-sale products into the catalog")
    parser.add_argument("--deal-count", type=int, default=25, metavar="N",
                        help="How many deals to keep (default: 25)")
    parser.add_argument("--max-verify", type=int, default=60, metavar="N",
                        help="Max candidates to scrape-verify locally (free, default: 60)")
    parser.add_argument("--min-discount", type=int, default=10, metavar="PCT",
                        help="Minimum discount %% to qualify as a deal (default: 10)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Discover + verify + rank, but do not touch the CSV or images")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # .env still loaded for AMAZON_ASSOCIATE_TAG; no paid credentials needed.
    load_dotenv_if_needed()

    today_iso = date.today().isoformat()

    candidates = discover_candidates(fb.CATEGORIES)
    if not candidates:
        logger.error("Discovery produced 0 candidates — Amazon may be blocking; aborting without CSV changes")
        return 2

    # Verify cheapest-signal-first: page-rank order already favors movers.
    deals = verify_candidates(
        candidates, max_verify=args.max_verify, min_discount=args.min_discount,
    )[: args.deal_count]
    if not deals:
        logger.error("0 qualifying deals after verification — catalog untouched")
        return 2

    if args.dry_run:
        for i, deal in enumerate(deals, 1):
            print(f"{i:2d}. -{deal.discount_pct}%  ${deal.price:.2f}  "
                  f"(was ${deal.list_price:.2f})  score={deal.deal_score:.0f}  {deal.title}")
        return 0

    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    new_rows, new_fields = merge_deals_into_rows(rows, fieldnames, deals, today_iso)
    write_catalog(new_rows, new_fields)
    logger.info("Catalog updated: %d deals for %s (%d rows total)", len(deals), today_iso, len(new_rows))

    downloaded = download_images(deals)
    logger.info("Images: %d downloaded", downloaded)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = AUDIT_DIR / f"daily-deals-{today_iso}.json"
    audit_path.write_text(
        json.dumps([asdict(d) for d in deals], indent=2), encoding="utf-8"
    )
    logger.info("Audit written: %s", audit_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
