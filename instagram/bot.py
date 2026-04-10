"""
Instagram OODA Bot — daily posts promoting HotProducts.com picks

OODA Loop:
  Observe  — scrape hotproductsdot.com for today's featured products
  Orient   — rank by score (stars × review_count^0.4), skip already-posted
  Decide   — pick the top unposted product
  Act      — generate caption, post to Instagram, notify via Telegram

Run: python3 instagram/bot.py
Schedule: once daily at 10am via cron (see schedule.sh)
"""
import os
import sys
import json
from datetime import datetime, date

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

# Load .env from project root
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            if _k.strip() and _v.strip() and _k.strip() not in os.environ:
                os.environ[_k.strip()] = _v.strip()

# Telegram notify — reuse Trading/notify.py if available, else no-op
try:
    sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "Trading"))
    import notify
except ImportError:
    class notify:
        @staticmethod
        def send(msg): pass

from instagram.scraper import get_all_products
from instagram.caption import generate
from instagram.poster  import post_image, check_credentials

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
MAX_HISTORY = 200   # product slugs to remember (prevents repeating old posts)


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            d = json.load(f)
            d["posted_slugs"] = set(d.get("posted_slugs", []))
            return d
    return {"posted_slugs": set(), "last_post": None, "total_posts": 0}


def save_state(state):
    s = dict(state)
    slugs = list(s["posted_slugs"])
    s["posted_slugs"] = slugs[-MAX_HISTORY:]
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2)


def already_posted_today(state):
    last = state.get("last_post", "")
    if not last:
        return False
    try:
        return datetime.fromisoformat(last).date() == date.today()
    except (ValueError, TypeError):
        return False


def run():
    log("=== Instagram OODA Bot ===")

    # ── Observe ───────────────────────────────────────────────────────
    log("OBSERVE: Scraping hotproductsdot.com...")
    products = get_all_products()
    if not products:
        log("ERROR: No products scraped. Aborting.")
        return

    log(f"  Found {len(products)} products")
    for i, p in enumerate(products[:5], 1):
        log(f"  #{i} {p['name']} — {p['stars']}★ · {p['reviews']:,} reviews · score={p['score']:.1f}")

    # ── Orient ────────────────────────────────────────────────────────
    state = load_state()

    if already_posted_today(state):
        log("Already posted today — skipping.")
        return

    log("ORIENT: Selecting best unposted product...")
    candidate = None
    for p in products:
        if p["slug"] not in state["posted_slugs"]:
            candidate = p
            break

    if not candidate:
        log("All current products already posted. Clearing history and restarting cycle.")
        state["posted_slugs"] = set()
        candidate = products[0]

    log(f"  Selected: {candidate['name']}")

    # ── Decide ────────────────────────────────────────────────────────
    log("DECIDE: Generating caption...")
    caption = generate(candidate)
    log(f"  Caption preview: {caption[:80]}...")

    if not candidate.get("image_url"):
        log("ERROR: No image URL — cannot post to Instagram.")
        return

    # ── Act ───────────────────────────────────────────────────────────
    log("ACT: Posting to Instagram...")

    ok, info = check_credentials()
    if not ok:
        log(f"Instagram credentials invalid: {info}")
        log("Set INSTAGRAM_USER_ID and INSTAGRAM_ACCESS_TOKEN in .env")
        return

    log(f"  Authenticated as @{info}")
    post_id, err = post_image(candidate["image_url"], caption)

    if err:
        log(f"  Post FAILED: {err}")
        notify.send(f"❌ <b>Instagram post failed</b>\n{candidate['name']}\n{err}")
        return

    log(f"  Posted! Post ID: {post_id}")
    state["posted_slugs"].add(candidate["slug"])
    state["last_post"] = datetime.now().isoformat()
    state["total_posts"] = state.get("total_posts", 0) + 1
    save_state(state)

    notify.send(
        f"📸 <b>Instagram posted!</b>\n"
        f"{candidate['name']}\n"
        f"{candidate['stars']}★ · {candidate['reviews']:,} reviews\n"
        f"Post #{state['total_posts']} · {candidate['category']}"
    )
    log(f"Done. Total posts: {state['total_posts']}")


if __name__ == "__main__":
    run()
