#!/usr/bin/env python3
"""
fix_amazon_urls.py - Resolve search-only Amazon URLs to direct /dp/ASIN links.

Many legacy products in products/top-1000.csv have Amazon URLs in the form:
    https://www.amazon.com/s?k=Product+Name&tag=hotproduct033-20

This script finds those rows, searches Amazon for the product name, extracts
the best matching ASIN, and replaces the URL with a direct /dp/ link.

API key setup:
    Copy .env.example to .env and set RAINFOREST_API_KEY=your_key_here
    Or export the variable: set RAINFOREST_API_KEY=your_key_here  (Windows)
                            export RAINFOREST_API_KEY=your_key_here (Mac/Linux)

Usage:
    python fix_amazon_urls.py --audit               # Count problems, no scraping
    python fix_amazon_urls.py                       # Dry run — preview changes
    python fix_amazon_urls.py --apply               # Write fixes (direct scraping)
    python fix_amazon_urls.py --apply --rainforest  # Use Rainforest API (recommended)
    python fix_amazon_urls.py --apply --rainforest --limit 200  # Process 200 at once
    python fix_amazon_urls.py --apply --limit 50    # Direct scraping, 50 per run
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
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# Amazon search → ASIN resolution
# ---------------------------------------------------------------------------
@dataclass
class SearchResult:
    asin: str
    title: str
    overlap: float


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
        if best is None or score > best.overlap:
            best = SearchResult(asin=asin, title=title, overlap=score)

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
        if best is None or score > best.overlap:
            best = SearchResult(asin=asin, title=title, overlap=score)
        if score >= 0.80:
            break

    return best


def make_direct_url(asin: str) -> str:
    return f"https://www.amazon.com/dp/{asin}?tag={AFFILIATE_TAG}"


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------
def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})


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
def resolve_one(idx: int, row: dict[str, str], use_rainforest: bool = False, api_key: str = "") -> FixResult:
    name    = row.get("Product Name", "").strip()
    old_url = row.get("Amazon URL", "").strip()
    result  = FixResult(index=idx, name=name, old_url=old_url)

    if use_rainforest:
        hit = search_for_asin_rainforest(name, api_key)
    else:
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))  # polite delay for direct scraping
        hit = search_for_asin(name)
    if hit is None:
        result.status = "error"
        return result

    result.matched_title = hit.title
    result.overlap        = hit.overlap

    if hit.overlap < MATCH_THRESHOLD:  # module default used for standalone call
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
    mode_label = "Rainforest API (no rate limits)" if use_rainforest else "direct Amazon scraping"
    print(f"  Mode                 : {mode_label}")
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
            print(f"  Re-run with --apply to update the CSV ({len(good_res)} URLs would be fixed).")
            return

        if not good_res:
            print("\n  Nothing to apply — no successful lookups.")
            return

        fix_map: dict[int, str] = {r.index: r.new_url for r in good_res}
        updated_rows = []
        for i, row in enumerate(rows):
            if i in fix_map:
                row = dict(row)
                row["Amazon URL"] = fix_map[i]
            updated_rows.append(row)

        write_csv(csv_path, updated_rows)
        remaining = sum(1 for r in updated_rows if needs_fix(r))
        print(f"\n  ✅ CSV updated — {len(good_res)} URLs fixed.")
        print(f"  Still needs fixing: {remaining:,} products")
        print(f"  (Run again to process the next batch)")

    # ── Sequential loop with Ctrl+C support ──────────────────────────────────
    if workers > 1:
        print(f"  Running with {workers} parallel workers …\n")
        try:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(resolve_one, idx, row, use_rainforest, api_key): (idx, row) for idx, row in to_fix}
                done = 0
                for future in as_completed(futures):
                    done += 1
                    r = future.result()
                    name = r.name[:55]
                    if r.status == "ok":
                        print(f"  [{done}/{len(to_fix)}] ✓ {name} → {r.asin}")
                    elif r.status == "weak_match":
                        print(f"  [{done}/{len(to_fix)}] ⚠ {name} → {r.asin} ({r.overlap:.0%})")
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
                r = resolve_one(row_idx, row, use_rainforest=use_rainforest, api_key=api_key)
                if r.status == "ok":
                    print(f"    ✓ ASIN: {r.asin}  overlap: {r.overlap:.0%}  → {r.matched_title[:55]}")
                elif r.status == "weak_match":
                    print(f"    ⚠ WEAK ({r.overlap:.0%}) ASIN: {r.asin}  → {r.matched_title[:55]}")
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
        "--csv", type=Path, default=CSV_PATH,
        help=f"Path to CSV (default: {CSV_PATH})",
    )
    args = parser.parse_args()

    csv_path  = args.csv
    threshold = args.threshold

    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        return 1

    rows = load_csv(csv_path)

    if args.audit:
        cmd_audit(rows, csv_path)
        return 0

    cmd_fix(rows, csv_path=csv_path, threshold=threshold,
            apply=args.apply, limit=args.limit, workers=args.workers,
            use_rainforest=args.rainforest, api_key=RAINFOREST_API_KEY)
    return 0


if __name__ == "__main__":
    sys.exit(main())
