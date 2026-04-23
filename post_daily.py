#!/usr/bin/env python3
"""
Daily social media poster for HotProducts.

Picks one product per day (rotating through the top 60 by affiliate potential)
and posts it to Instagram and TikTok.

Usage:
    python post_daily.py [--dry-run] [--platform instagram|tiktok|all]
        [--catalog-image-only] [--on-empty-ai-images catalog|abort]
        [-v|-q] [--log-file PATH]

Instagram publishing: Meta often cannot fetch third-party CDNs (e.g. ImgBB). The script writes a
1080×1080 JPEG under site/public/instagram-feed/{slug}.jpg. That URL must return HTTP 200 image/jpeg
on the public web (git push + deploy). Use INSTAGRAM_MEDIA_BASE_URL for a preview host, or
INSTAGRAM_RAW_GITHUB_BASE (optional) — if unset, the script tries to infer
https://raw.githubusercontent.com/OWNER/REPO/BRANCH from `git remote origin` so you can
`git push` the instagram-feed JPEG (public repo) without waiting for Hostinger deploy.
ImgBB is tried last: it often passes our HTTP probe but Meta’s fetcher still rejects it.

Required GitHub Actions secrets (set in repo Settings → Secrets):
    IG_USER_ID          — Instagram Business Account ID (numeric string)
    IG_ACCESS_TOKEN     — Meta Graph API long-lived page access token
                          (instagram_basic + instagram_content_publish permissions)
    TIKTOK_ACCESS_TOKEN — TikTok Content Posting API access token
                          (video.publish scope)
"""

import argparse
import csv
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

import tiktok_api
from instagram import image_gen, image_gen_gemini, banner_compose

# Optional: AI-powered affiliate tools (guarded import)
try:
    from instagram import affiliate_tools as _affiliate_tools
    _AFFILIATE_TOOLS_AVAILABLE = True
except ImportError:
    _AFFILIATE_TOOLS_AVAILABLE = False

# Optional: local FLUX generation (imported conditionally based on CLI flag)

# ─── Config ──────────────────────────────────────────────────────────────────

SITE_URL        = "https://hotproductsdot.com"
CSV_PATH        = Path(__file__).parent / "products" / "top-1000.csv"
LOG_PATH        = Path(__file__).parent / "marketing-campaigns" / "post_log.csv"
ROTATION_POOL   = 60   # rotate through top-N products by affiliate potential

logger = logging.getLogger(__name__)


def configure_logging(*, verbose: bool, quiet: bool, log_file: str | None) -> None:
    """Console + optional file; idempotent for repeated calls in tests."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    fmt = "%(asctime)s %(levelname)s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    for h in handlers:
        h.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    for h in handlers:
        root.addHandler(h)
    # Library noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


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
      - Price          (log scale — high-end items still win, but a $50 product
                        isn't 50× behind a $2500 one. Prevents the rotation pool
                        from being dominated by cameras and gaming PCs.)
      - BSR            (lower rank = more recent sales; inverted so lower is better)

    All factors are multiplied so any zero collapses the score.
    """
    rating       = p["rating"]                          # 0–5
    review_count = max(p["review_count"], 1)            # guard log(0)
    price        = max(p["price_num"], 1.0)             # guard log(0)
    bsr          = p["bsr"]                             # int or None

    # BSR factor: map rank → 0–1 where rank=1 → 1.0, rank=10000 → ~0.0
    # Using 1 / log(bsr + 1) keeps high-BSR products from dominating.
    bsr_factor = 1.0 / math.log(bsr + 2) if bsr is not None else 0.5  # neutral if missing

    return rating * math.log(review_count) * math.log(price + 1) * bsr_factor


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


CATEGORY_COOLDOWN = 3  # don't reuse a category that appeared in the last N successful posts


def _recent_categories(products: list[dict], n: int = CATEGORY_COOLDOWN) -> set[str]:
    """Return the categories of the last n successfully posted products."""
    if not LOG_PATH.exists():
        return set()
    name_to_cat = {p["name"]: p["category"] for p in products}
    try:
        with open(LOG_PATH, newline="", encoding="utf-8") as f:
            ok_rows = [r for r in csv.reader(f) if len(r) >= 4 and r[3] == "ok"]
        return {name_to_cat[r[2]] for r in ok_rows[-n:] if r[2] in name_to_cat}
    except Exception:
        return set()


def pick_next_product(products: list[dict], force: bool = False) -> dict:
    """
    Pick the next unposted product from the pool with category diversity.

    Order of preference:
      1. Top-scoring unposted product whose category has NOT appeared in
         the last CATEGORY_COOLDOWN successful posts (prevents "5 cameras
         in a row" when cameras dominate the score).
      2. Top-scoring unposted product (cooldown unsatisfiable).
      3. Day-of-year rotation through the full pool (everything posted).
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

    recent_cats = _recent_categories(products)
    diverse = [p for p in unposted if p["category"] not in recent_cats]
    if diverse:
        if recent_cats:
            print(f"   (avoiding recent categories: {', '.join(sorted(recent_cats))})")
        return diverse[0]
    return unposted[0]


def product_page_url(product: dict) -> str:
    return f"{SITE_URL}/products/{product['slug']}/"


def product_image_url(product: dict) -> str:
    return f"{SITE_URL}/products/{product['slug']}.jpg"


def _instagram_media_origin() -> str:
    """Public origin for /instagram-feed/… JPEGs (production or preview deploy)."""
    raw = (os.environ.get("INSTAGRAM_MEDIA_BASE_URL") or SITE_URL).strip().rstrip("/")
    return raw or SITE_URL.rstrip("/")


def prepare_instagram_site_feed_jpeg(product: dict, banner_path: str | None) -> tuple[str | None, str | None]:
    """
    Write site/public/instagram-feed/{slug}.jpg (1080×1080, Instagram-safe aspect ratio).

    Prefer the composed banner file when present; otherwise build a square crop from the
    catalog product JPG. Meta can fetch this URL from your domain (after deploy).

    Returns (public_https_url, local_dest_path) or (None, None) if site/ tree is missing.
    """
    repo_root = Path(__file__).resolve().parent
    site_public = repo_root / "site" / "public"
    if not site_public.is_dir():
        logger.warning("No site/public — cannot write instagram-feed mirror (clone layout expected)")
        return None, None

    dest_dir = site_public / "instagram-feed"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{product['slug']}.jpg"

    try:
        if banner_path and Path(banner_path).is_file():
            shutil.copy2(banner_path, dest)
            logger.info("Instagram feed mirror: copied banner → %s", dest)
        else:
            banner_compose.download_square_instagram_feed_jpeg(product_image_url(product), dest)
            logger.info("Instagram feed mirror: square crop from catalog → %s", dest)
    except Exception as exc:
        logger.exception("Instagram feed mirror failed: %s", exc)
        print(f"   [!] Could not write site/instagram-feed JPEG: {exc}")
        return None, None

    url = f"{_instagram_media_origin()}/instagram-feed/{product['slug']}.jpg"
    print(
        "   Instagram feed JPEG (Meta must GET this as image/jpeg, not 404 HTML):\n"
        f"      file: {dest}\n"
        f"      URL:  {url}\n"
        "      → git add this file && git push (public repo). Raw URL is inferred from `git remote`\n"
        "        when INSTAGRAM_RAW_GITHUB_BASE is unset. Deploy the site too if you use /instagram-feed/ there."
    )
    return url, str(dest)


def infer_github_raw_root_from_git(repo_root: Path) -> str | None:
    """
    Build https://raw.githubusercontent.com/OWNER/REPO/BRANCH from git remote (HTTPS or SSH).
    Returns None if not a GitHub repo, git missing, or parse fails.
    """
    try:
        remote = subprocess.check_output(
            ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    if "github.com" not in remote:
        return None
    m = re.search(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?\s*$", remote)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    try:
        branch = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        branch = "main"
    if not branch or branch == "HEAD":
        branch = "main"
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}"


def instagram_raw_github_feed_url(slug: str) -> str | None:
    """
    Raw GitHub URL for site/public/instagram-feed/{slug}.jpg.

    Uses INSTAGRAM_RAW_GITHUB_BASE if set (branch root, no trailing slash), else infers from git.
    """
    repo_root = Path(__file__).resolve().parent
    base = (os.environ.get("INSTAGRAM_RAW_GITHUB_BASE") or "").strip().rstrip("/")
    inferred = False
    if not base:
        base = infer_github_raw_root_from_git(repo_root) or ""
        inferred = bool(base)
    if not base:
        return None
    if inferred:
        logger.info("Inferred GitHub raw base from git: %s", base)
    return f"{base}/site/public/instagram-feed/{slug}.jpg"


def _is_imgbb_url(url: str) -> bool:
    u = (url or "").lower()
    return "i.ibb.co" in u or "ibb.co/" in u


_META_FETCH_UA = (
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
)


def probe_instagram_image_url(url: str, timeout: int = 20) -> tuple[bool, str]:
    """
    Check whether Meta's crawler can plausibly use this URL (HTTP 200, image/jpeg or image/png).
    HEAD is tried first; GET with stream on 405/501 or missing content-type.
    """
    headers = {"User-Agent": _META_FETCH_UA}
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True, headers=headers)
        status = r.status_code
        ct = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()

        if status in (405, 501) or not ct:
            r = requests.get(url, timeout=timeout, allow_redirects=True, headers=headers, stream=True)
            status = r.status_code
            ct = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            r.close()

        if status != 200:
            return False, f"HTTP {status} (Instagram needs 200 + image/jpeg or image/png; got {ct!r})"
        if ct not in ("image/jpeg", "image/jpg", "image/png"):
            return False, f"HTTP {status} but Content-Type={ct!r} — often a 404 HTML page, not an image"
        return True, f"HTTP {status} {ct}"
    except requests.RequestException as exc:
        return False, f"fetch error: {exc}"


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
        raw_s = str(raw or "").strip()
        if not raw_s:
            return "Check price"
        return raw_s if raw_s.startswith("$") else raw_s


# ── Hook templates ───────────────────────────────────────────────────────────
# Used when no AI hook is available. First line of caption — IG truncates
# the feed preview around ~125 chars, so keep these short and punchy.
INSTAGRAM_HOOK_TEMPLATES = (
    # Curiosity / contrarian
    "Stop scrolling. This {noun} just made our shortlist 👀",
    "Why is nobody talking about this {noun}? 🤔",
    "Wasn't expecting THIS from {a_noun} 😳",
    "Hot take: this might be the best {noun} on Amazon right now 🔥",
    # Social proof
    "{review_count_short}+ reviewers can't be wrong about this one 🔥",
    "{rating}★ across {review_count_short} reviews. This {noun} hits different.",
    "When {review_count_short} buyers all say the same thing, you listen 👂",
    # FOMO / scarcity
    "Trending hard right now and we finally get why ⬇️",
    "Heads up: this keeps selling out 🚨",
    # Problem-solution
    "If you've been hunting for the right {noun}, this is it ⤵️",
    "This is the {noun} you didn't know you needed 🎯",
)

# Singular noun phrases that read naturally inside the hook templates.
# "the right ___", "this ___ hits different", "Wasn't expecting THIS from a ___"
CATEGORY_NOUN = {
    "photography":  "camera pick",
    "camera":       "camera pick",
    "audio":        "audio pick",
    "headphones":   "pair of headphones",
    "speakers":     "speaker setup",
    "computers":    "tech pick",
    "gaming":       "gaming setup",
    "smart home":   "smart home device",
    "kitchen":      "kitchen tool",
    "appliances":   "appliance",
    "fitness":      "workout pick",
    "health":       "wellness pick",
    "beauty":       "beauty pick",
    "home":         "home find",
    "outdoor":      "outdoor pick",
    "pet":          "pet must-have",
    "tools":        "tool",
    "automotive":   "car upgrade",
    "office":       "desk upgrade",
    "toys":         "toy",
    "baby":         "baby essential",
}

# ── Hashtag strategy ─────────────────────────────────────────────────────────
# Mix of niche (high-intent, lower competition) + mid-tier + brand.
# IG's sweet spot is 8–12 tags; we ship 10.
NICHE_HASHTAGS_BY_CATEGORY = {
    "photography":  ["#cameragear",  "#photographyequipment", "#photogear"],
    "camera":       ["#cameragear",  "#photographyequipment", "#photogear"],
    "audio":        ["#audiogear",   "#audiophile",            "#headphones"],
    "headphones":   ["#audiogear",   "#audiophile",            "#headphones"],
    "speakers":     ["#audiogear",   "#hifi",                  "#speakerlovers"],
    "computers":    ["#pcsetup",     "#techgear",              "#desktopsetup"],
    "gaming":       ["#gamingsetup", "#pcgaming",              "#gamergear"],
    "smart home":   ["#smarthome",   "#smarthomedevices",      "#hometech"],
    "kitchen":      ["#kitchengadgets", "#kitchentools",       "#kitchenmusthaves"],
    "appliances":   ["#kitchengadgets", "#smallappliances",    "#kitchenmusthaves"],
    "fitness":      ["#fitnessgear", "#homegym",               "#workoutgear"],
    "health":       ["#wellnessfinds","#healthgadgets",        "#selfcaretools"],
    "beauty":       ["#beautyfinds", "#skincareroutine",       "#beautygadgets"],
    "home":         ["#homefinds",   "#homemusthaves",         "#homedecor"],
    "outdoor":      ["#outdoorgear", "#campingessentials",     "#adventuregear"],
    "pet":          ["#petproducts", "#petlovers",             "#petsofinstagram"],
    "tools":        ["#diytools",    "#workshopgear",          "#handytools"],
    "automotive":   ["#cargear",     "#caraccessories",        "#autodetailing"],
    "office":       ["#officesetup", "#deskgoals",             "#workfromhomesetup"],
    "toys":         ["#toysforkids", "#kidsmusthaves",         "#kidstoys"],
    "baby":         ["#babymusthaves","#newmom",               "#parentingtips"],
}
MID_TIER_HASHTAGS = (
    "#amazonfinds", "#amazonmusthaves", "#productreview",
    "#dealoftheday", "#bestofamazon",
)
BRAND_HASHTAGS = ("#hotproducts", "#hotproductsdaily")


def _short_review_count(raw: str) -> str:
    """Compact display: 1234 → '1.2k', 800 → '800'."""
    try:
        n = int(str(raw).replace(",", "").strip())
    except (ValueError, AttributeError):
        return str(raw or "many")
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def _pick_hook_template(product: dict) -> str:
    """Deterministic per-day-per-product so the same product on the same day reads identically."""
    seed = f"{product.get('slug', '')}|{date.today().isoformat()}"
    idx = abs(hash(seed)) % len(INSTAGRAM_HOOK_TEMPLATES)
    return INSTAGRAM_HOOK_TEMPLATES[idx]


def _render_hook(product: dict) -> str:
    template = _pick_hook_template(product)
    category = product.get("category", "product")
    noun = CATEGORY_NOUN.get(category.lower().strip(), f"{category.lower()} pick")
    article = "an" if noun[:1].lower() in "aeiou" else "a"
    return template.format(
        category=category,
        category_lower=category.lower(),
        noun=noun,
        a_noun=f"{article} {noun}",
        rating=product.get("rating", ""),
        review_count_short=_short_review_count(product.get("reviews", "")),
        name=product.get("name", ""),
    )


def instagram_body(product: dict, *, ai_hook: str | None = None, ai_cta: str | None = None) -> str:
    """IG caption body. Hook-driven first line + social proof + bio CTA + optional AI CTA.

    IG caption URLs are NOT clickable, so we drive traffic to bio link instead.
    """
    stars   = format_stars(product["rating"])
    price   = _fmt_price(product["price"]) if product["price"] not in ("", "N/A") else "Check price"
    review_str = _short_review_count(product["reviews"])

    hook = (ai_hook or _render_hook(product)).strip()

    lines = [
        hook,
        "",
        f"{stars} {product['rating']}/5 · {review_str} reviews",
        f"💰 {price}",
        "",
        ai_cta.strip() if ai_cta else "Save this one for when you finally pull the trigger 💾",
        "",
        "🔗 Tap the link in our bio for the full review + best price",
    ]
    return "\n".join(lines)


def instagram_tags(product: dict) -> str:
    """Hashtag block: 3 niche + 5 mid-tier + 2 brand = 10 tags (IG sweet spot)."""
    category_key = product.get("category", "").lower().strip()
    niche = NICHE_HASHTAGS_BY_CATEGORY.get(category_key)
    if not niche:
        # Fallback: build a tag from category slug.
        slug = re.sub(r"[^a-z0-9]", "", category_key) or "products"
        niche = [f"#{slug}", "#amazonproducts", "#trendingnow"]
    return " ".join((*niche, *MID_TIER_HASHTAGS, *BRAND_HASHTAGS))


def instagram_caption(product: dict) -> str:
    return instagram_body(product) + "\n\n" + instagram_tags(product)


# ── First-comment templates ──────────────────────────────────────────────────
# Posted as the first comment by @hotproductsdot.official right after the
# main post publishes. Drives (a) bio-link taps via a second CTA and
# (b) replies via an open question — both are algorithmic engagement signals.
INSTAGRAM_FIRST_COMMENT_TEMPLATES = (
    "🔗 Full review + best price link in bio!\n\nWould you grab this {noun} or is there something better you'd go with instead? 👀",
    "🛒 Amazon link + our full review: link in bio\n\nBe honest — {price} for this {noun}: yay or nay? 🤔",
    "🔥 We put this {noun} through the wringer — full breakdown on the site (link in bio)\n\nWhat's the last {noun} you actually loved? Drop it below 👇",
    "🔗 Tap the bio link for the Amazon deal + our full review\n\nTag someone who NEEDS this in their life 🏷️",
    "💬 Full review + current Amazon price: link in bio\n\nFrom 1–10, how hyped are you about this one? 👇",
)


def instagram_first_comment(product: dict) -> str:
    """First auto-comment text. Rotated deterministically per product+date."""
    seed = f"comment|{product.get('slug', '')}|{date.today().isoformat()}"
    idx = abs(hash(seed)) % len(INSTAGRAM_FIRST_COMMENT_TEMPLATES)
    template = INSTAGRAM_FIRST_COMMENT_TEMPLATES[idx]
    noun = CATEGORY_NOUN.get(
        product.get("category", "").lower().strip(),
        f"{product.get('category', 'product').lower()} pick",
    )
    price = _fmt_price(product["price"]) if product.get("price") not in ("", "N/A", None) else "this price"
    return template.format(noun=noun, price=price)


def tiktok_caption(product: dict, *, ai_hook: str | None = None, ai_cta: str | None = None) -> str:
    """TikTok caption. Optionally inject AI hook and CTA."""
    price   = product["price"] if product["price"] not in ("", "N/A") else "Check price"
    cat_slug = re.sub(r"[^a-z0-9]", "", product["category"].lower())
    cat_tag = "#" + (cat_slug or "products")

    lines = [
        ai_hook or f"🔥 {product['name']}",  # use AI hook if provided
        f"⭐ {product['rating']}/5  💰 {price}",
        f"🔗 {product_page_url(product)}",
        "",
    ]

    if ai_cta:
        lines.append(ai_cta)
        lines.append("")

    lines.append(f"#hotproducts #amazonfinds #TikTokMadeMeBuyIt {cat_tag} #dealoftheday")

    return "\n".join(lines)


# ─── Instagram ───────────────────────────────────────────────────────────────

def _instagram_rejected_image_fetch(err: dict) -> bool:
    """
    True when Meta could not download image_url (misleading copy: 'Only photo or video...').
    See OAuthException code 9004 / error_subcode 2207052.
    """
    msg = (err.get("message") or "").lower()
    code = err.get("code")
    sub = err.get("error_subcode")
    if sub == 2207052 or code == 9004:
        return True
    if "only photo or video" in msg:
        return True
    if "could not retrieve media" in msg or "media download" in msg:
        return True
    return False


def _instagram_try_next_image_url(err: dict) -> bool:
    """True if another image_url might succeed (CDN fetch failure or unsupported aspect ratio)."""
    if _instagram_rejected_image_fetch(err):
        return True
    return "aspect ratio" in (err.get("message") or "").lower()


def post_instagram(
    product: dict,
    dry_run: bool = False,
    image_url: str | None = None,
    image_urls: tuple[str, ...] | list[str] | None = None,
) -> dict:
    """Two-step Instagram Graph API publish: create container → publish."""
    caption = instagram_caption(product)
    if image_urls is not None:
        raw = list(image_urls)
    else:
        raw = [image_url or product_image_url(product)]

    urls: list[str] = []
    seen: set[str] = set()
    for u in raw:
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    if not urls:
        urls = [product_image_url(product)]

    if dry_run:
        print(f"[DRY RUN] Instagram\n  try URLs: {urls}\n  caption:\n{caption}\n")
        return {"ok": True, "dry_run": True}

    user_id = os.environ.get("IG_USER_ID", "")
    token   = os.environ.get("IG_ACCESS_TOKEN", "")

    if not user_id or not token:
        return {"ok": False, "error": "Missing IG_USER_ID or IG_ACCESS_TOKEN env var"}

    api_base = "https://graph.instagram.com/v21.0" if token.startswith("IG") else "https://graph.facebook.com/v21.0"

    # Drop URLs that clearly are not fetchable as JPEG/PNG (e.g. 404 HTML on production).
    verified: list[str] = []
    probe_lines: list[str] = []
    for u in urls:
        ok, detail = probe_instagram_image_url(u)
        probe_lines.append(f"  {u}\n    → {detail}")
        if ok:
            verified.append(u)
        else:
            logger.warning("Instagram URL probe failed: %s — %s", u, detail)

    if not verified:
        return {
            "ok": False,
            "error": (
                "No image URL passes a Meta-style fetch check (HTTP 200 + image/jpeg or image/png):\n"
                + "\n".join(probe_lines)
                + f"\n\nPush site/public/instagram-feed/{product['slug']}.jpg to GitHub (public repo) "
                "and `git push`, or deploy it on your site. Raw GitHub URLs are auto-inferred from "
                "`git remote` when INSTAGRAM_RAW_GITHUB_BASE is unset."
            ),
        }

    if len(verified) < len(urls):
        print("  [!] Some image URLs were skipped (not publicly reachable as JPEG/PNG). Trying:")
        for u in verified:
            print(f"      • {u}")

    urls = verified

    # Step 1 — create media container (site + raw GitHub before ImgBB — Meta often blocks ImgBB anyway)
    d1: dict = {}
    for i, attempt_url in enumerate(urls):
        try:
            r1 = requests.post(
                f"{api_base}/{user_id}/media",
                data={"image_url": attempt_url, "caption": caption, "access_token": token},
                timeout=30,
            )
            d1 = r1.json()
        except requests.RequestException as exc:
            return {"ok": False, "error": str(exc)}

        if "error" not in d1:
            if i > 0:
                logger.info("Instagram /media succeeded with URL #%s: %s", i + 1, attempt_url)
            break

        err = d1["error"]
        msg = err.get("message", str(err))
        if not _instagram_try_next_image_url(err):
            return {"ok": False, "error": msg}

        logger.warning("Instagram /media rejected URL %s: %s", attempt_url, msg)
        if i + 1 < len(urls):
            print(f"  [!] Trying alternate image URL ({i + 2}/{len(urls)})…")
    else:
        last_msg = (d1.get("error") or {}).get("message", "All Instagram image URLs were rejected")
        slug = product["slug"]
        if urls and all(_is_imgbb_url(u) for u in urls):
            extra = (
                f"\n\nImgBB often returns HTTP 200 to our probe, but Meta’s servers still reject i.ibb.co. "
                f"Push `site/public/instagram-feed/{slug}.jpg` to your public GitHub default branch, then "
                f"re-run this script (it tries raw.githubusercontent.com before ImgBB when `git remote` is GitHub)."
            )
        else:
            extra = (
                "\n\nEnsure at least one URL is raw.githubusercontent.com (git push) or your live site "
                "returning 200 image/jpeg — Meta frequently blocks ImgBB."
            )
        return {"ok": False, "error": f"{last_msg}{extra}"}

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

    media_id = d2.get("id", "")

    # Step 3 — auto-reply first comment to drive engagement + surface a second CTA.
    # Comment failure is non-fatal: the post is already live, so we log and move on.
    first_comment = instagram_first_comment(product)
    if first_comment:
        try:
            r3 = requests.post(
                f"{api_base}/{media_id}/comments",
                data={"message": first_comment, "access_token": token},
                timeout=30,
            )
            d3 = r3.json()
            if "error" in d3:
                logger.warning("First comment failed: %s", d3["error"].get("message", d3["error"]))
            else:
                logger.info("First comment posted id=%s", d3.get("id", ""))
        except requests.RequestException as exc:
            logger.warning("First comment request error: %s", exc)

    return {"ok": True, "post_id": media_id, "platform": "instagram"}


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
    # Instagram captions and TikTok Content Posting titles both cap at 2200 (see tiktok_api.py).
    limit = 2200
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
    parser.add_argument(
        "--catalog-image-only",
        action="store_true",
        help="Skip ModelsLab generation; use the on-site product JPG (ImgBB banner still uses it if configured).",
    )
    parser.add_argument(
        "--banner-only",
        action="store_true",
        help="Skip AI image variant generation (banner, studio_dark, etc.); compose and post the banner only.",
    )
    parser.add_argument(
        "--use-local-flux",
        action="store_true",
        help="Use local FLUX.1 [schnell] for image generation (GTX 1070 compatible). "
             "Requires: pip install -r requirements-flux.txt; First run downloads ~5.5GB model.",
    )
    parser.add_argument(
        "--on-empty-ai-images",
        choices=("catalog", "abort"),
        default="catalog",
        metavar="MODE",
        help="When GEMINI_API_KEY is set and generation yields no variants: 'catalog' (default) uses site image; "
             "'abort' exits with an error.",
    )
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument("-v", "--verbose", action="store_true", help="Debug logging to stderr")
    log_group.add_argument("-q", "--quiet", action="store_true", help="Only warnings and errors on stderr")
    parser.add_argument("--log-file", metavar="PATH", help="Append logs to this file (UTF-8)")
    args = parser.parse_args()

    configure_logging(verbose=args.verbose, quiet=args.quiet, log_file=args.log_file)
    logger.info("post_daily start platform=%s dry_run=%s", args.platform, args.dry_run)

    # Set when branded banner compositing runs (ImgBB path).
    banner_path: str | None = None

    # Load all qualifying products for category operations; cap to pool for normal rotation
    all_products = load_top_products()
    if not all_products:
        logger.error("No products loaded from CSV at %s", CSV_PATH)
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
    logger.info(
        "Selected product name=%r slug=%s category=%r force=%s",
        product["name"],
        product["slug"],
        product["category"],
        args.force,
    )
    print(f"Today's product  : {product['name']}")
    print(f"Category         : {product['category']}")
    print(f"Rating           : {product['rating']}/5")
    print(f"Price            : {product['price']}")
    print(f"Page URL         : {product_page_url(product)}")
    print()

    # ── Image generation ─────────────────────────────────────────────────────
    chosen_image_url: str | None = None
    if args.catalog_image_only:
        logger.info("Skipping ModelsLab (--catalog-image-only); image source=catalog")
        print(">> Using catalog product image only (--catalog-image-only).")
        print(f"   Image URL: {product_image_url(product)}")
    elif args.use_local_flux:
        # Use local FLUX.1 [schnell] for image generation (GTX 1070 compatible)
        from instagram import image_gen_local_flux
        save_dir = (
            Path(__file__).parent
            / "generated_images"
            / date.today().isoformat()
            / product["slug"]
        )
        print(">> Generating 5 image variants with local FLUX.1 [schnell]...")
        print("   ⚠️  WARNING: GTX 1070 will be SLOW (30-45 sec per image, ~2-4 min total)")
        logger.info("Local FLUX image generation save_dir=%s", save_dir)
        try:
            variants = image_gen_local_flux.generate_product_images(product, n=5, save_dir=save_dir)
            if variants:
                chosen = image_gen.pick_image(variants)
                if chosen is None:
                    logger.info("No AI variant selected (picker 0); image source=catalog")
                    chosen_image_url = None
                    print("   Using catalog site photo (no AI variant selected).")
                else:
                    chosen_image_url = chosen["url"]
                    logger.info("Selected image style=%s url=%s", chosen.get("style"), chosen_image_url)
                    print(f"   ✓ Selected variant: {chosen.get('style', 'unknown')}")
            else:
                logger.warning("No image variants generated")
                if args.on_empty_ai_images == "abort":
                    logger.error("Generation failed; aborting (--on-empty-ai-images abort)")
                    print("[!] Image generation failed and --on-empty-ai-images abort is set. Exiting.")
                    sys.exit(1)
                chosen_image_url = None
                print("   ✗ Generation failed; using catalog image.")
        except Exception as exc:
            logger.exception("Local FLUX generation error: %s", exc)
            if args.on_empty_ai_images == "abort":
                print(f"[!] Generation error: {exc}")
                print("    Exiting (--on-empty-ai-images abort).")
                sys.exit(1)
            chosen_image_url = None
            print(f"   ✗ Generation error: {exc}")
            print("   Using catalog image instead.")
    elif os.environ.get("GEMINI_API_KEY"):
        save_dir = (
            Path(__file__).parent
            / "generated_images"
            / date.today().isoformat()
            / product["slug"]
        )
        print(">> Generating 5 image variants with Google Gemini (Nano Banana)...")
        logger.info("Gemini image generation save_dir=%s", save_dir)
        try:
            variants = image_gen_gemini.generate_product_images(product, n=5, save_dir=save_dir)
            if variants:
                chosen = image_gen_gemini.pick_image(variants)
                if chosen is None:
                    logger.info("No AI variant selected (picker 0); image source=catalog")
                    chosen_image_url = None
                    print("   Using catalog site photo (no AI variant selected).")
                else:
                    chosen_image_url = chosen["local_path"]
                    logger.info(
                        "AI image selected index=%s style=%s local_path=%s",
                        chosen["index"],
                        chosen["style"],
                        chosen_image_url,
                    )
                    print(f"   Selected: [{chosen['index']}] {chosen['style']}  {chosen_image_url}")
            else:
                logger.warning("Gemini returned no variants (empty list)")
                print("   [!] No variants generated — falling back to site image")
                if args.on_empty_ai_images == "abort":
                    logger.error("Exiting (--on-empty-ai-images=abort)")
                    print("[!] Aborting because no AI images were produced.")
                    sys.exit(1)
        except ValueError as exc:
            logger.warning("Gemini skipped: %s", exc)
            print(f"   [!] {exc} — falling back to site image")
        except KeyboardInterrupt:
            logger.info("Interrupted during image generation")
            print("Aborted.")
            sys.exit(0)
    else:
        logger.info("GEMINI_API_KEY unset; image source=catalog")
        print(f"Image URL        : {product_image_url(product)}")
        print("   (set GEMINI_API_KEY in .env to generate custom images)")

    # ── Banner composition (HotProducts brand style) ──────────────────────────
    # Composes the product image into the branded 1080×1080 banner format.
    # Requires IMGBB_API_KEY in .env to upload the banner to a public URL.
    # Falls back to the generated/site image if no upload key is configured.
    cloudinary_url = os.environ.get("CLOUDINARY_URL", "")
    # Cloudinary only — Meta's Graph API reliably accepts res.cloudinary.com.
    # No ImgBB fallback: Meta routinely rejects i.ibb.co URLs, so a fallback would
    # produce silent post failures. Fail loud if Cloudinary isn't configured/working.
    if cloudinary_url:
        source = chosen_image_url or product_image_url(product)
        logger.debug("Banner compose source URL=%s", source)
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
            print("   Uploading to Cloudinary...")
            public_url = banner_compose.upload_to_cloudinary(
                banner_path,
                cloudinary_url,
                public_id=f"hotproducts/{product['slug']}-banner",
            )
            if public_url:
                chosen_image_url = public_url
                logger.info("Cloudinary upload OK public_url=%s", public_url)
                print(f"   Banner URL: {chosen_image_url}")
            else:
                chosen_image_url = None
                logger.warning("Cloudinary upload returned no URL")
                print("   [!] Cloudinary upload failed — Instagram post will be skipped")
        except Exception as exc:
            chosen_image_url = None
            logger.exception("Banner compose failed: %s", exc)
            print(f"   [!] Banner compose failed: {exc} — Instagram post will be skipped")
    else:
        chosen_image_url = None
        print("   [!] CLOUDINARY_URL not set — Instagram post will be skipped")
    print()

    # Note: site/public/instagram-feed/*.jpg used to be a fallback host for IG.
    # Now that Cloudinary handles all hosting, that mirror is dead code — and
    # generated_images/ is just a local debug cache. Neither needs to be written
    # or committed; banner_path on disk under generated_images/ is the only
    # artifact, and it's gitignored.

    results: dict[str, dict] = {}

    # ── AI caption enrichment (Hook Writer + CTA Builder) ──────────────────────
    ai_hook: str | None = None
    ai_cta_ig: str | None = None
    ai_cta_tt: str | None = None
    if _AFFILIATE_TOOLS_AVAILABLE and os.environ.get("ANTHROPIC_API_KEY"):
        logger.info("Generating AI hook + CTAs for %s", product["name"])
        try:
            hooks = _affiliate_tools.generate_hooks(product, count=5)
            ai_hook = hooks[0] if hooks else None  # best hook (first)
            ai_cta_ig = _affiliate_tools.build_cta(product, platform="instagram")
            ai_cta_tt = _affiliate_tools.build_cta(product, platform="tiktok")
            if ai_hook:
                logger.info("AI hook selected: %r", ai_hook)
        except Exception as exc:
            logger.warning("AI caption generation failed: %s", exc)

    # ── Instagram draft + approval ────────────────────────────────────────────
    if args.platform in ("instagram", "all"):
        ig_body = instagram_body(product, ai_hook=ai_hook, ai_cta=ai_cta_ig)
        ig_tags = instagram_tags(product)
        show_draft(
            product   = product,
            platform  = "instagram",
            body      = ig_body,
            tags      = ig_tags,
            banner_local  = banner_path,
            banner_public = chosen_image_url,
        )
        if ask_approval("instagram", args.dry_run):
            # Cloudinary only — Meta reliably accepts res.cloudinary.com.
            # No fallbacks: a missing Cloudinary URL means the upload step failed and we
            # want a loud failure rather than fallback to a host Meta will reject.
            if not chosen_image_url:
                err = "No image URL — Cloudinary upload must succeed (set CLOUDINARY_URL)."
                print(f"  FAIL {err}")
                result = {"ok": False, "error": err}
            else:
                ig_urls = [chosen_image_url]
                logger.info("Posting Instagram try_urls=%s", ig_urls)
                print(">> Posting to Instagram...")
                result = post_instagram(product, dry_run=False, image_urls=ig_urls)
                if result["ok"]:
                    logger.info("Instagram OK post_id=%s", result.get("post_id", ""))
                    print(f"  OK  post_id: {result.get('post_id', '')}")
                else:
                    logger.error("Instagram failed: %s", result.get("error"))
                    print(f"  FAIL {result['error']}")
            results["instagram"] = result
            log_result(product, "instagram", result)
        else:
            logger.info("Instagram post skipped (not approved)")
            print("  Skipped.")

    # ── TikTok draft + approval ───────────────────────────────────────────────
    if args.platform in ("tiktok", "all"):
        tt_caption = tiktok_caption(product, ai_hook=ai_hook, ai_cta=ai_cta_tt)
        tt_body, tt_tags = (tt_caption.rsplit("\n\n", 1) + [""])[:2]
        show_draft(
            product   = product,
            platform  = "tiktok",
            body      = tt_body,
            tags      = tt_tags,
            banner_local  = banner_path,
            banner_public = chosen_image_url,
        )
        if ask_approval("tiktok", args.dry_run):
            tik_image = chosen_image_url or product_image_url(product)
            logger.info("Posting TikTok image_url=%s", tik_image)
            print(">> Posting to TikTok...")
            result    = tiktok_api.post_photo([tik_image], tt_caption)
            results["tiktok"] = result
            if result["ok"]:
                logger.info("TikTok OK publish_id=%s", result.get("publish_id", ""))
                print(f"  OK  publish_id: {result.get('publish_id', '')}")
            else:
                logger.error("TikTok failed: %s", result.get("error"))
                print(f"  FAIL {result['error']}")
            log_result(product, "tiktok", result)
        else:
            logger.info("TikTok post skipped (not approved)")
            print("  Skipped.")

    if any(not r["ok"] for r in results.values()):
        logger.error("One or more platforms failed; exiting 1")
        sys.exit(1)
    logger.info("post_daily finished ok results=%s", list(results.keys()))


if __name__ == "__main__":
    main()
