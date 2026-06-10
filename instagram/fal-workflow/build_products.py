#!/usr/bin/env python3
"""Build FAL workflow product presets from @hotproductsdot.official feed + catalog."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "products" / "top-1000.csv"
OUT_PATH = Path(__file__).resolve().parent / "products.json"
FEED_DIR = REPO_ROOT / "site" / "public" / "instagram-feed"

_HOOKS = [
    "This one's flying off the shelves 🔥",
    "Everyone's talking about this 👀",
    "Found the product of the week 👇",
    "This deal is too good not to share ⚡",
    "Your next obsession just dropped 🛍️",
    "The internet can't stop buying this 📦",
    "Spotted a top pick today 👇",
    "Amazon is buzzing about this right now 🐝",
]

_CLOSERS = [
    "🔗 Link in bio to grab yours before it sells out.",
    "💬 Drop a ❤️ if you'd buy this!",
    "🛒 Tap the link in bio — your wallet will thank you later.",
    "📲 Check the link in bio for the latest price.",
    "👉 Link in bio — limited stock, act fast!",
    "💡 Link in bio. You can thank us later.",
]

_HASHTAGS = "#amazon #amazonfinds #musthave #productreview #deals #shopping #trending #viral #onlineshopping #affordablelife #hotproducts #hotproductsdotcom"


def _slugify(text: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", text.lower()))


def _star_display(stars: float | None) -> str:
    if not stars:
        return "⭐⭐⭐⭐☆"
    full = int(stars)
    half = 1 if (stars - full) >= 0.3 else 0
    empty = 5 - full - half
    return "⭐" * full + ("✨" if half else "") + "☆" * empty


def _parse_price(raw: str) -> float | None:
    m = re.search(r"[\d,]+(?:\.\d+)?", (raw or "").strip())
    if not m:
        return None
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return None


def _price_text(price: float | None) -> str:
    if not price:
        return "Check Amazon for price"
    return f"${price:,.2f} on Amazon"


def _instagram_caption(product: dict) -> str:
    slug = product["slug"]
    hook = _HOOKS[hash(slug) % len(_HOOKS)]
    closer = _CLOSERS[hash(slug + "c") % len(_CLOSERS)]
    stars = product.get("stars")
    reviews = product.get("reviews") or 0
    lines = [
        hook,
        "",
        f"✨ {product['name']}",
        "",
        f"{_star_display(stars)} {stars or '—'}/5 · {reviews:,} reviews",
        f"📦 {product.get('category', 'Amazon Pick')}",
        f"💰 {_price_text(product.get('price'))}",
        "",
        closer,
        "",
        _HASHTAGS,
    ]
    return "\n".join(lines)


def _load_catalog() -> dict[str, dict]:
    by_slug: dict[str, dict] = {}
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Product Name") or row.get("name") or "").strip()
            if not name:
                continue
            slug = _slugify(name)
            stars_raw = (row.get("Rating") or row.get("stars") or "").strip()
            reviews_raw = (
                row.get("Review Count") or row.get("Reviews") or row.get("reviews") or "0"
            ).strip()
            try:
                stars = float(stars_raw) if stars_raw else None
            except ValueError:
                stars = None
            try:
                reviews = int(re.sub(r"[^0-9]", "", reviews_raw) or "0")
            except ValueError:
                reviews = 0
            by_slug[slug] = {
                "slug": slug,
                "name": name,
                "category": (row.get("Category") or row.get("category") or "").strip(),
                "amazon_url": (row.get("Amazon URL") or row.get("amazon_url") or "").strip(),
                "stars": stars,
                "reviews": reviews,
                "price": _parse_price(
                    row.get("Price Range") or row.get("Price") or row.get("price") or ""
                ),
            }
    return by_slug


def _fetch_amazon_image_url(amazon_url: str) -> str | None:
    if not amazon_url:
        return None
    try:
        resp = requests.get(
            amazon_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=15,
        )
        if not resp.ok:
            return None
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            resp.text,
        )
        if m:
            return m.group(1)
        m = re.search(
            r'"large"\s*:\s*"(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"',
            resp.text,
        )
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _feed_slugs() -> list[str]:
    slugs = []
    for path in sorted(FEED_DIR.glob("*.jpg")):
        slugs.append(path.stem)
    return slugs


def build() -> list[dict]:
    catalog = _load_catalog()
    products = []
    for slug in _feed_slugs():
        product = catalog.get(slug)
        if not product:
            print(f"  skip {slug}: not in catalog")
            continue
        amazon_image_url = _fetch_amazon_image_url(product["amazon_url"])
        if not amazon_image_url:
            print(f"  skip {slug}: no Amazon image URL")
            continue
        products.append(
            {
                "slug": slug,
                "name": product["name"],
                "category": product["category"],
                "amazon_url": product["amazon_url"],
                "amazon_image_url": amazon_image_url,
                "instagram_post": _instagram_caption(product),
                "instagram_feed_image": f"https://hotproductsdot.com/instagram-feed/{slug}.jpg",
            }
        )
        print(f"  OK {slug}")
    return products


def main() -> None:
    products = build()
    payload = {
        "source": "https://www.instagram.com/hotproductsdot.official",
        "workflow": "hotproducts-instagram-ad-creative",
        "products": products,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(products)} products to {OUT_PATH}")


if __name__ == "__main__":
    main()
