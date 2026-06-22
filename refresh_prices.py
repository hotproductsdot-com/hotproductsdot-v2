#!/usr/bin/env python3
"""
refresh_prices.py — Update live Amazon prices for all products in top-1000.csv.

For each product with a valid ASIN:
  - Fetches current price via Scrapling (TLS fingerprint impersonation)
  - If price changed: writes new price to "Price Range", old value to "Old Price"
  - Updates "Refreshed Date" on any changed row

Usage:
  python refresh_prices.py                   # update all products
  python refresh_prices.py --workers 4       # concurrent workers (default: 4)
  python refresh_prices.py --dry-run         # preview without writing
  python refresh_prices.py --delay 2.5       # per-request delay (default: 2.0s)
"""
from __future__ import annotations

import argparse
import csv
import logging
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup
from scrapling.fetchers import FetcherSession

CSV_PATH = Path(__file__).parent / "products" / "top-1000.csv"
ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")

# Ordered from most specific (buy-box scoped) to least specific.
# Do NOT put ".a-price .a-offscreen" first — it matches comparison carousels
# above the buy box and returns the wrong product's price.
PRICE_SELECTORS = [
    ".apex-pricetopay-value .a-offscreen",   # price-to-pay widget
    "#apex_offerDisplay_desktop .a-offscreen",  # offer display block
    "#corePrice_feature_div .a-offscreen",   # core price feature
    "#buybox .a-price .a-offscreen",         # buybox-scoped price
    "#priceblock_ourprice",                  # legacy selector
    "#price",                                # legacy selector
    ".a-price .a-offscreen",                 # last resort — broad, may mismatch
]

FIELDNAMES = [
    "Product Name", "Category", "Price Range", "Old Price",
    "Review Count", "Rating", "BSR", "Affiliate Potential",
    "Amazon URL", "Refreshed Date", "Action Needed",
]

log = logging.getLogger("refresh_prices")
_print_lock = threading.Lock()


def _log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def fetch_live_price(asin: str, delay: float) -> str:
    """Fetch current price for an ASIN. Returns price string, 'N/F', 'BLOCKED', or 'ERR:...'."""
    url = f"https://www.amazon.com/dp/{asin}"
    time.sleep(random.uniform(delay * 0.8, delay * 1.2))
    try:
        # FetcherSession is a context manager in scrapling 0.4.x — calling
        # .get() on the unentered object raises AttributeError.
        with FetcherSession() as session:
            resp = session.get(url, timeout=25, retries=1)
    except Exception as e:
        return f"ERR:{e}"

    if resp.status != 200:
        return f"HTTP {resp.status}"

    body = resp.body.decode(resp.encoding or "utf-8", errors="replace")
    if "Robot Check" in body or "Type the characters" in body:
        return "BLOCKED"

    soup = BeautifulSoup(body, "html.parser")
    for sel in PRICE_SELECTORS:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text:
                return text
    return "N/F"


def _parse_price_value(s: str) -> float | None:
    """Extract a float from a price string. Returns None if unparseable."""
    if not s:
        return None
    cleaned = re.sub(r"[^\d.]", "", s.split("-")[0].replace(",", ""))
    try:
        v = float(cleaned)
        return v if v > 0 else None
    except ValueError:
        return None


def prices_differ(stored: str, live: str) -> bool:
    """True if the live price is meaningfully different from the stored one."""
    sv = _parse_price_value(stored)
    lv = _parse_price_value(live)
    if sv is None or lv is None:
        # Can't compare numerically — treat as changed if text differs
        return stored.strip() != live.strip()
    if sv == 0:
        return lv != 0
    return abs(sv - lv) / max(sv, 1) > 0.02  # >2% threshold


def process_row(
    idx: int,
    total: int,
    row: dict[str, str],
    delay: float,
) -> tuple[dict[str, str], str]:
    """
    Process a single row. Returns (updated_row, status).
    status: 'updated' | 'unchanged' | 'skipped' | 'no_price' | 'blocked' | 'error'
    """
    url = row.get("Amazon URL", "")
    m = ASIN_RE.search(url)
    if not m:
        return row, "skipped"

    asin = m.group(1)
    stored_price = row.get("Price Range", "").strip()
    name = row.get("Product Name", "")[:55]

    live = fetch_live_price(asin, delay)

    if live == "BLOCKED":
        _log(f"  [{idx:>4}/{total}] BLOCKED           {asin}  {name}")
        return row, "blocked"
    if live.startswith("ERR") or live.startswith("HTTP"):
        _log(f"  [{idx:>4}/{total}] {live:<18} {asin}  {name}")
        return row, "error"
    if live == "N/F":
        _log(f"  [{idx:>4}/{total}] no price           {asin}  {name}")
        return row, "no_price"

    if not prices_differ(stored_price, live):
        _log(f"  [{idx:>4}/{total}] ok  {stored_price:<12}       {asin}  {name}")
        updated = {**row, "Old Price": row.get("Old Price", "")}
        return updated, "unchanged"

    today = f"{date.today().month}/{date.today().day}/{date.today().year}"
    updated = {
        **row,
        "Price Range": live,
        "Old Price": stored_price,
        "Refreshed Date": today,
    }
    _log(f"  [{idx:>4}/{total}] {stored_price:<12} → {live:<12} {asin}  {name}")
    return updated, "updated"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workers", type=int, default=4, help="Concurrent fetch workers (default: 4)")
    parser.add_argument("--delay",   type=float, default=2.0, help="Per-worker delay in seconds (default: 2.0)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing CSV")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,  # suppress Scrapling info noise
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found: {CSV_PATH}")
        return 1

    # utf-8-sig strips the BOM so DictReader's first key is "Product Name", not
    # "﻿Product Name" — the latter silently blanks every name on rewrite.
    rows = list(csv.DictReader(CSV_PATH.open(newline="", encoding="utf-8-sig")))
    total = len(rows)

    valid = [(i + 1, r) for i, r in enumerate(rows) if ASIN_RE.search(r.get("Amazon URL", ""))]
    skipped_no_asin = total - len(valid)

    print("=" * 70)
    print(f"  Amazon Price Refresh via Scrapling")
    print(f"  Products:  {total}  ({len(valid)} with ASIN, {skipped_no_asin} skipped)")
    print(f"  Workers:   {args.workers}  |  Delay: {args.delay}s  |  Dry-run: {args.dry_run}")
    est = int(len(valid) * args.delay / args.workers)
    print(f"  Est. time: ~{est // 60}m {est % 60}s")
    print("=" * 70)
    print(f"  {'#':>4}  {'Status/Old':>12}   {'New':>12}  ASIN          Product")
    print("-" * 70)

    results: dict[int, tuple[dict, str]] = {}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(process_row, idx, len(valid), row, args.delay): (orig_pos, row)
            for orig_pos, (idx, row) in enumerate(valid)
        }
        for fut in as_completed(futures):
            orig_pos, _ = futures[fut]
            updated_row, status = fut.result()
            results[orig_pos] = (updated_row, status)

    # Merge results back — preserve original order
    final_rows: list[dict[str, str]] = []
    no_asin_iter = (r for r in rows if not ASIN_RE.search(r.get("Amazon URL", "")))
    valid_map = {orig_pos: (updated_row, status) for orig_pos, (updated_row, status) in results.items()}

    # Reconstruct in original CSV order
    valid_idx = 0
    for i, row in enumerate(rows):
        if ASIN_RE.search(row.get("Amazon URL", "")):
            updated_row, _ = valid_map[valid_idx]
            final_rows.append(updated_row)
            valid_idx += 1
        else:
            final_rows.append({**row, "Old Price": row.get("Old Price", "")})

    # Stats
    statuses = [s for _, s in results.values()]
    n_updated   = statuses.count("updated")
    n_unchanged = statuses.count("unchanged")
    n_no_price  = statuses.count("no_price")
    n_blocked   = statuses.count("blocked")
    n_errors    = statuses.count("error")

    print("\n" + "=" * 70)
    print(f"  Updated:    {n_updated}")
    print(f"  Unchanged:  {n_unchanged}")
    print(f"  No price:   {n_no_price}")
    print(f"  Blocked:    {n_blocked}")
    print(f"  Errors:     {n_errors}")
    print(f"  No ASIN:    {skipped_no_asin}")
    print("=" * 70)

    if args.dry_run:
        print("\n  [DRY RUN] No changes written.")
        return 0

    # Write updated CSV. Derive fieldnames from the live data, NOT the module
    # FIELDNAMES (which is a stale schema) — this preserves the sale columns and
    # whatever columns the file actually carries.
    fieldnames = list(final_rows[0].keys()) if final_rows else list(FIELDNAMES)
    for row in final_rows:
        for k in row:
            if k not in fieldnames:
                fieldnames.append(k)
    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in final_rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"\n  CSV written: {CSV_PATH}")
    print(f"  {n_updated} prices updated, {n_unchanged} unchanged.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
