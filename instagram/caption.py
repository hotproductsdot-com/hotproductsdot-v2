"""
Caption generator — creates Instagram-ready captions for HotProducts picks.
Uses Claude API if ANTHROPIC_API_KEY is set, otherwise uses varied templates.
"""
import os
import json
import random
import urllib.request
import urllib.parse

# ── Template bank — rotated daily so feed doesn't look repetitive ─────────────

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

_HASHTAG_SETS = [
    "#amazon #amazonfinds #musthave #productreview #deals #shopping #trending #viral #onlineshopping #affordablelife",
    "#amazondailydeals #topproduct #productoftheday #shopnow #amazondeals #tiktokmademebuyit #shopping #sale #findoftheday #recommended",
    "#amazonfind #bestproducts #reviewoftheday #buynow #shopaholic #dealsoftheday #hotproducts #trendingnow #mustbuy #productpick",
]


def _star_display(stars):
    full  = int(stars)
    half  = 1 if (stars - full) >= 0.3 else 0
    empty = 5 - full - half
    return "⭐" * full + ("✨" if half else "") + "☆" * empty


def _price_text(price):
    if not price:
        return "Check Amazon for price"
    return f"${price:,.2f} on Amazon"


def generate_template(product):
    """Generate a caption from rotating templates — no API required."""
    hook     = _HOOKS[hash(product["slug"]) % len(_HOOKS)]
    closer   = _CLOSERS[hash(product["slug"] + "c") % len(_CLOSERS)]
    tags     = _HASHTAG_SETS[hash(product["slug"] + "t") % len(_HASHTAG_SETS)]
    stars_ui = _star_display(product["stars"] or 0)
    price    = _price_text(product.get("price"))
    reviews  = f"{product['reviews']:,}" if product.get("reviews") else "many"

    lines = [
        hook,
        "",
        f"✨ {product['name']}",
        "",
        f"{stars_ui} {product['stars']}/5 · {reviews} reviews",
        f"📦 {product.get('category', 'Amazon Pick')}",
        f"💰 {price}",
        "",
        closer,
        "",
        tags,
        "#hotproducts #hotproductsdotcom",
    ]
    return "\n".join(lines)


def generate_claude(product):
    """
    Generate a caption using Claude claude-haiku-4-5-20251001 (fast + cheap).
    Falls back to template if API key missing or call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return generate_template(product)

    prompt = (
        f"Write an engaging Instagram caption for this Amazon product.\n\n"
        f"Product: {product['name']}\n"
        f"Category: {product.get('category', '')}\n"
        f"Rating: {product['stars']}/5 stars ({product['reviews']:,} reviews)\n"
        f"Price: {_price_text(product.get('price'))}\n\n"
        f"Rules:\n"
        f"- 3–5 short punchy lines max\n"
        f"- Start with a hook (no 'Introducing' or 'Check out')\n"
        f"- Include 1–2 relevant emojis per line\n"
        f"- End with 'Link in bio' call-to-action\n"
        f"- Add 10 relevant hashtags on the last line\n"
        f"- Always include #hotproducts and #hotproductsdotcom in the hashtags\n"
        f"- Tone: enthusiastic but not spammy"
    )

    payload = json.dumps({
        "model":      "claude-haiku-4-5-20251001",
        "max_tokens": 400,
        "messages":   [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]
    except Exception as e:
        print(f"[caption] Claude API error: {e} — falling back to template")
        return generate_template(product)


def generate(product):
    """Return the best caption available for this product."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return generate_claude(product)
    return generate_template(product)
