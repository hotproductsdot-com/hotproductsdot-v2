#!/usr/bin/env python3
"""
fix_amazon_urls.py - Resolve search-only Amazon URLs to direct /dp/ASIN links.

Many legacy products in products/top-1000.csv have Amazon URLs in the form:
    https://www.amazon.com/s?k=Product+Name&tag=hotproduct033-20

This script finds those rows, searches Amazon for the product name, extracts
the best matching ASIN, and replaces the URL with a direct /dp/ link.

Default mode is direct scraping (no third-party API). Optional --rainforest
uses Rainforest API when you have quota; if that quota is exhausted, omit
--rainforest and use direct mode — possibly smaller --limit and longer
--delay-min/--delay-max if Amazon returns 503 often.

Rainforest API key (only with --rainforest):
    Copy .env.example to .env and set RAINFOREST_API_KEY=your_key_here
    Or export the variable: set RAINFOREST_API_KEY=your_key_here  (Windows)
                            export RAINFOREST_API_KEY=your_key_here (Mac/Linux)

Usage:
    python fix_amazon_urls.py --audit               # Count problems, no scraping
    python fix_amazon_urls.py                       # Dry run — preview changes
    python fix_amazon_urls.py --apply               # Write fixes (direct scraping)
    python fix_amazon_urls.py --apply --limit 50    # Direct scraping, 50 per run
    python fix_amazon_urls.py --apply --delay-min 8 --delay-max 15  # Slower, gentler
    python fix_amazon_urls.py --apply --update-prices  # Also set Price Range from listing (when found)
    python fix_amazon_urls.py --apply --rainforest  # Rainforest (needs API quota)
    python fix_amazon_urls.py --apply --rainforest --limit 200
"""
from __future__ import annotations

import argparse
import csv
import random
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import os
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# .env loader — reads .env from the project root (no extra deps needed)
# ---------------------------------------------------------------------------
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CSV_PATH      = Path("products/top-1000.csv")
AFFILIATE_TAG = "hotproduct033-20"
MAX_RETRIES   = 3
DELAY_MIN     = 3.0   # seconds between requests (direct scraping only)
DELAY_MAX     = 6.0
MATCH_THRESHOLD = 0.40  # min word-overlap ratio to accept a search result as correct

# Rainforest API — loaded from .env or environment variable
RAINFOREST_API_KEY = os.environ.get("RAINFOREST_API_KEY", "")
RAINFOREST_BASE    = "https://api.rainforestapi.com/request"

FIELDNAMES = [
    "Product Name", "Category", "Price Range", "Review Count",
    "Rating", "BSR", "Affiliate Potential", "Amazon URL",
    "Refreshed Date", "Action Needed",
]

USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def _fetch(url: str) -> Optional[str]:
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=_headers(), timeout=15)
            if r.status_code == 503:
                wait = 12 + random.uniform(5, 15)
                print(f"    ⚠ Rate-limited (503) – waiting {wait:.0f}s …")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                print(f"    ⚠ HTTP {r.status_code}")
                return None
            return r.text
        except requests.RequestException as exc:
            print(f"    ⚠ Request error: {exc} (attempt {attempt + 1}/{MAX_RETRIES})")
            time.sleep(5)
    return None


# ---------------------------------------------------------------------------
# Name-matching helpers
# ---------------------------------------------------------------------------
_STOP = frozenset({
    "the", "a", "an", "and", "or", "for", "of", "in", "with",
    "inch", "pack", "set", "kit", "bundle", "new", "2024", "2025",
})


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOP and len(w) > 1}


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _clean_price(raw: str) -> str:
    """Normalize a price string from Amazon (same idea as add_new_products)."""
    raw = raw.strip()
    raw = re.sub(r"^from\s+", "", raw, flags=re.IGNORECASE)
    prices = re.findall(r"\$[\d,]+(?:\.\d{2})?", raw)
    if len(prices) >= 2:
        return f"{prices[0]}-{prices[1]}"
    if len(prices) == 1:
        return prices[0]
    return raw if raw else ""


def _price_from_search_item(item) -> str:
    """Best-effort price from a search-result tile (may be missing for some listings)."""
    price_el = (
        item.select_one(".a-price .a-offscreen")
        or item.select_one(".a-price-whole")
    )
    return _clean_price(price_el.get_text(strip=True) if price_el else "")


def _price_from_rainforest_item(item: dict) -> str:
    p = item.get("price")
    if isinstance(p, dict):
        raw = p.get("raw")
        if raw:
            return _clean_price(str(raw))
        val = p.get("value")
        if val is not None:
            try:
                return _clean_price(f"${float(val):.2f}")
            except (TypeError, ValueError):
                pass
    elif isinstance(p, str) and p.strip():
        return _clean_price(p)
    return ""


# ---------------------------------------------------------------------------
# Amazon search → ASIN resolution
# ---------------------------------------------------------------------------
@dataclass
class SearchResult:
    asin: str
    title: str
    overlap: float
    price_range: str = ""


def search_for_asin(product_name: str) -> Optional[SearchResult]:
    """Search Amazon for product_name and return the best matching ASIN."""
    query = urllib.parse.quote_plus(product_name)
    url   = f"https://www.amazon.com/s?k={query}"
    html  = _fetch(url)
    if not html:
        return None

    soup  = BeautifulSoup(html, "html.parser")
    items = soup.select('[data-component-type="s-search-result"]') or \
            soup.select(".s-result-item[data-asin]")

    best: Optional[SearchResult] = None

    for item in items[:8]:
        asin = item.get("data-asin", "").strip()
        if not asin or len(asin) != 10:
            continue

        title_el = (
            item.select_one("h2 a span")
            or item.select_one("h2 span")
            or item.select_one(".a-text-normal")
        )
        if not title_el:
            continue
        title = title_el.get_text(strip=True)

        score = _overlap(product_name, title)
        price_range = _price_from_search_item(item)
        if best is None or score > best.overlap:
            best = SearchResult(asin=asin, title=title, overlap=score, price_range=price_range)

        # Early exit on strong match
        if score >= 0.80:
            break

    return best


def search_for_asin_rainforest(product_name: str, api_key: str) -> Optional[SearchResult]:
    """Use Rainforest API to find the best ASIN for a product name.
    No rate limits, no CAPTCHAs — results come from Rainforest's proxy network.
    """
    try:
        resp = requests.get(
            RAINFOREST_BASE,
            params={
                "api_key":      api_key,
                "type":         "search",
                "amazon_domain": "amazon.com",
                "search_term":  product_name,
            },
            timeout=30,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"    ⚠ Rainforest API error: {exc}")
        return None

    if "error" in data:
        print(f"    ⚠ Rainforest error: {data['error'].get('message', data['error'])}")
        return None

    results = data.get("search_results", [])
    best: Optional[SearchResult] = None

    for item in results[:8]:
        asin = item.get("asin", "").strip()
        if not asin or len(asin) != 10:
            continue
        title = item.get("title", "").strip()
        score = _overlap(product_name, title)
        price_range = _price_from_rainforest_item(item)
        if best is None or score > best.overlap:
            best = SearchResult(asin=asin, title=title, overlap=score, price_range=price_range)
        if score >= 0.80:
            break

    return best


def make_direct_url(asin: str) -> str:
    return f"https://www.amazon.com/dp/{asin}?tag={AFFILIATE_TAG}"


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------
def load_csv(path: Path) -> list[dict[str, str]]:
    # utf-8-sig strips the BOM so DictReader's first key is "Product Name", not
    # "﻿Product Name" — the latter silently blanks every name on rewrite.
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    # Derive fieldnames from the live data so extra columns (e.g. sale columns)
    # are never dropped; fall back to FIELDNAMES only when there are no rows.
    fieldnames = list(rows[0].keys()) if rows else list(FIELDNAMES)
    for row in rows:
        for k in row:
            if k not in fieldnames:
                fieldnames.append(k)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def needs_fix(row: dict[str, str]) -> bool:
    url = row.get("Amazon URL", "").strip()
    return bool(url) and "/dp/" not in url


# ---------------------------------------------------------------------------
# Fix result
# ---------------------------------------------------------------------------
@dataclass
class FixResult:
    index: int
    name: str
    old_url: str
    new_url: str = ""
    asin: str = ""
    matched_title: str = ""
    overlap: float = 0.0
    new_price_range: str = ""  # from search listing when --update-prices
    status: str = "pending"   # ok | no_match | weak_match | error | skipped


# ---------------------------------------------------------------------------
# Audit (no scraping)
# ---------------------------------------------------------------------------
def cmd_audit(rows: list[dict[str, str]], csv_path: Path = CSV_PATH) -> None:
    total     = len(rows)
    has_asin  = sum(1 for r in rows if "/dp/" in r.get("Amazon URL", ""))
    no_asin   = sum(1 for r in rows if needs_fix(r))
    empty_url = sum(1 for r in rows if not r.get("Amazon URL", "").strip())

    print(f"\n{'='*60}")
    print(f"  CSV Audit: {csv_path}")
    print(f"{'='*60}")
    print(f"  Total products      : {total:,}")
    print(f"  Has ASIN (/dp/)     : {has_asin:,}  ✓")
    print(f"  Search URL (no ASIN): {no_asin:,}  ← need fixing")
    print(f"  Empty URL           : {empty_url:,}")

    # Show breakdown by category
    from collections import Counter
    cat_counts: Counter[str] = Counter()
    for r in rows:
        if needs_fix(r):
            cat_counts[r.get("Category", "Unknown").strip()] += 1

    if cat_counts:
        print(f"\n  Products needing fix by category (top 15):")
        for cat, n in cat_counts.most_common(15):
            print(f"    {cat:<35} {n:>4}")
    print()


# ---------------------------------------------------------------------------
# Main fix logic (single-threaded, with optional parallel mode)
# ---------------------------------------------------------------------------
def resolve_one(
    idx: int,
    row: dict[str, str],
    use_rainforest: bool = False,
    api_key: str = "",
    delay_min: float = DELAY_MIN,
    delay_max: float = DELAY_MAX,
    threshold: float = MATCH_THRESHOLD,
) -> FixResult:
    name    = row.get("Product Name", "").strip()
    old_url = row.get("Amazon URL", "").strip()
    result  = FixResult(index=idx, name=name, old_url=old_url)

    if use_rainforest:
        hit = search_for_asin_rainforest(name, api_key)
    else:
        time.sleep(random.uniform(delay_min, delay_max))  # polite delay for direct scraping
        hit = search_for_asin(name)
    if hit is None:
        result.status = "error"
        return result

    result.matched_title = hit.title
    result.overlap        = hit.overlap
    if hit.price_range and hit.price_range != "$0":
        result.new_price_range = hit.price_range

    if hit.overlap < threshold:
        result.status = "weak_match"
        result.asin   = hit.asin
        result.new_url = make_direct_url(hit.asin)
    else:
        result.status  = "ok"
        result.asin    = hit.asin
        result.new_url = make_direct_url(hit.asin)

    return result


def cmd_fix(
    rows: list[dict[str, str]],
    csv_path: Path = CSV_PATH,
    threshold: float = MATCH_THRESHOLD,
    apply: bool = False,
    limit: int = 0,
    workers: int = 1,
    use_rainforest: bool = False,
    api_key: str = "",
    delay_min: float = DELAY_MIN,
    delay_max: float = DELAY_MAX,
    update_prices: bool = False,
) -> None:
    to_fix = [(i, r) for i, r in enumerate(rows) if needs_fix(r)]

    if not to_fix:
        print("  ✅ All products already have direct /dp/ ASIN URLs — nothing to fix!")
        return

    if use_rainforest and not api_key:
        print("ERROR: --rainforest requires RAINFOREST_API_KEY.", file=sys.stderr)
        print("  Set it in .env or as an environment variable.", file=sys.stderr)
        print("  See .env.example for the template.", file=sys.stderr)
        sys.exit(1)

    if limit:
        to_fix = to_fix[:limit]

    total_need = sum(1 for r in rows if needs_fix(r))
    print(f"\n{'='*60}")
    print(f"  {'DRY RUN' if not apply else 'APPLYING'} — fix Amazon URLs")
    mode_label = "Rainforest API" if use_rainforest else "direct Amazon scraping"
    print(f"  Mode                 : {mode_label}")
    if not use_rainforest:
        print(f"  Scrape delay (s)     : {delay_min:.1f} – {delay_max:.1f} between products")
    print(f"  Update prices        : {'yes (from search listing)' if update_prices else 'no'}")
    print(f"{'='*60}")
    print(f"  Products needing fix : {total_need:,}")
    print(f"  Processing this run  : {len(to_fix):,}" + (f" (--limit {limit})" if limit else ""))
    print(f"  Match threshold      : {threshold:.0%} word-overlap")
    print()

    results: list[FixResult] = []

    def _save_and_summarise(collected: list[FixResult], interrupted: bool = False) -> None:
        """Print summary and write whatever was resolved so far to the CSV."""
        ok_res    = [r for r in collected if r.status == "ok"]
        weak_res  = [r for r in collected if r.status == "weak_match"]
        error_res = [r for r in collected if r.status in ("error", "no_match")]
        good_res  = ok_res + weak_res

        tag = "  ⚠ INTERRUPTED —" if interrupted else ""
        print(f"\n{'─'*60}")
        print(f"{tag} Results for {len(collected)} products processed:")
        print(f"    ✓ Strong match (≥{threshold:.0%})  : {len(ok_res):>4}")
        print(f"    ⚠ Weak match  (<{threshold:.0%})   : {len(weak_res):>4}  (will still be applied)")
        print(f"    ✗ Failed / no result     : {len(error_res):>4}  (URL unchanged)")
        print(f"{'─'*60}")

        if weak_res:
            print(f"\n  Weak matches — review manually:")
            for r in weak_res[:20]:
                print(f"    [{r.overlap:.0%}] {r.name[:50]}")
                print(f"          matched: {r.matched_title[:55]}")
                print(f"          URL:     {r.new_url}")

        if error_res:
            print(f"\n  Failed lookups — URL unchanged:")
            for r in error_res[:10]:
                print(f"    ✗ {r.name[:65]}")

        if not apply:
            print(f"\n  [DRY RUN] No changes made.")
            n_prices = sum(1 for r in good_res if r.new_price_range)
            extra = f", {n_prices} Price Range fields" if update_prices and n_prices else ""
            print(f"  Re-run with --apply to update the CSV ({len(good_res)} URLs{extra} would be updated).")
            return

        if not good_res:
            print("\n  Nothing to apply — no successful lookups.")
            return

        fix_map: dict[int, str] = {r.index: r.new_url for r in good_res}
        price_map: dict[int, str] = {
            r.index: r.new_price_range
            for r in good_res
            if update_prices and r.new_price_range
        }
        updated_rows = []
        for i, row in enumerate(rows):
            if i in fix_map:
                row = dict(row)
                row["Amazon URL"] = fix_map[i]
                if i in price_map:
                    row["Price Range"] = price_map[i]
            updated_rows.append(row)

        write_csv(csv_path, updated_rows)
        remaining = sum(1 for r in updated_rows if needs_fix(r))
        print(f"\n  ✅ CSV updated — {len(good_res)} URLs fixed.")
        if price_map:
            print(f"  Price Range updated: {len(price_map):,} rows (search-listing snapshot).")
        print(f"  Still needs fixing: {remaining:,} products")
        print(f"  (Run again to process the next batch)")

    # ── Sequential loop with Ctrl+C support ──────────────────────────────────
    if workers > 1:
        print(f"  Running with {workers} parallel workers …\n")
        try:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {
                    ex.submit(
                        resolve_one,
                        idx,
                        row,
                        use_rainforest,
                        api_key,
                        delay_min,
                        delay_max,
                        threshold,
                    ): (idx, row)
                    for idx, row in to_fix
                }
                done = 0
                for future in as_completed(futures):
                    done += 1
                    r = future.result()
                    name = r.name[:55]
                    if r.status == "ok":
                        px = f"  {r.new_price_range}" if r.new_price_range else ""
                        print(f"  [{done}/{len(to_fix)}] ✓ {name} → {r.asin}{px}")
                    elif r.status == "weak_match":
                        px = f"  {r.new_price_range}" if r.new_price_range else ""
                        print(f"  [{done}/{len(to_fix)}] ⚠ {name} → {r.asin} ({r.overlap:.0%}){px}")
                    else:
                        print(f"  [{done}/{len(to_fix)}] ✗ {name} ({r.status})")
                    results.append(r)
        except KeyboardInterrupt:
            print("\n\n  ⚠ Ctrl+C detected — saving fixes collected so far …")
            _save_and_summarise(results, interrupted=True)
            sys.exit(0)
    else:
        try:
            for i, (row_idx, row) in enumerate(to_fix):
                name = row.get("Product Name", "").strip()
                print(f"  [{i+1}/{len(to_fix)}] {name[:65]}")
                r = resolve_one(
                    row_idx,
                    row,
                    use_rainforest=use_rainforest,
                    api_key=api_key,
                    delay_min=delay_min,
                    delay_max=delay_max,
                    threshold=threshold,
                )
                if r.status == "ok":
                    pr = f"  price: {r.new_price_range}" if r.new_price_range else ""
                    print(f"    ✓ ASIN: {r.asin}  overlap: {r.overlap:.0%}  → {r.matched_title[:55]}{pr}")
                elif r.status == "weak_match":
                    pr = f"  price: {r.new_price_range}" if r.new_price_range else ""
                    print(f"    ⚠ WEAK ({r.overlap:.0%}) ASIN: {r.asin}  → {r.matched_title[:55]}{pr}")
                else:
                    print(f"    ✗ {r.status}")
                results.append(r)
        except KeyboardInterrupt:
            print("\n\n  ⚠ Ctrl+C detected — saving fixes collected so far …")
            _save_and_summarise(results, interrupted=True)
            sys.exit(0)

    _save_and_summarise(results)



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve search-only Amazon URLs to direct /dp/ASIN links",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--rainforest", action="store_true",
        help="Use Rainforest API instead of direct scraping (needs RAINFOREST_API_KEY in .env)",
    )
    parser.add_argument(
        "--audit", action="store_true",
        help="Just count and categorise missing ASINs — no scraping",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Write fixes to CSV (default: dry run, no changes)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max products to process per run (default: all)",
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help="Parallel scraping workers, default 1 (sequential). Use ≤3 to avoid bans.",
    )
    parser.add_argument(
        "--threshold", type=float, default=MATCH_THRESHOLD,
        help=f"Min word-overlap to accept a match (default: {MATCH_THRESHOLD})",
    )
    parser.add_argument(
        "--delay-min", type=float, default=DELAY_MIN,
        help=f"Min seconds between direct-scrape requests (default: {DELAY_MIN})",
    )
    parser.add_argument(
        "--delay-max", type=float, default=DELAY_MAX,
        help=f"Max seconds between direct-scrape requests (default: {DELAY_MAX})",
    )
    parser.add_argument(
        "--update-prices", action="store_true",
        help="When applying, also set Price Range from the matched search result (listing snapshot)",
    )
    parser.add_argument(
        "--csv", type=Path, default=CSV_PATH,
        help=f"Path to CSV (default: {CSV_PATH})",
    )
    args = parser.parse_args()

    if args.delay_min < 0 or args.delay_max < 0 or args.delay_max < args.delay_min:
        print("ERROR: --delay-min and --delay-max must be non-negative and max >= min.", file=sys.stderr)
        return 1

    csv_path  = args.csv
    threshold = args.threshold

    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        return 1

    rows = load_csv(csv_path)

    if args.audit:
        cmd_audit(rows, csv_path)
        return 0

    cmd_fix(
        rows,
        csv_path=csv_path,
        threshold=threshold,
        apply=args.apply,
        limit=args.limit,
        workers=args.workers,
        use_rainforest=args.rainforest,
        api_key=RAINFOREST_API_KEY,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        update_prices=args.update_prices,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
