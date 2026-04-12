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
from instagram import image_gen, banner_compose

# ─── Config ──────────────────────────────────────────────────────────────────

SITE_URL        = "https://hotproductsdot.com"
CSV_PATH        = Path(__file__).parent / "products" / "top-1000.csv"
LOG_PATH        = Path(__file__).parent / "marketing-campaigns" / "post_log.csv"
IG_API_BASE     = "https://graph.facebook.com/v21.0"
ROTATION_POOL   = 60   # rotate through top-N products by affiliate potential

# ─── Helpers ─────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", text.lower()))


def _parse_bsr(raw: str) -> int | None:
    """Parse BSR string like '#1', '#1,234' into an integer rank. Returns None if unparseable."""
    cleaned = re.sub(r"[^0-9]", "", (raw or "").strip())
    return int(cleaned) if cleaned else None


def _parse_price(raw: str) -> float:
    """Parse a price string into a float, taking the lower bound of ranges.

    Handles: '$99', '$3,549-5,699', '$299-$349', 'Check price', etc.
    Returns 0.0 if unparseable.
    """
    # Extract the first number (with optional decimal) from the string
    m = re.search(r"[\d,]+(?:\.\d+)?", (raw or "").strip())
    if not m:
        return 0.0
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return 0.0


def _score_product(p: dict) -> float:
    """
    Composite score weighting:
      - Rating         (0–5)
      - Review count   (log scale — diminishing returns)
      - Price          (higher price = higher affiliate commission)
      - BSR            (lower rank = more recent sales; inverted so lower is better)

    All factors are multiplied so any zero collapses the score.
    """
    import math
    rating       = p["rating"]                          # 0–5
    review_count = max(p["review_count"], 1)            # guard log(0)
    price        = p["price_num"]                       # raw float
    bsr          = p["bsr"]                             # int or None

    # BSR factor: map rank → 0–1 where rank=1 → 1.0, rank=10000 → ~0.0
    # Using 1 / log(bsr + 1) keeps high-BSR products from dominating.
    bsr_factor = 1.0 / math.log(bsr + 2) if bsr is not None else 0.5  # neutral if missing

    return rating * math.log(review_count) * price * bsr_factor


def load_top_products(n: int | None = None) -> list[dict]:
    """
    Read CSV, filter for availability, then return top-N products ranked by
    composite score: rating × log(reviews) × price × BSR-sales-proxy.

    Availability filters (must pass all):
      - Has a non-empty Amazon URL
      - Rating ≥ 4.5
      - Review count ≥ 100
    """
    products = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = (row.get("Product Name") or "").strip()
            if not name:
                continue

            amazon_url = (row.get("Amazon URL") or "").strip()
            if not amazon_url:
                continue  # skip: no availability guarantee without a URL

            try:
                rating = float((row.get("Rating") or "0").strip() or "0")
            except ValueError:
                rating = 0.0
            if not (4.5 <= rating <= 5.0):
                continue  # skip: below quality threshold or invalid (e.g. misaligned CSV column)

            try:
                review_count = int(re.sub(r"[^0-9]", "", (row.get("Review Count") or "0")))
            except ValueError:
                review_count = 0
            if review_count < 100:
                continue  # skip: too few reviews to trust

            try:
                potential = int((row.get("Affiliate Potential") or "7").strip() or "7")
            except ValueError:
                potential = 7

            price_num = _parse_price(row.get("Price Range") or "")
            bsr       = _parse_bsr(row.get("BSR") or "")

            product = {
                "name":         name,
                "slug":         slugify(name),
                "category":     (row.get("Category") or "").strip(),
                "price":        (row.get("Price Range") or "Check price").strip(),
                "price_num":    price_num,
                "rating":       rating,
                "reviews":      str(review_count),
                "review_count": review_count,
                "potential":    potential,
                "bsr":          bsr,
                "amazon_url":   amazon_url,
            }
            product["_score"] = _score_product(product)
            products.append(product)

    products.sort(key=lambda x: x["_score"], reverse=True)
    return products[:n] if n is not None else products


def load_posted_products() -> set[str]:
    """Return product names that have been successfully posted (any platform)."""
    if not LOG_PATH.exists():
        return set()
    posted: set[str] = set()
    with open(LOG_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("Status") == "ok":
                name = (row.get("Product") or "").strip()
                if name:
                    posted.add(name)
    return posted


def filter_by_category(products: list[dict], category: str) -> list[dict]:
    """Return products matching the given category (case-insensitive)."""
    return [p for p in products if p["category"].lower() == category.lower()]


def pick_next_product(products: list[dict], force: bool = False) -> dict:
    """
    Pick the next unposted product from the pool (highest score first).

    Skips products already logged as successfully posted unless --force is used.
    Falls back to day-of-year rotation if the entire pool has been posted.
    """
    if force:
        day = date.today().timetuple().tm_yday
        return products[(day - 1) % len(products)]

    posted = load_posted_products()
    unposted = [p for p in products if p["name"] not in posted]

    if not unposted:
        print("[!] All products in pool have been posted. Cycling back from the full pool.")
        day = date.today().timetuple().tm_yday
        return products[(day - 1) % len(products)]

    skipped = len(products) - len(unposted)
    if skipped:
        print(f"   (skipping {skipped} previously posted product(s))")
    return unposted[0]


def product_page_url(product: dict) -> str:
    return f"{SITE_URL}/products/{product['slug']}/"


def product_image_url(product: dict) -> str:
    return f"{SITE_URL}/products/{product['slug']}.jpg"


def format_stars(rating: float) -> str:
    full = int(rating)
    half = rating - full >= 0.5
    return "⭐" * full + ("✨" if half else "")


# ─── Caption generators ──────────────────────────────────────────────────────

def _fmt_price(raw: str) -> str:
    """Format a raw price string with $ prefix and comma separators."""
    p = str(raw or "").strip().lstrip("$").replace(",", "")
    try:
        val = float(p)
        return f"${val:,.2f}" if val > 0 else "Check price"
    except ValueError:
        return raw if raw.startswith("$") else f"${raw}" if raw else "Check price"


def instagram_body(product: dict) -> str:
    """Post body without hashtags."""
    stars   = format_stars(product["rating"])
    price   = _fmt_price(product["price"]) if product["price"] not in ("", "N/A") else "Check price"
    reviews = product["reviews"]
    try:
        review_str = f"{int(reviews.replace(',', '')):,}"
    except (ValueError, AttributeError):
        review_str = reviews or "many"

    return "\n".join([
        f"🔥 {product['name']}",
        "",
        f"{stars} {product['rating']}/5 · {review_str} verified reviews",
        f"💰 {price}",
        "",
        f"👉 Full details + link → {product_page_url(product)}",
    ])


def instagram_tags(product: dict) -> str:
    """Hashtag block only."""
    cat_tag = "#" + re.sub(r"[^a-z0-9]", "", product["category"].lower())
    return (
        f"#hotproducts #amazonfinds #bestproducts {cat_tag} "
        "#dealoftheday #productreview #amazondeals #mustbuy #shopping"
    )


def instagram_caption(product: dict) -> str:
    return instagram_body(product) + "\n\n" + instagram_tags(product)


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

def post_instagram(product: dict, dry_run: bool = False, image_url: str | None = None) -> dict:
    """Two-step Instagram Graph API publish: create container → publish."""
    caption   = instagram_caption(product)
    image_url = image_url or product_image_url(product)

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


# ─── Draft preview ───────────────────────────────────────────────────────────

def _wsl_to_win(path: str) -> str:
    """Convert /mnt/X/... WSL path to X:\\... Windows path."""
    import re as _re
    m = _re.match(r"^/mnt/([a-z])/(.+)$", path)
    if m:
        return m.group(1).upper() + ":\\" + m.group(2).replace("/", "\\")
    return path


def _open_image(local_path: str) -> None:
    """Open the banner in the Windows default image viewer (WSL2-safe)."""
    import subprocess
    win_path = _wsl_to_win(local_path)
    try:
        subprocess.Popen(
            ["explorer.exe", win_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # non-WSL2 env — viewer open not supported, path is shown in terminal


def show_draft(
    product: dict,
    platform: str,
    body: str,
    tags: str,
    banner_local: str | None,
    banner_public: str | None,
) -> None:
    """Print a fully formatted post draft to the terminal."""
    W = 62
    caption = body + "\n\n" + tags
    char_count = len(caption)

    print()
    print("╔" + "═" * W + "╗")
    label = f"  {platform.upper()} POST DRAFT  "
    print("║" + label.center(W) + "║")
    print("╚" + "═" * W + "╝")

    # ── Image ────────────────────────────────────────────────────────────────
    print()
    print("  📸  IMAGE")
    print("  " + "─" * (W - 2))
    if banner_local:
        print(f"  Local  : {banner_local}")
        win_path = _wsl_to_win(banner_local)
        if win_path != banner_local:
            print(f"  Windows: {win_path}")
        _open_image(banner_local)
        print("  (Opening in Windows viewer...)")
    if banner_public:
        print(f"  Public : {banner_public}")

    # ── Post body ─────────────────────────────────────────────────────────────
    print()
    print("  📝  POST BODY")
    print("  " + "─" * (W - 2))
    for line in body.splitlines():
        print(f"  {line}")

    # ── Hashtags ──────────────────────────────────────────────────────────────
    print()
    print("  🏷️   HASHTAGS")
    print("  " + "─" * (W - 2))
    # wrap hashtags at ~60 chars
    words, current_line = tags.split(), ""
    for word in words:
        if len(current_line) + len(word) + 1 > 58:
            print(f"  {current_line}")
            current_line = word
        else:
            current_line = f"{current_line} {word}".strip()
    if current_line:
        print(f"  {current_line}")

    # ── Stats ─────────────────────────────────────────────────────────────────
    print()
    limit  = 2200 if platform == "instagram" else 2200
    bar_w  = 40
    filled = int(bar_w * min(char_count / limit, 1.0))
    bar    = "█" * filled + "░" * (bar_w - filled)
    print(f"  Characters: {char_count:,} / {limit:,}")
    print(f"  [{bar}]")
    print()


def ask_approval(platform: str, dry_run: bool) -> bool:
    """Prompt for go/no-go. Returns True to post, False to skip."""
    if dry_run:
        print(f"  [DRY RUN] Would post to {platform} — skipping.")
        return False
    if not sys.stdin.isatty():
        print(f"  [non-interactive] Auto-approving {platform} post.")
        return True
    try:
        ans = input(f"  Post to {platform}? [y/N]: ").strip().lower()
        return ans == "y"
    except (EOFError, KeyboardInterrupt):
        print("\n  Aborted.")
        sys.exit(0)


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
    parser.add_argument("--force",    action="store_true",
                        help="Ignore post history and pick via day-of-year rotation")
    parser.add_argument("--category", metavar="CATEGORY",
                        help="Only pick from products in this category (case-insensitive). "
                             "Use --list-categories to see available options.")
    parser.add_argument("--list-categories", action="store_true",
                        help="Print all available product categories and exit")
    args = parser.parse_args()

    # Load all qualifying products for category operations; cap to pool for normal rotation
    all_products = load_top_products()
    if not all_products:
        print("[!] No products loaded from CSV.")
        sys.exit(1)

    if args.list_categories:
        categories = sorted({p["category"] for p in all_products if p["category"]})
        print("Available categories:")
        for cat in categories:
            count = sum(1 for p in all_products if p["category"] == cat)
            print(f"  {cat} ({count} product{'s' if count != 1 else ''})")
        sys.exit(0)

    if args.category:
        filtered = filter_by_category(all_products, args.category)
        if not filtered:
            all_cats = sorted({p["category"] for p in all_products if p["category"]})
            print(f"[!] No products found for category: '{args.category}'")
            print("    Available categories:")
            for cat in all_cats:
                print(f"      {cat}")
            sys.exit(1)
        products = filtered[:ROTATION_POOL]
        print(f"Category filter  : {args.category} ({len(products)} product(s) in pool)")
    else:
        products = all_products[:ROTATION_POOL]

    product = pick_next_product(products, force=args.force)
    print(f"Today's product  : {product['name']}")
    print(f"Category         : {product['category']}")
    print(f"Rating           : {product['rating']}/5")
    print(f"Price            : {product['price']}")
    print(f"Page URL         : {product_page_url(product)}")
    print()

    # ── Image generation ─────────────────────────────────────────────────────
    chosen_image_url: str | None = None
    if os.environ.get("FAL_KEY"):
        save_dir = (
            Path(__file__).parent
            / "generated_images"
            / date.today().isoformat()
            / product["slug"]
        )
        print(">> Generating 5 image variants with fal.ai nano-banana-2...")
        try:
            variants = image_gen.generate_product_images(product, n=5, save_dir=save_dir)
            if variants:
                chosen = image_gen.pick_image(variants)
                chosen_image_url = chosen["url"]
                print(f"   Selected: [{chosen['index']}] {chosen['style']}  {chosen_image_url}")
            else:
                print("   [!] No variants generated — falling back to site image")
        except ValueError as exc:
            print(f"   [!] {exc} — falling back to site image")
        except KeyboardInterrupt:
            print("Aborted.")
            sys.exit(0)
    else:
        print(f"Image URL        : {product_image_url(product)}")
        print("   (set FAL_KEY in .env to generate custom images)")

    # ── Banner composition (HotProducts brand style) ──────────────────────────
    # Composes the product image into the branded 1080×1080 banner format.
    # Requires IMGBB_API_KEY in .env to upload the banner to a public URL.
    # Falls back to the raw fal.ai image if no upload key is configured.
    imgbb_key = os.environ.get("IMGBB_API_KEY", "")
    if imgbb_key and (chosen_image_url or True):
        source = chosen_image_url or product_image_url(product)
        banner_save_dir = (
            Path(__file__).parent
            / "generated_images"
            / date.today().isoformat()
            / product["slug"]
        )
        banner_path = str(banner_save_dir / "banner.jpg")
        print(">> Composing HotProducts branded banner...")
        try:
            banner_compose.compose_banner(product, source, banner_path)
            print(f"   Banner saved → {banner_path}")
            print("   Uploading to imgbb...")
            public_url = banner_compose.upload_to_imgbb(banner_path, imgbb_key)
            if public_url:
                chosen_image_url = public_url
                print(f"   Banner URL: {chosen_image_url}")
            else:
                print("   [!] Upload failed — using original image URL")
        except Exception as exc:
            print(f"   [!] Banner compose failed: {exc} — using original image URL")
    elif not imgbb_key:
        print("   (set IMGBB_API_KEY in .env to enable branded banner compositing)")
    print()

    results: dict[str, dict] = {}

    # ── Instagram draft + approval ────────────────────────────────────────────
    if args.platform in ("instagram", "all"):
        ig_body = instagram_body(product)
        ig_tags = instagram_tags(product)
        show_draft(
            product   = product,
            platform  = "instagram",
            body      = ig_body,
            tags      = ig_tags,
            banner_local  = banner_path if "banner_path" in dir() else None,
            banner_public = chosen_image_url,
        )
        if ask_approval("instagram", args.dry_run):
            print(">> Posting to Instagram...")
            result = post_instagram(product, dry_run=False, image_url=chosen_image_url)
            results["instagram"] = result
            if result["ok"]:
                print(f"  OK  post_id: {result.get('post_id', '')}")
            else:
                print(f"  FAIL {result['error']}")
            log_result(product, "instagram", result)
        else:
            print("  Skipped.")

    # ── TikTok draft + approval ───────────────────────────────────────────────
    if args.platform in ("tiktok", "all"):
        tt_caption = tiktok_caption(product)
        tt_body, tt_tags = (tt_caption.rsplit("\n\n", 1) + [""])[:2]
        show_draft(
            product   = product,
            platform  = "tiktok",
            body      = tt_body,
            tags      = tt_tags,
            banner_local  = banner_path if "banner_path" in dir() else None,
            banner_public = chosen_image_url,
        )
        if ask_approval("tiktok", args.dry_run):
            print(">> Posting to TikTok...")
            tik_image = chosen_image_url or product_image_url(product)
            result    = tiktok_api.post_photo([tik_image], tt_caption)
            results["tiktok"] = result
            if result["ok"]:
                print(f"  OK  publish_id: {result.get('publish_id', '')}")
            else:
                print(f"  FAIL {result['error']}")
            log_result(product, "tiktok", result)
        else:
            print("  Skipped.")

    if any(not r["ok"] for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
