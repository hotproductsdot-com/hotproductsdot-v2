#!/usr/bin/env python3
"""Run 3 local Instagram post test draws through FAL.AI + banner_compose."""

from __future__ import annotations

import csv, os, re, sys
from pathlib import Path
from datetime import datetime

REPO = Path("/mnt/e/GITHUB/hotproductsdot-v2").resolve()
sys.path.insert(0, str(REPO))

ENV_PATH = REPO / ".env"
if ENV_PATH.exists():
    for raw_line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if re.match(r"^[A-Z][A-Z0-9_]*$", key.strip()):
            os.environ[key.strip()] = value.strip()

from instagram.image_gen_fal import _build_fal_prompt, _fal_generate_image
from instagram.banner_compose import compose_banner


def load_products(n=3):
    p = REPO / "products" / "top-1000.csv"
    rows = []
    with p.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("Product Name") or "").strip()
            if not name:
                continue
            try:
                rating = float((row.get("Rating") or "0").strip() or "0")
            except ValueError:
                rating = 0.0
            reviews_raw = (row.get("Review Count") or "").strip()
            reviews = int("".join(ch for ch in reviews_raw if ch.isdigit()) or "0")
            amazon = (row.get("Amazon URL") or "").strip()
            if rating < 4.5 or reviews < 100 or not amazon:
                continue
            rows.append({
                "name": name,
                "slug": re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-"),
                "category": (row.get("Category") or "Best Sellers").strip(),
                "price": (row.get("Price Range") or "Check price").strip(),
                "rating": rating,
                "review_count": reviews,
                "amazon_url": amazon,
            })
            if len(rows) >= n:
                break
    return rows


def _short_review_count(n: int) -> str:
    if n >= 1000:
        return f"{n/1000:.1f}k reviews"
    return f"{n} reviews"


def caption(product: dict) -> str:
    review_line = f"⭐ {product['rating']}/5  ·  {_short_review_count(product['review_count'])}"
    return "\n".join([
        "Stop scrolling. This gadget just made our shortlist 👀",
        "",
        review_line,
        f"💰 {product['price']}",
        "",
        "Save this one for when you finally pull the trigger 💾",
        "",
        "🔗 Tap the link in our bio for the full review + best price",
        "",
        " ".join([
            "#hotproducts", "#hotproductsdaily", "#amazonfinds", "#amazonmusthaves",
            "#productreview", "#dealoftheday", "#bestofamazon",
        ]),
    ])


def main() -> int:
    products = load_products(3)
    print(f"Selected {len(products)} products")
    out_root = REPO / "generated_images" / f"fal_test_{datetime.now().date().isoformat()}"

    for idx, product in enumerate(products, start=1):
        out_dir = out_root / str(idx)
        out_dir.mkdir(parents=True, exist_ok=True)
        prompt = _build_fal_prompt(product["name"], product["category"])
        print(f"\n[{idx}/3] {product['name']}")
        print(f"  PROMPT: {prompt[:120]}...")
        img_bytes = _fal_generate_image(prompt, None)
        if not img_bytes:
            print("  FAL returned nothing")
            continue
        variant = out_dir / "variant.jpg"
        variant.write_bytes(img_bytes)
        banner = out_dir / "banner.jpg"
        compose_banner(
            {"name": product["name"], "price": product["price"], "rating": str(product["rating"])},
            str(variant),
            str(banner),
        )
        print(f"  variant -> {variant}")
        print(f"  banner  -> {banner}")
        print("\n  CAPTION:")
        print(f"  {caption(product).replace(chr(10), chr(10) + '  ')}")

    print(f"\nOutputs: {out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
