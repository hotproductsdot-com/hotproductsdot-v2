"""
Fallback: re-render + repost Instagram banners that rendered dark-on-dark.

Usage:
  # Dry run — render fixed banners locally, print what would be deleted/posted:
  python scripts/repost_fix_dark_banners.py

  # Actually delete the old posts and publish new ones:
  python scripts/repost_fix_dark_banners.py --yes

  # Skip the API delete (if you've already deleted manually in the app):
  python scripts/repost_fix_dark_banners.py --yes --skip-delete

  # Override which slugs to process:
  python scripts/repost_fix_dark_banners.py --yes --only zeiss-otus-85mm-f-1-4

Requires (from .env):
  IG_USER_ID, IG_ACCESS_TOKEN — for publish/delete
  CLOUDINARY_URL              — for banner hosting

Lose warning: deleting a post resets engagement (likes, comments, reach) to zero.
Only run this if the posts have little engagement and a clean banner matters more.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from instagram import banner_compose, caption, poster

# Post metadata to re-render. Source image is the raw Flux variant (not the
# flattened banner, which already has text/overlays baked in).
POSTS: list[dict] = [
    {
        "slug":    "nikon-z9-ii",
        "post_id": None,  # fill in from post_log.csv / IG insights if available
        "source":  "generated_images/2026-04-12/nikon-z9-ii/variant_2_studio_dark.jpg",
        "product": {
            "name":     "Nikon Z9 II",
            "category": "Photography",
            "price":    "5296.95",
            "rating":   4.5,
            "reviews":  106,
            "bsr":      1,
            "potential": 9,
            "amazon_url": "https://www.amazon.com/dp/B09KHC4XCT?tag=hotproduct033-20",
        },
    },
    {
        "slug":    "canon-eos-r5-camera",
        "post_id": "17885956107374878",  # from marketing-campaigns/post_log.csv 2026-04-16
        "source":  "generated_images/2026-04-14/canon-eos-r5-camera/variant_2_studio_dark.jpg",
        "product": {
            "name":     "Canon EOS R5 Camera",
            "category": "Photography",
            "price":    "2799",
            "rating":   4.7,
            "reviews":  776,
            "bsr":      1,
            "potential": 9,
            "amazon_url": "https://www.amazon.com/dp/B08C68F2DX?tag=hotproduct033-20",
        },
    },
    {
        "slug":    "zeiss-otus-85mm-f-1-4",
        "post_id": "18097560736865683",  # from post_log.csv 2026-04-23
        "source":  None,  # no raw variant saved — must regenerate via image_gen_local_flux
        "product": {
            "name":     "Zeiss Otus 85mm f/1.4",
            "category": "Photography",
            "price":    "2499",
            "rating":   4.9,
            "reviews":  800,
            "bsr":      1,
            "potential": 9,
            "amazon_url": "https://www.amazon.com/dp/B0F59K7M9N?tag=hotproduct033-20",
        },
    },
]

OUT_DIR = REPO_ROOT / "generated_images" / "reposts"


def _render_banner(entry: dict) -> Path | None:
    source = entry.get("source")
    if not source:
        print(f"  [SKIP] {entry['slug']}: no raw source variant — regenerate via image_gen_local_flux.py first")
        return None
    source_path = REPO_ROOT / source
    if not source_path.exists():
        print(f"  [SKIP] {entry['slug']}: source missing at {source_path}")
        return None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{entry['slug']}-banner.jpg"
    banner_compose.compose_banner(entry["product"], str(source_path), str(out))
    return out


def _upload(banner_path: Path, slug: str) -> str | None:
    cloudinary_url = os.environ.get("CLOUDINARY_URL", "")
    if not cloudinary_url:
        print("  [!] CLOUDINARY_URL not set — cannot upload")
        return None
    return banner_compose.upload_to_cloudinary(
        str(banner_path),
        cloudinary_url,
        public_id=f"hotproducts/{slug}-banner-fixed",
    )


def process(entry: dict, *, apply: bool, skip_delete: bool) -> None:
    slug = entry["slug"]
    print(f"\n── {slug} ──")

    banner = _render_banner(entry)
    if not banner:
        return
    print(f"  banner rendered: {banner}")

    if not apply:
        print("  [dry-run] would upload, delete old post, and publish new post")
        print(f"  old post_id to delete: {entry.get('post_id') or '(none on file)'}")
        return

    public_url = _upload(banner, slug)
    if not public_url:
        print("  [FAIL] upload failed — aborting this entry")
        return
    print(f"  uploaded: {public_url}")

    post_id = entry.get("post_id")
    if post_id and not skip_delete:
        print(f"  deleting old post {post_id}...")
        ok, err = poster.delete_media(post_id)
        if ok:
            print("  deleted OK")
        else:
            print(f"  [!] delete failed: {err}")
            print("     Delete manually in the Instagram app, then re-run with --skip-delete.")
            return

    cap = caption.generate(entry["product"])
    print("  publishing new post...")
    new_id, err = poster.post_image(public_url, cap)
    if err:
        print(f"  [FAIL] publish failed: {err}")
        return
    print(f"  published: new post_id={new_id}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yes", action="store_true", help="actually delete and repost (default: dry run)")
    ap.add_argument("--skip-delete", action="store_true", help="skip the Graph API DELETE (use if already deleted manually)")
    ap.add_argument("--only", help="comma-separated slugs to process (default: all three)")
    args = ap.parse_args()

    entries = POSTS
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        entries = [e for e in POSTS if e["slug"] in wanted]

    if args.yes:
        ok, who = poster.check_credentials()
        if not ok:
            print(f"[FAIL] Instagram credentials: {who}")
            return 1
        print(f"Instagram account: {who}")
        print("Mode: APPLY — will delete old posts and publish new ones")
    else:
        print("Mode: DRY RUN (pass --yes to actually delete/repost)")

    for entry in entries:
        process(entry, apply=args.yes, skip_delete=args.skip_delete)

    return 0


if __name__ == "__main__":
    sys.exit(main())
