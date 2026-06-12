#!/usr/bin/env python3
"""
7_deal_finder.py — Find discounted Amazon products in our target categories.

Scrapes Amazon's Today's Deals search results (public HTML, no API key needed)
for each category in config.yaml, extracts discount %, prices, and deal badges,
cross-references results with the existing product catalog, then saves the
ranked list to data/deals.json.

Optionally posts the top deals to the Facebook Page via --post-facebook.

Source URL pattern:
  https://www.amazon.com/s?k={category}+deals&rh=p_n_deal_type:23566065011&sort=discount-rank

  The p_n_deal_type:23566065011 facet is Amazon's public "Today's Deals" filter
  (the same one in the left rail on amazon.com/deals). It returns Lightning Deals,
  Limited-Time Deals, and coupon items as standard search HTML without JS rendering.

Usage:
    python scripts/7_deal_finder.py                       # full run
    python scripts/7_deal_finder.py --dry-run             # fixture data, no network
    python scripts/7_deal_finder.py --categories kitchen,fitness
    python scripts/7_deal_finder.py --min-discount 25
    python scripts/7_deal_finder.py --post-facebook       # post top 3 to FB page
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Set

from bs4 import BeautifulSoup
from scrapling.fetchers import FetcherSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.config import CONFIG, is_dry_run  # noqa: E402

log = logging.getLogger("deal_finder")

AFFILIATE_TAG = "hotproduct033-20"
ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")
DISCOUNT_RE = re.compile(r"-\s*(\d+)\s*%")
PRICE_RE = re.compile(r"\$([\d,]+\.?\d*)")

# Amazon "Today's Deals" filtered search — public, no auth required.
# sort=discount-rank puts highest-% deals first.
_DEALS_URL = (
    "https://www.amazon.com/s"
    "?k={keyword}"
    "&rh=p_n_deal_type%3A23566065011"
    "&sort=discount-rank"
    "&language=en_US"
)

# Category slug → Amazon search keyword
_CATEGORY_KEYWORDS: dict[str, str] = {
    "kitchen":     "kitchen gadgets",
    "fitness":     "fitness exercise equipment",
    "photography": "camera photography",
    "smart-home":  "smart home devices",
    "laptops":     "laptop computer",
    "gaming":      "gaming accessories",
    "beauty":      "beauty skincare",
}


# ── Data model ──────────────────────────────────────────────────────────────────

@dataclass
class Deal:
    asin: str
    title: str
    category: str
    current_price: str
    original_price: str
    discount_pct: int
    deal_badge: str     # e.g. "Lightning Deal", "Limited time deal", "Coupon"
    affiliate_url: str
    in_catalog: bool    # True if ASIN already exists in top-1000.csv
    found_at: str       # ISO-8601 UTC


# ── Dry-run fixtures ─────────────────────────────────────────────────────────────

_FIXTURES: list[Deal] = [
    Deal(
        asin="B08N5WRWNW",
        title="Echo Dot (4th Gen) | Smart speaker with Alexa | Charcoal",
        category="smart-home",
        current_price="$29.99",
        original_price="$49.99",
        discount_pct=40,
        deal_badge="Lightning Deal",
        affiliate_url=f"https://www.amazon.com/dp/B08N5WRWNW?tag={AFFILIATE_TAG}",
        in_catalog=False,
        found_at=datetime.now(timezone.utc).isoformat(),
    ),
    Deal(
        asin="B07PDHSLM6",
        title="Instant Pot Duo 7-in-1 Electric Pressure Cooker, 6 Quart",
        category="kitchen",
        current_price="$59.95",
        original_price="$99.95",
        discount_pct=40,
        deal_badge="Limited time deal",
        affiliate_url=f"https://www.amazon.com/dp/B07PDHSLM6?tag={AFFILIATE_TAG}",
        in_catalog=True,
        found_at=datetime.now(timezone.utc).isoformat(),
    ),
    Deal(
        asin="B09B8YWXDF",
        title="Resistance Bands Set for Exercise Workout — 5 Levels",
        category="fitness",
        current_price="$14.99",
        original_price="$24.99",
        discount_pct=40,
        deal_badge="Coupon",
        affiliate_url=f"https://www.amazon.com/dp/B09B8YWXDF?tag={AFFILIATE_TAG}",
        in_catalog=False,
        found_at=datetime.now(timezone.utc).isoformat(),
    ),
]


# ── Price helpers ────────────────────────────────────────────────────────────────

def _parse_price(raw: str) -> str:
    m = PRICE_RE.search(raw.replace(",", ""))
    return f"${m.group(1)}" if m else raw.strip()


def _price_float(text: str) -> float:
    m = PRICE_RE.search(text.replace(",", ""))
    try:
        return float(m.group(1)) if m else 0.0
    except (ValueError, AttributeError):
        return 0.0


def _calc_discount(original: str, current: str) -> int:
    o, c = _price_float(original), _price_float(current)
    if o > 0 and 0 < c < o:
        return round((o - c) / o * 100)
    return 0


# ── HTML parsing ─────────────────────────────────────────────────────────────────

def _parse_deals_page(html: str, category: str, min_discount: int) -> list[Deal]:
    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now(timezone.utc).isoformat()
    deals: list[Deal] = []
    seen: set[str] = set()

    for card in soup.select("[data-asin]"):
        asin = card.get("data-asin", "").strip()
        if not asin or len(asin) != 10 or asin in seen:
            continue

        # Title — h2 contains text directly in a span (no intermediate <a> in current HTML)
        title_el = card.select_one("h2 span, a.a-link-normal span, [data-cy='title-recipe'] span")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue

        # Sale price (required — skip if missing)
        price_el = card.select_one(".a-price .a-offscreen")
        current_price = _parse_price(price_el.get_text()) if price_el else ""
        if not current_price:
            continue

        # Original (struck-through) price
        orig_el = card.select_one(
            ".a-text-price .a-offscreen, "
            ".a-price.a-text-price .a-offscreen"
        )
        original_price = _parse_price(orig_el.get_text()) if orig_el else ""

        # Discount % — try badge first, then calculate from prices
        discount_pct = 0
        badge_el = card.select_one(
            ".savingPriceOverride, "
            "span.a-color-price, "
            "span.s-coupon-highlight-color, "
            "[data-a-badge-color] .a-badge-text"
        )
        if badge_el:
            m = DISCOUNT_RE.search(badge_el.get_text())
            if m:
                discount_pct = int(m.group(1))
        if not discount_pct and original_price:
            discount_pct = _calc_discount(original_price, current_price)

        if discount_pct < min_discount:
            continue

        # Human-readable deal badge
        deal_badge = ""
        for sel in [".a-badge-text", "span.s-coupon-highlight-color"]:
            el = card.select_one(sel)
            if el:
                t = el.get_text(strip=True)
                if any(kw in t.lower() for kw in ("lightning", "limited time", "coupon", "deal", "off")):
                    deal_badge = t
                    break

        seen.add(asin)
        deals.append(Deal(
            asin=asin,
            title=title[:200],
            category=category,
            current_price=current_price,
            original_price=original_price,
            discount_pct=discount_pct,
            deal_badge=deal_badge,
            affiliate_url=f"https://www.amazon.com/dp/{asin}?tag={AFFILIATE_TAG}",
            in_catalog=False,
            found_at=now,
        ))

    return deals


# ── Network ───────────────────────────────────────────────────────────────────────

def _fetch_direct(url: str) -> str:
    """Fetch via scrapling (chrome-impersonated). Returns HTML or '' if blocked."""
    try:
        with FetcherSession() as session:
            resp = session.get(url, timeout=25, retries=2)
    except Exception as exc:
        return ""
    if resp.status != 200:
        return ""
    body = resp.body.decode(resp.encoding or "utf-8", errors="replace")
    if "Robot Check" in body or "Type the characters" in body:
        return ""
    return body


def _fetch_via_oxylabs(url: str) -> str:
    """Fallback: fetch via Oxylabs realtime scraper API.

    Uses OXYLABS_USERNAME/OXYLABS_PASSWORD from .env if available.
    Returns HTML or '' on failure.
    """
    user = os.getenv("OXYLABS_USERNAME", "").strip()
    pwd = os.getenv("OXYLABS_PASSWORD", "").strip()
    if not user or not pwd:
        return ""
    import requests

    try:
        r = requests.post(
            "https://realtime.oxylabs.io/v1/queries",
            auth=(user, pwd),
            json={"source": "amazon", "url": url, "parse": False},
            timeout=90,
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            return ""
        if results[0].get("status_code") != 200:
            return ""
        return results[0].get("content") or ""
    except Exception:
        return ""


def _fetch_category_deals(category: str, delay: float, min_discount: int) -> list[Deal]:
    keyword = _CATEGORY_KEYWORDS.get(category, category.replace("-", " "))
    url = _DEALS_URL.format(keyword=keyword.replace(" ", "+"))
    print(f"  [deal_finder] {category} → {url}")

    time.sleep(random.uniform(delay * 0.8, delay * 1.2))
    body = _fetch_direct(url)
    if not body:
        body = _fetch_via_oxylabs(url)
    if not body:
        print(f"  [deal_finder] HTTP 503 for {category} — skipping")
        return []

    deals = _parse_deals_page(body, category, min_discount)
    print(f"  [deal_finder] {category}: {len(deals)} deals ≥{min_discount}% off")
    return deals


# ── Catalog cross-reference ───────────────────────────────────────────────────────

def _load_catalog_asins() -> Set[str]:
    csv_path = Path(CONFIG["_repo_root"]) / "products" / "top-1000.csv"
    if not csv_path.exists():
        return set()
    asins: Set[str] = set()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            m = ASIN_RE.search(row.get("Amazon URL", ""))
            if m:
                asins.add(m.group(1))
    return asins


# ── Persistence ───────────────────────────────────────────────────────────────────

def _save_deals(deals: list[Deal]) -> Path:
    out = Path(CONFIG["paths"]["data_dir"]) / "deals.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(deals),
        "deals": [asdict(d) for d in deals],
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


# ── Facebook ──────────────────────────────────────────────────────────────────────

def _post_to_facebook(deals: list[Deal], top_n: int = 3) -> None:
    try:
        from lib.facebook import post_link
    except ImportError as exc:
        print(f"  [deal_finder] Facebook lib unavailable: {exc}")
        return

    for deal in deals[:top_n]:
        lines = [f"🔥 Deal Alert: {deal.title}", ""]
        lines.append(f"💰 Now: {deal.current_price}")
        if deal.original_price:
            lines.append(f"Was: {deal.original_price}  ({deal.discount_pct}% off)")
        if deal.deal_badge:
            lines.append(f"🏷️  {deal.deal_badge}")
        lines += ["", "👉 Shop now:"]
        message = "\n".join(lines)
        try:
            result = post_link(message=message, link=deal.affiliate_url)
            print(f"  [deal_finder] Facebook → id={result.get('id')}  {deal.title[:50]}")
        except Exception as exc:
            print(f"  [deal_finder] Facebook ERROR: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--categories", default="", help="Comma-separated category slugs (default: all)")
    ap.add_argument("--min-discount", type=int, default=None, help="Min discount %% (default: from config)")
    ap.add_argument("--max-per-category", type=int, default=None, help="Max deals per category")
    ap.add_argument("--post-facebook", action="store_true", help="Post top 3 deals to Facebook Page")
    ap.add_argument("--dry-run", action="store_true", help="Use fixture data, no network calls")
    args = ap.parse_args()

    if args.dry_run:
        os.environ["GROWTH_ENGINE_DRY_RUN"] = "1"

    dry = is_dry_run()
    deals_cfg = CONFIG.get("deals", {})
    min_discount = args.min_discount if args.min_discount is not None else deals_cfg.get("min_discount_pct", 20)
    max_per_cat = args.max_per_category if args.max_per_category is not None else deals_cfg.get("max_deals_per_category", 5)
    post_fb = args.post_facebook or deals_cfg.get("post_to_facebook", False)
    delay = deals_cfg.get("request_delay_sec", 3.0)

    categories: list[str] = (
        [c.strip() for c in args.categories.split(",") if c.strip()]
        if args.categories
        else [c["slug"] for c in CONFIG.get("target_categories", [])]
    )

    print("═" * 60)
    print(f"  Deal Finder — {CONFIG['site']['domain']}")
    print(f"  Categories : {', '.join(categories)}")
    print(f"  Min discount: {min_discount}%  |  Max/cat: {max_per_cat}")
    print(f"  Dry-run: {dry}  |  Post FB: {post_fb}")
    print("═" * 60)

    all_deals: list[Deal] = []

    if dry:
        print("[deal_finder] DRY RUN — using fixture data, no network calls.")
        all_deals = [d for d in _FIXTURES if not categories or d.category in categories]
    else:
        catalog_asins = _load_catalog_asins()
        seen_global: set[str] = set()

        for cat in categories:
            cat_deals = _fetch_category_deals(cat, delay, min_discount)
            added = 0
            for deal in cat_deals:
                if deal.asin in seen_global:
                    continue
                deal.in_catalog = deal.asin in catalog_asins
                all_deals.append(deal)
                seen_global.add(deal.asin)
                added += 1
                if added >= max_per_cat:
                    break

    # Rank: catalog items first (affiliate links already in CSV), then by discount
    all_deals.sort(key=lambda d: (-int(d.in_catalog), -d.discount_pct))

    print(f"\n[deal_finder] Total: {len(all_deals)} deals")
    for d in all_deals:
        catalog_tag = " [catalog]" if d.in_catalog else ""
        badge = f"  {d.deal_badge}" if d.deal_badge else ""
        print(f"  {d.discount_pct:>3}% off  {d.current_price:<8}  {d.category:<12}  {d.title[:50]}{catalog_tag}{badge}")

    if dry:
        print("\n[deal_finder] DRY RUN — nothing written.")
        return 0

    out_path = _save_deals(all_deals)
    print(f"\n[deal_finder] Saved → {out_path}")

    if post_fb:
        _post_to_facebook(all_deals)

    print("[deal_finder] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
