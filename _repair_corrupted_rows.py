"""One-off repair: re-scrape corrupted catalog rows and write verified values.

Targets rows whose Price/Rating/Review Count columns were swapped or shifted
(2026-06-10 corruption). Bypasses the >25% drift gate on purpose — the CSV
values are known-bad, so live data is the only truth. Dated backup first.
"""
from __future__ import annotations

import csv
import sys
import time
from datetime import date
from pathlib import Path

from amazon_local_api import fetch_product
from refresh_catalog_local import CSV_PATH, extract_asin

TARGET_ASINS = {
    "B09QF1H3VF",  # Dell XPS 17 Laptop
    "B0CP9YB3Q4",  # STANLEY Quencher H2.0
    "B08CGVTVMN",  # Vizio V-Series 5.1 Soundbar
    "B0D3TNZTNS",  # Nakamichi Shockwafe Ultra
    "B0FVQYBVGP",  # ASUS ROG Huracan G21CX
    "B0DVZ9D58R",  # Turtle Beach Stealth 600 Gen 3
    "B07ZQRNWDH",  # Sennheiser GSP 370
    "B09V3FPPZY",  # Samsung Jet Bot AI+
    "B0C1SHGHSZ",  # Google Pixel Tablet
    "B09HR7SWTR",  # Roku Express 4K+
    "B08DG5J6QJ",  # B&O Beosound A1
    "B08N69BKCX",  # Amazon Echo 4th Gen
    "B09NJ8SJB9",  # Dell XPS 13 Plus
    "B08TZR782B",  # ViewSonic VP2768a
    "B08LB3LZL5",  # Ninja Foodi 9-in-1
    "B0727R431B",  # ChefSteps Joule
    "B09JL9N6R7",  # Chamberlain myQ
    "B0C6BQ8YW2",  # Ryobi PCL550B
    "B0D9NJ9BV5",  # Nest Protect 2-Pack
    "B0CK3L9WD3",  # Raspberry Pi 5 8GB
    "B07DXLSMBC",  # WD Elements SE 2TB
    "B08YF4LNDQ",  # By Terry Face Cream
    "B016Z69QF2",  # Kiehl's Ultra Facial Cream
    "B01FRI60LC",  # Yamaha YFL-222 Flute
}


def main() -> int:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    stamp = date.today().isoformat()
    backup = CSV_PATH.with_name(f"top-1000.backup.{stamp}.repair.csv")
    backup.write_bytes(CSV_PATH.read_bytes())
    print(f"Backup: {backup.name}")

    targets = [
        (i, asin) for i, row in enumerate(rows)
        if (asin := extract_asin(row.get("Amazon URL", ""))) in TARGET_ASINS
    ]
    print(f"Repairing {len(targets)} rows...\n")

    today = f"{date.today().month}/{date.today().day}/{date.today().year}"
    repaired, failed = [], []
    for n, (idx, asin) in enumerate(targets, 1):
        row = rows[idx]
        name = row.get("Product Name", "")[:45]
        live = fetch_product(asin, base_delay=2.0)
        if live.page_status != "ok" or not live.is_definitive():
            failed.append((asin, name, live.page_status, live.error))
            print(f"[{n:>2}/{len(targets)}] {asin} FAILED ({live.page_status}) {name}")
            time.sleep(2.0)
            continue
        before = (row.get("Price Range"), row.get("Rating"), row.get("Review Count"))
        if live.price is not None:
            row["Price Range"] = f"{live.price:.2f}"
        if live.rating is not None:
            row["Rating"] = f"{live.rating:.1f}"
        if live.reviews_count is not None:
            row["Review Count"] = str(live.reviews_count)
        row["Refreshed Date"] = today
        after = (row.get("Price Range"), row.get("Rating"), row.get("Review Count"))
        repaired.append(asin)
        print(f"[{n:>2}/{len(targets)}] {asin} {name}")
        print(f"        price/rating/reviews: {before} -> {after}")
        time.sleep(2.0)

    tmp = CSV_PATH.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(CSV_PATH)

    print(f"\nRepaired: {len(repaired)}   Failed: {len(failed)}")
    for asin, name, status, err in failed:
        print(f"  UNREPAIRED {asin} ({status}): {name}  {err or ''}")
    print(f"Catalog written: {CSV_PATH.name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
