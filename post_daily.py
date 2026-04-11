#!/usr/bin/env python3
"""
Daily social media poster for HotProducts.

Picks one product per day (rotating through the top 60 by affiliate potential)
and posts it to Instagram and TikTok.

Usage:
    python post_instagram.py [--dry-run] [--platform instagram|tiktok|all]

Required GitHub Actions secrets (set in repo Settings → Secrets):
    IG_USER_ID          — Instagram Business Account ID (numeric string)
    IG_ACCESS_TOKEN     — Meta Graph API long-lived page access token
                          (instagram_basic + instagram_content_publish permissions)
    TIKTOK_ACCESS_TOKEN — TikTok Content Posting API access token
                          (video.publish scope)
"""

import argparse
import csv
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

import tiktok_api

# ─── Config ──────────────────────────────────────────────────────────────────

SITE_URL        = "https://hotproductsdot.com"
CSV_PATH        = Path(__file__).parent / "products" / "top-1000.csv"
LOG_PATH        = Path(__file__).parent / "marketing-campaigns" / "post_log.csv"
IG_API_BASE     = "https://graph.facebook.com/v21.0"
ROTATION_POOL   = 60   # rotate through top-N products by affiliate potential

# ─── Helpers ─────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
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
    day = date.today().timetuple().tm_yday  # 1–366
    return products[(day - 1) % len(products)]


def product_page_url(product: dict) -> str:
    return f"{SITE_URL}/products/{product['slug']}/"


def product_image_url(product: dict) -> str:
    return f"{SITE_URL}/products/{product['slug']}.jpg"


def format_stars(rating: float) -> str:
    full = int(rating)
    half = rating - full >= 0.5
    return "⭐" * full + ("✨" if half else "")


# ─── Caption generators ──────────────────────────────────────────────────────

def instagram_caption(product: dict) -> str:
    stars   = format_stars(product["rating"])
    price   = product["price"] if product["price"] not in ("", "N/A") else "Check price"
    reviews = product["reviews"]
    try:
        review_str = f"{int(reviews.replace(',', '')):,}"
    except (ValueError, AttributeError):
        review_str = reviews or "many"

    cat_tag = "#" + re.sub(r"[^a-z0-9]", "", product["category"].lower())

    return "\n".join([
        f"🔥 {product['name']}",
        "",
        f"{stars} {product['rating']}/5 · {review_str} verified reviews",
        f"💰 {price}",
        "",
        f"👉 Full details + link → {product_page_url(product)}",
        "",
        f"#hotproducts #amazonfinds #bestproducts {cat_tag} "
        "#dealoftheday #productreview #amazondeals #mustbuy #shopping",
    ])


def tiktok_caption(product: dict) -> str:
    price   = product["price"] if product["price"] not in ("", "N/A") else "Check price"
    cat_tag = "#" + re.sub(r"[^a-z0-9]", "", product["category"].lower())

    return "\n".join([
        f"🔥 {product['name']}",
        f"⭐ {product['rating']}/5  💰 {price}",
        f"🔗 {product_page_url(product)}",
        "",
        f"#hotproducts #amazonfinds #TikTokMadeMeBuyIt {cat_tag} #dealoftheday",
    ])


# ─── Instagram ───────────────────────────────────────────────────────────────

def post_instagram(product: dict, dry_run: bool = False) -> dict:
    """Two-step Instagram Graph API publish: create container → publish."""
    caption   = instagram_caption(product)
    image_url = product_image_url(product)

    if dry_run:
        print(f"[DRY RUN] Instagram\n  image  : {image_url}\n  caption:\n{caption}\n")
        return {"ok": True, "dry_run": True}

    user_id = os.environ.get("IG_USER_ID", "")
    token   = os.environ.get("IG_ACCESS_TOKEN", "")

    if not user_id or not token:
        return {"ok": False, "error": "Missing IG_USER_ID or IG_ACCESS_TOKEN env var"}

    api_base = "https://graph.instagram.com/v21.0" if token.startswith("IG") else "https://graph.facebook.com/v21.0"

    # Step 1 — create media container
    try:
        r1 = requests.post(
            f"{api_base}/{user_id}/media",
            data={"image_url": image_url, "caption": caption, "access_token": token},
            timeout=30,
        )
        d1 = r1.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}

    if "error" in d1:
        return {"ok": False, "error": d1["error"].get("message", str(d1["error"]))}

    creation_id = d1.get("id")
    if not creation_id:
        return {"ok": False, "error": f"No creation_id returned: {d1}"}

    time.sleep(3)  # Meta recommends a brief pause before publishing

    # Step 2 — publish
    try:
        r2 = requests.post(
            f"{api_base}/{user_id}/media_publish",
            data={"creation_id": creation_id, "access_token": token},
            timeout=30,
        )
        d2 = r2.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}

    if "error" in d2:
        return {"ok": False, "error": d2["error"].get("message", str(d2["error"]))}

    return {"ok": True, "post_id": d2.get("id", ""), "platform": "instagram"}


# ─── Logging ─────────────────────────────────────────────────────────────────

def log_result(product: dict, platform: str, result: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not LOG_PATH.exists()
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["Date", "Platform", "Product", "Status", "Detail"])
        status = "ok" if result.get("ok") else "error"
        detail = result.get("post_id") or result.get("publish_id") or result.get("error") or ""
        writer.writerow([date.today().isoformat(), platform, product["name"], status, detail])


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    # Ensure stdout handles emojis on Windows consoles
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Post today's product to Instagram and TikTok")
    parser.add_argument("--dry-run",  action="store_true", help="Preview posts without sending")
    parser.add_argument("--platform", choices=["instagram", "tiktok", "all"], default="instagram")
    args = parser.parse_args()

    products = load_top_products(ROTATION_POOL)
    if not products:
        print("[!] No products loaded from CSV.")
        sys.exit(1)

    product = pick_todays_product(products)
    print(f"Today's product  : {product['name']}")
    print(f"Category         : {product['category']}")
    print(f"Rating           : {product['rating']}/5")
    print(f"Price            : {product['price']}")
    print(f"Page URL         : {product_page_url(product)}")
    print(f"Image URL        : {product_image_url(product)}")
    print()

    results: dict[str, dict] = {}

    if args.platform in ("instagram", "all"):
        print(">> Posting to Instagram...")
        result = post_instagram(product, dry_run=args.dry_run)
        results["instagram"] = result
        if result["ok"]:
            print(f"  OK post_id: {result.get('post_id', 'dry-run')}")
        else:
            print(f"  FAIL {result['error']}")
        if not args.dry_run:
            log_result(product, "instagram", result)

    if args.platform in ("tiktok", "all"):
        print(">> Posting to TikTok...")
        caption = tiktok_caption(product)
        result  = tiktok_api.post_photo([product_image_url(product)], caption)
        if args.dry_run:
            print(f"[DRY RUN] TikTok\n  image  : {product_image_url(product)}\n  caption:\n{caption}\n")
            result = {"ok": True, "dry_run": True}
        results["tiktok"] = result
        if result["ok"]:
            print(f"  OK publish_id: {result.get('publish_id', 'dry-run')}")
        else:
            print(f"  FAIL {result['error']}")
        if not args.dry_run:
            log_result(product, "tiktok", result)

    if any(not r["ok"] for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
