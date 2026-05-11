#!/usr/bin/env python3
"""Quick price-check test: fetch live prices for 25 catalog products via Scrapling."""
import csv
import random
import re
import time
from pathlib import Path
from bs4 import BeautifulSoup
from scrapling.fetchers import FetcherSession

CSV_PATH = Path("/mnt/e/GITHUB/hotproductsdot-v2/products/top-1000.csv")
ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")

PRICE_SELECTORS = [
    ".apex-pricetopay-value .a-offscreen",
    "#apex_offerDisplay_desktop .a-offscreen",
    "#corePrice_feature_div .a-offscreen",
    "#buybox .a-price .a-offscreen",
    "#priceblock_ourprice",
    "#price",
    ".a-price .a-offscreen",  # last resort — may match comparison carousels
]

def fetch_live_price(fetcher: FetcherSession, asin: str) -> str:
    url = f"https://www.amazon.com/dp/{asin}"
    try:
        resp = fetcher.get(url, timeout=20, retries=1)
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
            if text:  # skip empty matches
                return text
    return "N/F"


def main() -> None:
    rows = list(csv.DictReader(CSV_PATH.open(newline="", encoding="utf-8")))
    candidates = [
        r for r in rows
        if ASIN_RE.search(r.get("Amazon URL", ""))
        and r.get("Price Range", "").strip()
    ]
    sample = random.sample(candidates, min(25, len(candidates)))

    fetcher = FetcherSession()
    results = []

    print(f"{'#':<4} {'ASIN':<12} {'Stored':<16} {'Live':<16} Product")
    print("-" * 100)

    for i, row in enumerate(sample, 1):
        m = ASIN_RE.search(row["Amazon URL"])
        asin = m.group(1) if m else "UNKNOWN"
        stored = row["Price Range"].strip()

        live = fetch_live_price(fetcher, asin)

        name = row["Product Name"][:50]
        flag = ""
        if live not in ("N/F", "BLOCKED") and not live.startswith("ERR") and not live.startswith("HTTP"):
            # crude mismatch flag
            stored_num = re.search(r"[\d.]+", stored.replace(",", ""))
            live_num = re.search(r"[\d.]+", live.replace(",", ""))
            if stored_num and live_num:
                s, l = float(stored_num.group()), float(live_num.group())
                if abs(s - l) / max(s, 1) > 0.15:
                    flag = " <-- DIFF"

        print(f"{i:<4} {asin:<12} {stored:<16} {live:<16} {name}{flag}")
        results.append({"asin": asin, "stored": stored, "live": live, "name": row["Product Name"]})

        if i < len(sample):
            time.sleep(random.uniform(2.5, 4.0))

    # Summary
    blocked   = sum(1 for r in results if r["live"] == "BLOCKED")
    errors    = sum(1 for r in results if r["live"].startswith(("ERR", "HTTP")))
    not_found = sum(1 for r in results if not r["live"] or r["live"] == "N/F")
    found     = len(results) - blocked - errors - not_found

    print("\n" + "=" * 60)
    print(f"  Prices found:     {found}/25")
    print(f"  Price not found:  {not_found}/25  (page loaded but no price el)")
    print(f"  Blocked/CAPTCHA:  {blocked}/25")
    print(f"  Errors/non-200:   {errors}/25")
    print("=" * 60)


if __name__ == "__main__":
    main()
