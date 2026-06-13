#!/usr/bin/env python3
"""Check that catalog product names still match the live Amazon ASIN title.

This is a safety net for rows where the display name/description is correct
but the Amazon link points to a different variant. It uses the existing
amazon_local_api scraper so the check works through Amazon's bot defenses
more reliably than a raw HTML fetch.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from amazon_local_api import fetch_product

STOPWORDS = {
    "amazon", "the", "and", "for", "with", "from", "a", "an", "of", "to",
    "smart", "video", "calling", "touch", "screen", "display", "device", "new",
    "black", "white", "gen",
}

ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})", re.IGNORECASE)


def parse_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def extract_asin(url: str) -> str | None:
    m = ASIN_RE.search(url or "")
    return m.group(1).upper() if m else None


def normalize_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split()
        if token and token not in STOPWORDS
    }


def title_coverage(expected: str, observed: str) -> float:
    expected_tokens = normalize_tokens(expected)
    observed_tokens = normalize_tokens(observed)
    if not expected_tokens:
        return 1.0
    hits = sum(1 for token in expected_tokens if token in observed_tokens)
    return hits / len(expected_tokens)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=Path(__file__).parent / "products" / "top-1000.csv")
    parser.add_argument("--output", default="")
    parser.add_argument("--min-coverage", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    csv_path = Path(args.csv)
    rows = parse_csv(csv_path)
    items = []
    for row in rows:
        url = (row.get("Amazon URL") or "").strip()
        name = (row.get("Product Name") or "").strip()
        asin = extract_asin(url)
        if url and asin and name:
            items.append((name, asin, url))
    if args.limit > 0:
        items = items[:args.limit]

    mismatches = []
    errors = []
    checked = 0

    for name, asin, url in items:
        checked += 1
        product = fetch_product(asin)
        if product.page_status != "ok" or not product.title:
            errors.append({
                "name": name,
                "asin": asin,
                "url": url,
                "page_status": product.page_status,
                "error": product.error,
                "engine": product.engine,
                "attempts": product.attempts,
            })
            continue

        coverage = title_coverage(name, product.title)
        if coverage < args.min_coverage:
            mismatches.append({
                "name": name,
                "asin": asin,
                "url": url,
                "amazonTitle": product.title,
                "coverage": round(coverage, 3),
            })

    report = {
        "date": datetime.now(timezone.utc).isoformat(),
        "csvFile": str(csv_path),
        "summary": {
            "total": len(items),
            "checked": checked,
            "mismatches": len(mismatches),
            "errors": len(errors),
        },
        "mismatches": mismatches,
        "errors": errors,
    }

    out_path = Path(args.output) if args.output else csv_path.with_name("title-report.json")
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Checked {checked} products; mismatches: {len(mismatches)}; errors: {len(errors)}")
    print(f"Report saved to: {out_path}")
    return 1 if mismatches or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
