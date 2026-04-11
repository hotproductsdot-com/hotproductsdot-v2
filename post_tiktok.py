#!/usr/bin/env python3
"""
Daily social media poster for HotProducts.

Picks one product per day (rotating through the top 60 by affiliate potential)
and posts it to TikTok.

Usage:
    python post_tiktok.py [--dry-run]

Required GitHub Actions secrets (set in repo Settings \u00b7 Secrets):
    TIKTOK_ACCESS_TOKEN \u00b4 TikTok Content Posting API access token
                          (video.publish scope)
"""

import argparse
import csv
import os
import re
import sys
from datetime import date
from pathlib import Path

try:
    import tiktok_api
except ImportError:
    print("tiktok_api.py not found in the same directory. Please make sure it is there.")
    sys.exit(1)

# \u00b1\u00b1 Config \\nSITE_URL        = "https://hotproductsdot.com"
CSV_PATH        = Path(__file__).parent / "products" / "top-1000.csv"
LOG_PATH        = Path(__file__).parent / "marketing-campaigns" / "post_log.csv"
ROTATION_POOL   = 60   # rotate through top-N products by affiliate potential

# \u00b1\u00b1 Helpers \\ndef slugify(text: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", text.lower()))


def load_top_products(n: int) -> list[dict]:
    """Read CSV, return top-N products sorted by affiliate potential then rating."""
    products = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = (row.get("Product Name") or "").strip()
            if not name:
                continue
            try:
                potential = int((row.get("Affiliate Potential") or "7").strip() or "7")
            except ValueError:
                potential = 7
            try:
                rating = float((row.get("Rating") or "4.5").strip() or "4.5")
            except ValueError:
                rating = 4.5
            products.append({
                "name":     name,
                "slug":     slugify(name),
                "category": (row.get("Category") or "").strip(),
                "price":    (row.get("Price Range") or "Check price").strip(),
                "rating":   rating,
                "reviews":  (row.get("Review Count") or "").strip(),
                "potential": potential,
            })
    products.sort(key=lambda x: (x["potential"], x["rating"]), reverse=True)
    return products[:n]


def pick_todays_product(products: list[dict]) -> dict:
    """Deterministic daily rotation using day-of-year."""
    day = date.today().timetuple().tm_yday  # 1\u2013366
    return products[(day - 1) % len(products)]


def product_page_url(product: dict) -> str:
    return f"{SITE_URL}/products/{product[\'slug\']}/"


def product_image_url(product: dict) -> str:
    return f"{SITE_URL}/products/{product[\'slug\']}.jpg"


# \u00b1\u00b1 Caption generators \\ndef tiktok_caption(product: dict) -> str:
    price   = product["price"] if product["price"] not in ("", "N/A") else "Check price"
    cat_tag = "#" + re.sub(r"[^a-z0-9]", "", product["category"].lower())

    return "\\n".join([
        f"\ud83d\udd25 {product[\'name\']}",
        f"\u2b50 {product[\'rating\']}/5  \ud83d\udcb0 {price}",
        f"\ud83d\udd17 {product_page_url(product)}",
        "",
        f"#hotproducts #amazonfinds #TikTokMadeMeBuyIt {cat_tag} #dealoftheday",
    ])


# \u00b1\u00b1 Logging \\ndef log_result(product: dict, platform: str, result: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not LOG_PATH.exists()
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["Date", "Platform", "Product", "Status", "Detail"])
        status = "ok" if result.get("ok") else "error"
        detail = result.get("post_id") or result.get("publish_id") or result.get("error") or ""
        writer.writerow([date.today().isoformat(), platform, product["name"]", status, detail])


# \u00b1\u00b1 Main \\ndef main() -> None:
    # Ensure stdout handles emojis on Windows consoles
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Post today\'s product to TikTok")
    parser.add_argument("--dry-run",  action="store_true", help="Preview posts without sending")
    args = parser.parse_args()

    products = load_top_products(ROTATION_POOL)
    if not products:
        print("[!] No products loaded from CSV.")
        sys.exit(1)

    product = pick_todays_product(products)
    print(f"Today\'s product  : {product[\'name\']}")
    print(f"Category         : {product[\'category\']}")
    print(f"Rating           : {product[\'rating\']}/5")
    print(f"Price            : {product[\'price\']}")
    print(f"Page URL         : {product_page_url(product)}")
    print(f"Image URL        : {product_image_url(product)}")
    print()

    print("> Posting to TikTok...")
    caption = tiktok_caption(product)
    result  = tiktok_api.post_photo([product_image_url(product)], caption)
    if args.dry_run:
        print(f"[DRY RUN] TikTok\\n  image  : {product_image_url(product)}\\n  caption:\\n{caption}\\n")
        result = {"ok": True, "dry_run": True}
    if result["ok"]:
        print(f"  OK publish_id: {result.get(\'publish_id\', \'dry-run\')}")
    else:
        print(f"  FAIL {result[\'error\']}")
    if not args.dry_run:
        log_result(product, "tiktok", result)

    if not result["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
