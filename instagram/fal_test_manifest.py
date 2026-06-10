#!/usr/bin/env python3
"""
On-device 3-post Instagram review generator for FAL.AI creative banners.

Outputs local banner/variant JPGs plus terminal-ready captions.
Skip Marketplace flow entirely.
"""
from __future__ import annotations

import csv
import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime

# fallback for sandboxed environments where Path(…) might misbehave
REPO_DIR = (Path(__file__).resolve().parent.parent if '__file__' in globals() else Path('.')).resolve()
sys.path.insert(0, str(REPO_DIR))

try:
    from instagram.image_gen_fal import _build_fal_prompt, _fal_generate_image, _load_image_bytes
    from instagram.banner_compose import compose_banner
except Exception as exc:
    print(f"Fatal import: {exc}")
    sys.exit(2)

PRODUCT_CSV = REPO_DIR / "products" / "top-1000.csv"


def load_top_products(n: int = 3) -> list[dict]:
    if not PRODUCT_CSV.exists():
        raise FileNotFoundError(f"Missing {PRODUCT_CSV}")
    rows: list[dict] = []
    with PRODUCT_CSV.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("Product Name") or "").strip()
            if not name:
                continue
            try:
                rating = float((row.get("Rating") or "0").strip() or "0")
            except ValueError:
                rating = 0.0
            reviews_raw = (row.get("Review Count") or "").strip()
            review_count = int("".join(ch for ch in reviews_raw if ch.isdigit()) or "0")
            amazon_url = (row.get("Amazon URL") or "").strip()
            if rating < 4.5 or review_count < 100 or not amazon_url:
                continue
            rows.append({
                "name": name,
                "slug": name.lower().replace("&", "and").replace(" ", "-").replace("--", "-"),
                "category": (row.get("Category") or "").strip() or "Best Sellers",
                "amazon_url": amazon_url,
                "price": (row.get("Price Range") or "Check price").strip(),
                "rating": rating,
                "review_count": review_count,
                "bsr": (row.get("BSR") or "").strip(),
                "price_num": _parse_price(row.get("Price Range") or ""),
            })
            if len(rows) >= n:
                break
    return rows


def _parse_price(raw: str) -> float:
    raw = (raw or "").strip()
    if not raw:
        return 0.0
    raw = raw.replace("$", "").replace(",", "").split("-")[0].strip()
    try:
        return float(raw)
    except ValueError:
        return 0.0


def render_caption(product: dict) -> str:
    review_short = f"{product['review_count']/1000:.1f}k".replace(".0k", "k") if product["review_count"] >= 1000 else str(product["review_count"])
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
        "",
        " ".join([
            "#hotproducts", "#hotproductsdaily", "#amazonfinds", "#amazonmusthaves", "#productreview", "#dealoftheday", "#bestofamazon",
        ]),
    ]
    return "\n".join(lines)


def render_variant(product: dict, save_dir: Path) -> dict | None:
    save_dir.mkdir(parents=True, exist_ok=True)
    src_image = _load_image_bytes(product.get("amazon_url", "")) if product.get("amazon_url") else None
    if src_image is None:
        print(f"  [skip] cannot load source for {product['name']}")
        return None
    fal_result = _fal_generate_image(_build_fal_prompt(product["name"], product["category"]), src_image)
    if fal_result is None:
        print(f"  [skip] fal returned no image for {product['name']}")
        return None

    variant_path = save_dir / "variant.jpg"
    variant_path.write_bytes(fal_result)
    banner_path = save_dir / "banner.jpg"
    compose_banner({
        "name": product["name"],
        "price": product["price"],
        "rating": product["rating"],
    }, str(variant_path), str(banner_path))
    return {
        "banner": banner_path,
        "variant": variant_path,
        "caption": render_caption(product),
        "slug": product["slug"],
        "name": product["name"],
    }


def main() -> int:
    stamp = datetime.now().strftime("%Y-%m-%d")
    out_root = REPO_DIR / "generated_images" / f"fal_test_{stamp}"
    print(f"[manifest] out_root={out_root}")
    products = load_top_products(3)
    print(f"[manifest] products_selected={len(products)}")
    items: list[dict] = []
    for index, product in enumerate(products, start=1):
        item = render_variant(product, out_root / str(index))
        if item:
            items.append(item)
    for idx, item in enumerate(items, start=1):
        print(f"\n=== Post {idx}/{len(items)} ===\n{item['caption']}\n[image] {item['banner']}\n")
    if not items:
        print("[manifest] nothing generated")
        return 1
    manifest = {
        "date": stamp,
        "count": len(items),
        "items": [
            {
                "slug": item["slug"],
                "name": item["name"],
                "banner_path": str(item["banner"]),
                "variant_path": str(item["variant"]),
                "caption": item["caption"],
            }
            for item in items
        ],
    }
    manifest_path = out_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[manifest] written {manifest_path}")
    return 0


if __name__ == "__main__":
    import json
    sys.exit(main())
