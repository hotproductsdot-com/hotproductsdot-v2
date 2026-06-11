#!/usr/bin/env python3
"""Local 3-post test for migrated FAL.AI Instagram pipeline.

This bypasses Meta publish entirely and produces:
  generated_images/fal_instagram_test_POSTS/slug.jpg
plus captions preview in the terminal output.

Run:
  python3 instagram/fal_test_instagram_posts.py
"""
from __future__ import annotations

import csv
import re
import os
import sys
from io import BytesIO
from pathlib import Path
from datetime import datetime

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)

from instagram.image_gen_fal import _build_fal_prompt, _fal_generate_image, _load_image_bytes
from instagram.banner_compose import compose_banner

DEBUG = True

def log(msg: str) -> None:
    if DEBUG:
        print(msg, flush=True)

def load_products(n: int = 3) -> list[dict]:
    csv_path = PROJECT_ROOT / "products" / "top-1000.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    products = []
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("Product Name") or "").strip()
            if not name:
                continue
            category = (row.get("Category") or "").strip()
            amazon_url = (row.get("Amazon URL") or "").strip()
            if not amazon_url:
                continue
            try:
                rating = float((row.get("Rating") or "0").strip() or "0")
            except ValueError:
                rating = 0.0
            if rating < 4.5:
                continue
            try:
                review_count = int("".join(ch for ch in (row.get("Review Count") or "0") if ch.isdigit()))
            except ValueError:
                review_count = 0
            if review_count < 100:
                continue
            products.append({
                "name": name,
                "slug": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
                "category": category or "Best Sellers",
                "amazon_url": amazon_url,
                "price": (row.get("Price Range") or "Check price").strip(),
                "rating": rating,
                "review_count": review_count,
                "bsr": row.get("BSR", "").strip(),
                "price_num": float("".join(ch for ch in (row.get("Price Range") or "0") if (ch.isdigit() or ch == ".")) or "0"),
            })
            if len(products) >= n:
                break
    return products

def fetch_amazon_image(product: dict) -> str | None:
    url = product.get("amazon_url", "")
    if not url:
        return None
    try:
        import re as _re
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=20,
        )
        if not resp.ok:
            return None
        m = _re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', resp.text)
        if m:
            return m.group(1)
    except Exception as exc:
        log(f"  Amazon image fetch failed: {exc}")
    return None

def to_slug(product: dict) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", product["name"].lower()).strip("-")

def build_caption(product: dict) -> str:
    review_short = f"{int(product['review_count']/1000)}k" if product["review_count"] >= 1000 else str(product["review_count"])
    hook = f"Stop scrolling. This {product['category'].split()[0]} just made our shortlist 👀"
    lines = [
        hook,
        "",
        f"⭐ {product['rating']}/5  ·  {review_short} reviews",
        f"💰 {product['price']}",
        "",
        "Save this one for when you finally pull the trigger 💾",
        "",
        "🔗 Tap the link in our bio for the full review + best price",
    ]
    tags = " ".join([
        "#hotproducts",
        "#hotproductsdaily",
        "#amazonfinds",
        "#amazonmusthaves",
        "#productreview",
        "#dealoftheday",
        "#bestofamazon",
    ])
    return "\n".join(lines) + "\n\n" + tags

def compose_variants(product: dict, save_root: Path) -> dict:
    slug = to_slug(product)
    out_dir = save_root / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt = _build_fal_prompt(product["name"], product["category"])

    amz_url = fetch_amazon_image(product)
    base_bytes = _load_image_bytes(amz_url) if amz_url else None
    variant_path = out_dir / "variant_fal.jpg"

    out_bytes = _fal_generate_image(prompt, base_bytes)
    if out_bytes is None:
        return {"ok": False, "reason": "fal_generate returned no image"}

    variant_path.write_bytes(out_bytes)
    banner_path = out_dir / "banner.jpg"
    compose_banner({"name": product["name"], "price": product["price"], "rating": product["rating"]},
                   str(variant_path), str(banner_path))
    return {
        "ok": True,
        "banner": str(banner_path),
        "variant": str(variant_path),
        "amazon_image": amz_url,
    }

def main() -> int:
    stamp = datetime.now().strftime("%Y-%m-%d")
    save_root = PROJECT_ROOT / "generated_images" / f"fal_test_POSTS_{stamp}"
    results = []
    print(f"\n== FAL Instagram test batch -> {save_root}\n")
    for prod in load_products(3):
        print(f"Processing: {prod['name']}")
        res = compose_variants(prod, save_root)
        if res.get("ok"):
            res["slug"] = to_slug(prod)
            res["caption"] = build_caption(prod)
            results.append(res)
            print(f"  OK -> {res['banner']}")
        else:
            print(f"  FAIL -> {res.get('reason')}")

    print("\n== CAPTIONS ==\n")
    for res in results:
        print(f"Product : {res['slug']}")
        print(f"Banner  : {res['banner']}")
        print(res["caption"])
        print("-" * 40)

    print(f"\nArtifacts: {save_root}\n")
    return 0 if results else 1

if __name__ == "__main__":
    sys.exit(main())
