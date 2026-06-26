"""
Dry-render Instagram banners for the 7 posts deleted from
@hotproducts.online, using the catalog images as source.

Writes JPGs to generated_images/reposts-preview/{slug}-banner.jpg
and prints the absolute paths so the user can eyeball them before
authorizing a real publish.

Usage:
  python scripts/preview_repost_banners.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from instagram import banner_compose

OUT_DIR = REPO_ROOT / "generated_images" / "reposts-preview"

POSTS: list[dict] = [
    {
        "slug": "apple-airpods-pro-2nd-gen",
        "old_post_id": "17885493264487549",
        "product": {
            "name": "Apple AirPods Pro 2nd Gen",
            "category": "Headphones",
            "price": "258",
            "rating": 4.7,
            "reviews": 28624,
            "bsr": 1,
            "potential": 8,
            "amazon_url": "https://www.amazon.com/dp/B0CHWRXH8B?tag=hotproduct033-20",
        },
    },
    {
        "slug": "yeti-tundra-45-cooler",
        "old_post_id": "17956471269118380",
        "product": {
            "name": "YETI Tundra 45 Cooler",
            "category": "Outdoor & Camping",
            "price": "325",
            "rating": 4.7,
            "reviews": 4700,
            "bsr": 1,
            "potential": 9,
            "amazon_url": "https://www.amazon.com/dp/B07D1CFJRY?tag=hotproduct033-20",
        },
    },
    {
        "slug": "apple-ipad-pro-13-inch-m4",
        "old_post_id": "17986519535969095",
        "product": {
            "name": "Apple iPad Pro 13-Inch (M4)",
            "category": "Tablets",
            "price": "976",
            "rating": 4.8,
            "reviews": 1375,
            "bsr": 1,
            "potential": 8,
            "amazon_url": "https://www.amazon.com/dp/B0D3J98W75?tag=hotproduct033-20",
            "rembg_model": "u2net",
        },
    },
    {
        "slug": "instant-pot-duo-7-in-1-electric-pressure-cooker",
        "old_post_id": "18093351182273380",
        "product": {
            "name": "Instant Pot Duo 7-in-1 Electric Pressure Cooker",
            "category": "Kitchen",
            "price": "109",
            "rating": 4.6,
            "reviews": 183704,
            "bsr": 1,
            "potential": 9,
            "amazon_url": "https://www.amazon.com/dp/B00FLYWNYQ?tag=hotproduct033-20",
            "rembg_model": "isnet-general-use",
        },
    },
    {
        "slug": "apple-airpods-max",
        "old_post_id": "18044295059546076",
        "product": {
            "name": "Apple AirPods Max",
            "category": "Headphones",
            "price": "449",
            "rating": 4.6,
            "reviews": 16557,
            "bsr": 1,
            "potential": 9,
            "amazon_url": "https://www.amazon.com/dp/B0DGJBQSJY?tag=hotproduct033-20",
        },
    },
    {
        "slug": "canon-rf-70-200mm-f-2-8",
        "old_post_id": "18174554572400309",
        "product": {
            "name": "Canon RF 70-200mm f/2.8",
            "category": "Photography",
            "price": "3099",
            "rating": 4.7,
            "reviews": 1200,
            "bsr": 2,
            "potential": 8,
            "amazon_url": "https://www.amazon.com/dp/B0FKD5HXDJ?tag=hotproduct033-20",
            "rembg_model": "isnet-general-use",
        },
    },
    {
        "slug": "jbl-charge-5-portable-bluetooth-speaker",
        "old_post_id": "18328705333301676",
        "product": {
            "name": "JBL Charge 5 Portable Bluetooth Speaker",
            "category": "Speakers",
            "price": "109",
            "rating": 4.6,
            "reviews": 1819,
            "bsr": 6,
            "potential": 9,
            "amazon_url": "https://www.amazon.com/dp/B094LS37Z4?tag=hotproduct033-20",
        },
    },
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Rendering {len(POSTS)} banners → {OUT_DIR}\n")

    failures: list[str] = []
    for entry in POSTS:
        slug = entry["slug"]
        src = REPO_ROOT / "site" / "public" / "products" / f"{slug}.jpg"
        if not src.exists():
            print(f"  [MISS] {slug}: source image not found at {src}")
            failures.append(slug)
            continue
        out = OUT_DIR / f"{slug}-banner.jpg"
        try:
            banner_compose.compose_banner(entry["product"], str(src), str(out))
        except Exception as e:
            print(f"  [FAIL] {slug}: {e}")
            failures.append(slug)
            continue
        size_kb = out.stat().st_size // 1024
        print(f"  [OK]   {slug:<55} → {out.name}  ({size_kb} KB)")

    print()
    if failures:
        print(f"Done with {len(POSTS) - len(failures)}/{len(POSTS)} OK. Failed: {failures}")
        return 1
    print(f"All {len(POSTS)} banners rendered. Review them under:\n  {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
