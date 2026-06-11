#!/usr/bin/env python3
"""refresh_catalog_local.py — full catalog refresh via the LOCAL scraper.

Drop-in replacement for oxylabs-amazon-product.sh: pulls live price /
rating / review count for every product in products/top-1000.csv using
amazon_local_api (free, no API key) and merges changes back.

Behavior mirrors the Oxylabs script:
  * Dated backup of top-1000.csv before any write
  * Field-level differences appended to products/products4review.csv
  * Dead / unavailable listings appended to products/broken-links.csv
  * Tolerance gates keep the daily diff small (price ±2%, rating ±0.1,
    reviews ±5%); price drift >25% is treated as suspicious and skipped
  * "Refreshed Date" (M/D/YYYY) is set on every successfully checked row

Usage:
  venv/bin/python refresh_catalog_local.py [--limit N] [--offset N]
                                           [--workers 4] [--delay 2.0]
                                           [--dry-run]

Exit code 0 only when every processed ASIN reached a definitive verdict
(data parsed, or listing definitively gone/unavailable).
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from amazon_local_api import ProductData, fetch_product

REPO = Path(__file__).parent
CSV_PATH = REPO / "products" / "top-1000.csv"
REVIEW_PATH = REPO / "products" / "products4review.csv"
BROKEN_PATH = REPO / "products" / "broken-links.csv"

ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})", re.IGNORECASE)

PRICE_TOLERANCE = 0.02    # ignore price moves smaller than ±2%
RATING_TOLERANCE = 0.1    # ignore rating moves smaller than ±0.1
REVIEWS_TOLERANCE = 0.05  # ignore review-count moves smaller than ±5%
MAX_PRICE_DRIFT = 0.25    # >25% move = suspicious (wrong variant/geo) — skip

_print_lock = threading.Lock()


def _log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def extract_asin(url: str) -> str | None:
    m = ASIN_RE.search(url or "")
    return m.group(1).upper() if m else None


def _to_float(v) -> float | None:
    try:
        cleaned = re.sub(r"[^\d.]", "", str(v).split("-")[0].replace(",", ""))
        return float(cleaned) if cleaned else None
    except (TypeError, ValueError):
        return None


def _to_int(v) -> int | None:
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class UpdateDecision:
    """Which CSV fields should change for one row, plus audit info."""
    fields: dict = field(default_factory=dict)        # column -> new value
    diffs: tuple = ()                                 # (field, old, new) rows
    suspicious_price: bool = False


def decide_update(row: dict, live: ProductData) -> UpdateDecision:
    """Pure decision: compare a CSV row to live data. Never mutates `row`."""
    fields: dict = {}
    diffs: list = []
    suspicious = False

    # Sanity bounds: a parse glitch can hand us swapped fields (rating in
    # the price slot, review count in the rating slot — the 2026-06-10
    # AirPods Max corruption wrote rating=16685 / price=$4.60 to the
    # catalog and it shipped on a banner). Out-of-domain values are
    # discarded here so they can never reach the CSV.
    if live.rating is not None and not (0.0 < live.rating <= 5.0):
        live = dataclasses.replace(live, rating=None)
    if live.reviews_count is not None and live.reviews_count < 0:
        live = dataclasses.replace(live, reviews_count=None)
    if live.price is not None and live.price <= 0:
        live = dataclasses.replace(live, price=None)

    old_price = _to_float(row.get("Price Range"))
    if live.price is not None:
        if old_price is None:
            fields["Price Range"] = f"{live.price:.2f}"
            diffs.append(("Price", row.get("Price Range", ""), f"{live.price:.2f}"))
        elif abs(live.price - old_price) / max(old_price, 0.01) > PRICE_TOLERANCE:
            drift = abs(live.price - old_price) / max(old_price, 0.01)
            if drift > MAX_PRICE_DRIFT:
                suspicious = True
            else:
                fields["Price Range"] = f"{live.price:.2f}"
                diffs.append(("Price", f"{old_price:.2f}", f"{live.price:.2f}"))

    old_rating = _to_float(row.get("Rating"))
    if live.rating is not None:
        if old_rating is None or abs(live.rating - old_rating) > RATING_TOLERANCE:
            fields["Rating"] = f"{live.rating:.1f}"
            diffs.append(("Rating", row.get("Rating", ""), f"{live.rating:.1f}"))

    old_reviews = _to_int(row.get("Review Count"))
    if live.reviews_count is not None:
        if old_reviews is None or abs(live.reviews_count - old_reviews) / max(old_reviews, 1) > REVIEWS_TOLERANCE:
            fields["Review Count"] = str(live.reviews_count)
            diffs.append(("Review Count", row.get("Review Count", ""), str(live.reviews_count)))

    return UpdateDecision(fields=fields, diffs=tuple(diffs), suspicious_price=suspicious)


def _backup_csv() -> Path:
    stamp = date.today().isoformat()
    backup = CSV_PATH.with_name(f"top-1000.backup.{stamp}.csv")
    if backup.exists():
        backup = CSV_PATH.with_name(f"top-1000.backup.{stamp}_{time.strftime('%H%M%S')}.csv")
    backup.write_bytes(CSV_PATH.read_bytes())
    return backup


def _append_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if f.tell() == 0:  # atomic with the open — no exists() TOCTOU race
            writer.writerow(header)
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=0, help="Only process N products (0 = all)")
    parser.add_argument("--offset", type=int, default=0, help="Skip the first N products")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers (default 4)")
    parser.add_argument("--delay", type=float, default=2.0, help="Per-request delay seconds (default 2.0)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if not CSV_PATH.exists():
        print(f"ERROR: catalog not found: {CSV_PATH}")
        return 1

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    end = args.offset + args.limit if args.limit > 0 else len(rows)
    work: list[tuple[int, str]] = []  # (row index, asin)
    for i in range(args.offset, min(end, len(rows))):
        asin = extract_asin(rows[i].get("Amazon URL", ""))
        if asin:
            work.append((i, asin))

    total = len(work)
    print("=" * 72)
    print("  LOCAL Amazon catalog refresh (no API cost)")
    print(f"  Products: {total}  |  Workers: {args.workers}  |  Delay: {args.delay}s  |  Dry-run: {args.dry_run}")
    print("=" * 72)
    if not total:
        print("Nothing to do.")
        return 0

    if not args.dry_run:
        backup = _backup_csv()
        print(f"  Backup: {backup.name}")

    done = 0

    # Workers never touch `rows` — the product name is captured at submit
    # time and all catalog writes happen after the pool is fully drained.
    def job(idx: int, asin: str, name: str) -> tuple[int, ProductData]:
        nonlocal done
        time.sleep(random.uniform(args.delay * 0.8, args.delay * 1.4))
        product = fetch_product(asin, base_delay=max(args.delay, 1.0))
        with _print_lock:
            done += 1
            n = done
        if product.page_status == "ok":
            _log(f"  [{n:>4}/{total}] {asin}  ${product.price!s:<9} ★{product.rating!s:<4} "
                 f"({product.reviews_count!s:>7} rev)  {name}")
        else:
            _log(f"  [{n:>4}/{total}] {asin}  !! {product.page_status}: {product.error or ''}  {name}")
        return idx, product

    results: dict[int, ProductData] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(job, idx, asin, rows[idx].get("Product Name", "")[:48])
            for idx, asin in work
        ]
        for fut in as_completed(futures):
            idx, product = fut.result()
            results[idx] = product

    _now = date.today()
    today = f"{_now.month}/{_now.day}/{_now.year}"
    review_rows: list[list[str]] = []
    broken_rows: list[list[str]] = []
    updated = suspicious = unavailable = failed = unchanged = 0

    for idx, live in sorted(results.items()):
        row = rows[idx]
        name = row.get("Product Name", "")
        no_offer = (live.page_status == "ok" and live.price is None
                    and live.availability == "See All Buying Options")
        if live.page_status == "not_found" or no_offer or (
                live.page_status == "ok" and live.is_in_stock is False):
            unavailable += 1
            reason = ("listing_removed" if live.page_status == "not_found"
                      else "no_buybox_offer" if no_offer else "unavailable")
            broken_rows.append([live.asin, name, row.get("Amazon URL", ""), live.page_status,
                                reason, live.title or "", str(live.price or ""), live.availability or ""])
            continue
        if live.page_status != "ok":
            failed += 1
            continue

        decision = decide_update(row, live)
        if decision.suspicious_price:
            # Unverified price: send to the review file and leave the row
            # completely untouched — stamping Refreshed Date here would mark
            # a stale price as freshly verified.
            suspicious += 1
            _log(f"  SUSPICIOUS price skipped {live.asin}: CSV={row.get('Price Range')} live={live.price}")
            review_rows.append([live.asin, name, "Price (SUSPICIOUS >25% drift)",
                                str(row.get("Price Range", "")), f"{live.price:.2f}"])
            continue
        for fname, old, new in decision.diffs:
            review_rows.append([live.asin, name, fname, old, new])
        if decision.fields:
            rows[idx] = {**row, **decision.fields, "Refreshed Date": today}
            updated += 1
        else:
            rows[idx] = {**row, "Refreshed Date": today}
            unchanged += 1

    print("\n" + "=" * 72)
    print(f"  Updated: {updated}   Unchanged: {unchanged}   Unavailable/removed: {unavailable}")
    print(f"  Suspicious price (skipped): {suspicious}   Hard failures: {failed}")
    rate = 100.0 * (total - failed) / total if total else 100.0
    print(f"  Definitive-verdict success rate: {rate:.1f}% ({total - failed}/{total})")
    print("=" * 72)

    if args.dry_run:
        print("\n  [DRY RUN] No files written.")
        return 0 if failed == 0 else 1

    if review_rows:
        _append_csv(REVIEW_PATH, ["ASIN", "Product Name", "Field", "CSV Value", "Live Value"], review_rows)
        print(f"  Differences logged: {REVIEW_PATH.name} ({len(review_rows)} rows)")
    if broken_rows:
        _append_csv(BROKEN_PATH, ["ASIN", "Product Name", "Amazon URL", "HTTP Status",
                                  "Reason", "Title", "Price", "Availability"], broken_rows)
        print(f"  Broken/unavailable logged: {BROKEN_PATH.name} ({len(broken_rows)} rows)")

    tmp = CSV_PATH.with_suffix(".csv.tmp")
    # utf-8-sig preserves the BOM the catalog is read with (Excel-friendly).
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(CSV_PATH)
    print(f"  Catalog written: {CSV_PATH.name}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
