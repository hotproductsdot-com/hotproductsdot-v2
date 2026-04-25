"""
Publish the 7 Instagram banners we re-rendered (after dry-run review).

For each entry:
  1. Upload the local banner JPG to ImgBB.
  2. POST to Instagram Graph API to create + publish.
  3. Append a row to marketing-campaigns/post_log.csv with the new media_id.

90-second spacing between posts to stay under Meta's burst-rate heuristics.

Usage:
  venv/bin/python scripts/publish_repost_banners.py            # dry run
  venv/bin/python scripts/publish_repost_banners.py --yes      # actually publish
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

from instagram import banner_compose, caption, poster

PREVIEW_DIR = REPO_ROOT / "generated_images" / "reposts-preview"
LOG_PATH = REPO_ROOT / "marketing-campaigns" / "post_log.csv"
SPACING_SECONDS = 90

POSTS: list[dict] = [
    {
        "slug": "canon-eos-r6-ii-camera-skip",  # not in our list
    },
]
# (replaced below — full list)

POSTS = [
    {
        "slug": "apple-airpods-pro-2nd-gen",
        "product": {
            "name": "Apple AirPods Pro 2nd Gen",
            "category": "Headphones",
            "price": "258", "rating": 4.7, "reviews": 28624,
            "bsr": 1, "potential": 8,
            "amazon_url": "https://www.amazon.com/dp/B0CHWRXH8B?tag=hotproduct033-20",
        },
    },
    {
        "slug": "yeti-tundra-45-cooler",
        "product": {
            "name": "YETI Tundra 45 Cooler",
            "category": "Outdoor & Camping",
            "price": "325", "rating": 4.7, "reviews": 4700,
            "bsr": 1, "potential": 9,
            "amazon_url": "https://www.amazon.com/dp/B07D1CFJRY?tag=hotproduct033-20",
        },
    },
    {
        "slug": "apple-ipad-pro-13-inch-m4",
        "product": {
            "name": "Apple iPad Pro 13-Inch (M4)",
            "category": "Tablets",
            "price": "976", "rating": 4.8, "reviews": 1375,
            "bsr": 1, "potential": 8,
            "amazon_url": "https://www.amazon.com/dp/B0D3J98W75?tag=hotproduct033-20",
        },
    },
    {
        "slug": "instant-pot-duo-7-in-1-electric-pressure-cooker",
        "product": {
            "name": "Instant Pot Duo 7-in-1 Electric Pressure Cooker",
            "category": "Kitchen",
            "price": "109", "rating": 4.6, "reviews": 183704,
            "bsr": 1, "potential": 9,
            "amazon_url": "https://www.amazon.com/dp/B00FLYWNYQ?tag=hotproduct033-20",
        },
    },
    {
        "slug": "apple-airpods-max",
        "product": {
            "name": "Apple AirPods Max",
            "category": "Headphones",
            "price": "449", "rating": 4.6, "reviews": 16557,
            "bsr": 1, "potential": 9,
            "amazon_url": "https://www.amazon.com/dp/B0DGJBQSJY?tag=hotproduct033-20",
        },
    },
    {
        "slug": "canon-rf-70-200mm-f-2-8",
        "product": {
            "name": "Canon RF 70-200mm f/2.8",
            "category": "Photography",
            "price": "3099", "rating": 4.7, "reviews": 1200,
            "bsr": 2, "potential": 8,
            "amazon_url": "https://www.amazon.com/dp/B0FKD5HXDJ?tag=hotproduct033-20",
        },
    },
    {
        "slug": "jbl-charge-5-portable-bluetooth-speaker",
        "product": {
            "name": "JBL Charge 5 Portable Bluetooth Speaker",
            "category": "Speakers",
            "price": "109", "rating": 4.6, "reviews": 1819,
            "bsr": 6, "potential": 9,
            "amazon_url": "https://www.amazon.com/dp/B094LS37Z4?tag=hotproduct033-20",
        },
    },
]


def _build_caption(product: dict) -> str:
    """Adapt our product dict shape to what instagram/caption.py expects."""
    price_raw = str(product.get("price", "")).replace(",", "").replace("$", "")
    try:
        price_num = float(price_raw) if price_raw else None
    except ValueError:
        price_num = None
    adapted = {
        **product,
        "stars": product.get("rating") or 0,
        "price": price_num,
    }
    return caption.generate(adapted)


def append_log(post_date: str, name: str, media_id: str) -> None:
    """Append a successful row to marketing-campaigns/post_log.csv."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not LOG_PATH.exists()
    with LOG_PATH.open("a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["Date", "Platform", "Product", "Status", "Detail"])
        writer.writerow([post_date, "instagram", name, "ok", media_id])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yes", action="store_true", help="actually upload + publish (default: dry run)")
    args = ap.parse_args()

    api_key = os.environ.get("IMGBB_API_KEY", "")
    if not api_key:
        print("[FAIL] IMGBB_API_KEY not set in .env")
        return 1

    if args.yes:
        # Skip poster.check_credentials — its GET /{user_id} read endpoint
        # requires a Page-token exchange this script doesn't do, but the
        # User token in .env has instagram_content_publish scope and works
        # for the actual publish flow. Errors on real publish are caught
        # per-post below.
        if not os.environ.get("IG_USER_ID") or not os.environ.get("IG_ACCESS_TOKEN"):
            print("[FAIL] IG_USER_ID or IG_ACCESS_TOKEN not set in .env")
            return 1
        print(f"Mode: APPLY — will publish {len(POSTS)} posts with {SPACING_SECONDS}s spacing\n")
    else:
        print(f"Mode: DRY RUN — will NOT upload or publish (pass --yes to publish)\n")

    today = date.today().strftime("%Y-%m-%d")
    successes: list[tuple[str, str]] = []
    failures: list[tuple[str, str]] = []

    for i, entry in enumerate(POSTS):
        slug = entry["slug"]
        product = {**entry["product"], "slug": slug}
        banner = PREVIEW_DIR / f"{slug}-banner.jpg"
        print(f"── [{i + 1}/{len(POSTS)}] {slug}")

        if not banner.exists():
            print(f"  [SKIP] banner not rendered at {banner}")
            failures.append((slug, "banner missing"))
            continue
        print(f"  banner: {banner.name} ({banner.stat().st_size // 1024} KB)")

        if not args.yes:
            print(f"  [dry-run] would upload to ImgBB, publish to IG, log under {today}")
            continue

        public_url = banner_compose.upload_to_imgbb(str(banner), api_key, name=f"{slug}-banner")
        if not public_url:
            print("  [FAIL] ImgBB upload failed")
            failures.append((slug, "imgbb upload failed"))
            continue
        print(f"  uploaded: {public_url}")

        cap = _build_caption(product)
        media_id, err = poster.post_image(public_url, cap)
        if err or not media_id:
            print(f"  [FAIL] publish: {err}")
            failures.append((slug, str(err)))
            continue
        print(f"  published: media_id={media_id}")

        append_log(today, product["name"], media_id)
        successes.append((slug, media_id))

        if i < len(POSTS) - 1:
            print(f"  sleeping {SPACING_SECONDS}s before next post…")
            time.sleep(SPACING_SECONDS)

    print(f"\n{'=' * 60}")
    print(f"Done. {len(successes)} OK / {len(failures)} failed")
    for slug, mid in successes:
        print(f"  OK   {slug}: {mid}")
    for slug, err in failures:
        print(f"  FAIL {slug}: {err}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
