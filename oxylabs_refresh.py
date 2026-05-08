"""refresh_latest_picks.py — refresh price/rating/review_count for the
products shown on /latest (the 50 most recently IG-posted products).

Reads:
  marketing-campaigns/post_log.csv  (source of "latest" set, status=ok rows)
  products/top-1000.csv             (catalog with ASIN / Amazon URL)

Writes:
  products/top-1000.csv             (updates Price Range, Review Count,
                                     Rating, Refreshed Date for changed
                                     rows only)

Refresh source:
  Oxylabs Web Scraper API (source=amazon_product). Falls back to a no-op
  exit when OXYLABS_USERNAME/OXYLABS_PASSWORD are absent. Never aborts
  the caller — failures are logged and the workflow continues.

Tolerance gate (keeps the daily diff small):
  price        ± 2%
  rating       ± 0.1
  review_count ± 5%

Usage:
  python refresh_latest_picks.py [--limit 50] [--concurrency 5] [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests

REPO = Path(__file__).parent
LOG_PATH = REPO / "marketing-campaigns" / "post_log.csv"
CSV_PATH = REPO / "products" / "top-1000.csv"
OXY_ENDPOINT = "https://realtime.oxylabs.io/v1/queries"
ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")
# Price drifts larger than this are treated as suspicious (wrong variant, geo
# pricing, flash sale badge) and skipped rather than written to the catalog.
MAX_PRICE_DRIFT = 0.25

logger = logging.getLogger("refresh_latest")


@dataclass
class Refresh:
    name: str
    asin: str
    price: float | None = None
    rating: float | None = None
    reviews: int | None = None
    available: bool | None = None
    error: str | None = None
    # Diagnostic snapshot of fields _parse_availability inspected. Populated
    # by fetch_oxylabs so callers can audit why `available` came back None.
    signals: dict | None = None


def latest_picks(limit: int) -> list[str]:
    """Return up to `limit` distinct, most-recently-posted product names.
    Only status=ok rows count — quality_blocked / error rows are excluded."""
    if not LOG_PATH.exists():
        return []
    with LOG_PATH.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    seen: list[str] = []
    seen_set: set[str] = set()
    for row in reversed(rows):
        if row.get("Status") != "ok":
            continue
        name = (row.get("Product") or "").strip()
        if not name or name in seen_set:
            continue
        seen.append(name)
        seen_set.add(name)
        if len(seen) >= limit:
            break
    return seen


def extract_asin(amazon_url: str) -> str | None:
    m = ASIN_RE.search(amazon_url or "")
    return m.group(1) if m else None


def _to_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def fetch_oxylabs(asin: str, *, username: str, password: str) -> Refresh:
    """Fetch a single product via Oxylabs amazon_product. Never raises;
    populates the .error field on failure."""
    payload = {
        "source": "amazon_product",
        "query": asin,
        "domain": "com",
        "geo_location": "90210",
        "parse": True,
    }
    r = Refresh(name="", asin=asin)
    try:
        resp = requests.post(
            OXY_ENDPOINT,
            json=payload,
            auth=(username, password),
            timeout=60,
        )
        if resp.status_code != 200:
            r.error = f"HTTP {resp.status_code}"
            return r
        results = resp.json().get("results") or []
        if not results:
            r.error = "empty results"
            return r
        content = results[0].get("content") or {}
        # The amazon_product schema exposes price/rating/reviews_count
        # (sometimes nested). Try the canonical field first; fall back
        # to common variants without raising.
        price = content.get("price") or (content.get("pricing") or {}).get("current_price")
        rating = content.get("rating")
        reviews = (
            content.get("reviews_count")
            or content.get("reviews")
            or (content.get("rating_stars_distribution") or {}).get("total_count")
        )
        r.price = _to_float(price)
        r.rating = _to_float(rating)
        r.reviews = _to_int(reviews)
        r.available = _parse_availability(content)
        # Capture only the fields _parse_availability looked at, so the audit
        # log stays small and never leaks the full Oxylabs payload.
        r.signals = {
            "is_in_stock": content.get("is_in_stock"),
            "availability": content.get("availability"),
            "stock": content.get("stock"),
            "has_price": price is not None,
        }
    except Exception as exc:
        r.error = str(exc)[:120]
    return r


_UNAVAILABLE_RE = re.compile(
    r"(currently\s+unavailable|out\s+of\s+stock|unavailable|sold\s+out|cannot\s+be\s+shipped)",
    re.IGNORECASE,
)


def _parse_availability(content: dict) -> bool | None:
    """Best-effort availability parse from Oxylabs amazon_product content.

    Returns True (in stock), False (explicit unavailable), or None (unknown).
    """
    flag = content.get("is_in_stock")
    if isinstance(flag, bool):
        return flag

    text = content.get("availability") or content.get("stock") or ""
    if isinstance(text, dict):
        text = text.get("status") or text.get("text") or ""
    if isinstance(text, str) and text.strip():
        if _UNAVAILABLE_RE.search(text):
            return False
        return True

    return None


def changed(old: dict, new: Refresh) -> bool:
    """True iff at least one field crosses its tolerance threshold."""
    old_price = _to_float(old.get("Price Range"))
    if new.price is not None:
        if old_price is None:
            return True
        if abs(new.price - old_price) / max(old_price, 0.01) > 0.02:
            return True

    old_rating = _to_float(old.get("Rating"))
    if new.rating is not None:
        if old_rating is None:
            return True
        if abs(new.rating - old_rating) > 0.1:
            return True

    old_reviews = _to_int(old.get("Review Count"))
    if new.reviews is not None:
        if old_reviews is None:
            return True
        if abs(new.reviews - old_reviews) / max(old_reviews, 1) > 0.05:
            return True

    return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    user = os.environ.get("OXYLABS_USERNAME", "")
    pw = os.environ.get("OXYLABS_PASSWORD", "")
    if not (user and pw):
        logger.warning("OXYLABS_USERNAME/PASSWORD not set — skipping refresh (no-op exit 0)")
        return 0

    targets = latest_picks(args.limit)
    if not targets:
        logger.info("No latest picks to refresh")
        return 0
    logger.info("Refreshing %d products from /latest", len(targets))

    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    by_name = {r["Product Name"]: r for r in rows}

    work: list[tuple[str, str]] = []
    for name in targets:
        row = by_name.get(name)
        if not row:
            logger.warning("Not in catalog: %s", name[:60])
            continue
        asin = extract_asin(row.get("Amazon URL", ""))
        if not asin:
            logger.warning("No ASIN: %s", name[:60])
            continue
        work.append((name, asin))

    if not work:
        return 0

    refreshes: dict[str, Refresh] = {}
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {
            ex.submit(fetch_oxylabs, asin, username=user, password=pw): name
            for name, asin in work
        }
        for fut in as_completed(futs):
            name = futs[fut]
            r = fut.result()
            r.name = name
            refreshes[name] = r

    today = date.today().isoformat()
    updates = 0
    errors = 0
    for name, new in refreshes.items():
        if new.error:
            errors += 1
            logger.warning("%-60s [%s]", name[:60], new.error)
            continue
        row = by_name[name]
        if not changed(row, new):
            continue
        if new.price is not None:
            old_price = _to_float(row.get("Price Range"))
            if old_price and old_price > 0:
                drift = abs(new.price - old_price) / old_price
                if drift > MAX_PRICE_DRIFT:
                    pct = (new.price - old_price) / old_price * 100
                    logger.warning(
                        "SKIPPED price update for %-60s: "
                        "CSV=$%.2f Oxylabs=$%.2f (%+.1f%%) exceeds %d%% ceiling",
                        name[:60], old_price, new.price, pct, int(MAX_PRICE_DRIFT * 100),
                    )
                    new.price = None  # don't write, but still update rating/reviews
            if new.price is not None:
                row["Price Range"] = f"{new.price:.2f}"
        if new.rating is not None:
            row["Rating"] = f"{new.rating:.1f}"
        if new.reviews is not None:
            row["Review Count"] = str(new.reviews)
        row["Refreshed Date"] = today
        updates += 1
        logger.info(
            "UPDATED %-60s price=%s rating=%s reviews=%s",
            name[:60], new.price, new.rating, new.reviews,
        )

    logger.info(
        "Refresh result: %d updated, %d errors, %d unchanged (of %d fetched)",
        updates, errors, len(refreshes) - updates - errors, len(refreshes),
    )

    if args.dry_run:
        logger.info("--dry-run: not writing CSV")
        return 0

    if updates == 0:
        logger.info("No changes above tolerance threshold; CSV untouched")
        return 0

    tmp = CSV_PATH.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(CSV_PATH)
    logger.info("Wrote %s", CSV_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
