"""
Affiliate content generation tools powered by Claude.

4 tools for Amazon affiliate marketing:
- Hook Writer: scroll-stopping opening lines
- CTA Builder: platform-specific calls-to-action
- Content Calendar: 7-day posting plan
- Bio Optimizer: optimized Instagram/TikTok bio text
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore

# ── Constants ──────────────────────────────────────────────────────
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS_HOOKS = 300
_MAX_TOKENS_CTA = 100
_MAX_TOKENS_CAL = 2000
_MAX_TOKENS_BIO = 200

# Fallback templates (used when API is unavailable)
_HOOKS_FALLBACK = [
    "This one's blowing up on Amazon 🔥",
    "Everyone's grabbing this right now 👀",
    "The reviews don't lie 💯",
    "If you're not using this yet, you're missing out 😅",
    "Just ordered another one for myself ✨",
]

_CTA_FALLBACK = {
    "instagram": "Link in bio → 🛒",
    "tiktok": "Comment LINK 👇",
}

_BIO_FALLBACK = "Amazon affiliate 🛒 Sharing the best finds 💯 #hotproducts"


# ── Client management ──────────────────────────────────────────────
_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    """Lazy singleton client. Raises RuntimeError if ANTHROPIC_API_KEY not set."""
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ── Hook Writer ────────────────────────────────────────────────────
def generate_hooks(product: dict, count: int = 5) -> list[str]:
    """
    Generate scroll-stopping opening lines for a product.

    Args:
        product: dict with keys: name, category, rating, reviews, price
        count: number of hooks to generate (default: 5)

    Returns:
        list of hook strings

    Falls back to templates if ANTHROPIC_API_KEY is not set.
    """
    if not anthropic:
        return _HOOKS_FALLBACK[:count]

    try:
        client = _get_client()
    except RuntimeError:
        return _HOOKS_FALLBACK[:count]

    product_desc = (
        f"Product: {product.get('name', 'Unknown')}\n"
        f"Category: {product.get('category', 'Various')}\n"
        f"Price: {product.get('price', 'N/A')}\n"
        f"Rating: {product.get('rating', '4.0')}/5 ({product.get('reviews', '100')} reviews)"
    )

    prompt = f"""Generate {count} scroll-stopping Instagram hooks for this Amazon product.
Hooks should be 1-3 words, punchy, curiosity-inducing, and include relevant emojis.
Do NOT use ellipsis ("...") or trailing dots — every hook must end with a complete word or emoji.

{product_desc}

Return ONLY a JSON array of strings. No markdown, no explanation.
Example: ["This one's blowing up 🔥", "Everyone's ordering this 👀"]"""

    try:
        message = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS_HOOKS,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        hooks = json.loads(response_text)
        if isinstance(hooks, list) and len(hooks) > 0:
            return hooks[:count]
    except (json.JSONDecodeError, AttributeError, IndexError, Exception):
        pass

    return _HOOKS_FALLBACK[:count]


# ── CTA Builder ────────────────────────────────────────────────────
def build_cta(product: dict, platform: str) -> str:
    """
    Generate platform-specific call-to-action.

    Args:
        product: dict with keys: name, price
        platform: "instagram" or "tiktok"

    Returns:
        CTA string

    Falls back to templates if ANTHROPIC_API_KEY is not set or API fails.
    """
    if not anthropic:
        return _CTA_FALLBACK.get(platform.lower(), _CTA_FALLBACK["instagram"])

    try:
        client = _get_client()
    except RuntimeError:
        return _CTA_FALLBACK.get(platform.lower(), _CTA_FALLBACK["instagram"])

    platform_context = {
        "instagram": "Instagram (limited to 2,200 chars, use 'Link in bio' format, include price if under $50)",
        "tiktok": "TikTok (use 'Comment LINK' or 'DM LINK' convention, action-oriented)",
    }

    context = platform_context.get(platform.lower(), platform_context["instagram"])

    prompt = f"""Generate a single, punchy call-to-action for this product on {context}.

Product: {product.get('name', 'Unknown')} (${product.get('price', 'Check Amazon')})

Do NOT use ellipsis ("...") or trailing dots — the CTA must end on a complete word, price, or emoji.

Return ONLY the CTA string. No markdown, no quotes, no explanation.
Example for Instagram: Link in bio → $44.99 🛒
Example for TikTok: Comment LINK for the deal 👇"""

    try:
        message = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS_CTA,
            messages=[{"role": "user", "content": prompt}],
        )

        cta = message.content[0].text.strip()
        if cta and len(cta) < 150:  # sanity check
            return cta
    except Exception:
        pass

    return _CTA_FALLBACK.get(platform.lower(), _CTA_FALLBACK["instagram"])


# ── Content Calendar ───────────────────────────────────────────────
def generate_content_calendar(products: list[dict], days: int = 7) -> dict:
    """
    Generate a N-day content calendar with hook + CTA per day.

    Args:
        products: list of product dicts (name, category, price, rating, reviews, amazon_url, slug)
        days: number of days to plan (default: 7)

    Returns:
        dict with structure:
        {
            "generated_at": "ISO timestamp",
            "days": N,
            "entries": [
                {
                    "day": 1,
                    "date": "YYYY-MM-DD",
                    "platform": "instagram" | "tiktok",
                    "product": {...},
                    "hook": "...",
                    "cta": "...",
                    "hashtags": "..."
                }
            ]
        }

    Falls back to simple deterministic calendar if API unavailable.
    """
    entries = []

    if not anthropic or days < 1 or not products:
        # Fallback: round-robin products, alternate platforms
        for i in range(min(days, len(products))):
            product = products[i % len(products)]
            platform = "instagram" if i % 2 == 0 else "tiktok"

            entries.append({
                "day": i + 1,
                "date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
                "platform": platform,
                "product": product,
                "hook": _HOOKS_FALLBACK[i % len(_HOOKS_FALLBACK)],
                "cta": _CTA_FALLBACK[platform],
                "hashtags": "#hotproducts #amazonfinds #musthave",
            })

        return {
            "generated_at": datetime.now().isoformat(),
            "days": len(entries),
            "entries": entries,
        }

    # API-based calendar generation
    try:
        client = _get_client()
    except RuntimeError:
        # Fallback if no API key
        for i in range(min(days, len(products))):
            product = products[i % len(products)]
            platform = "instagram" if i % 2 == 0 else "tiktok"
            entries.append({
                "day": i + 1,
                "date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
                "platform": platform,
                "product": product,
                "hook": _HOOKS_FALLBACK[i % len(_HOOKS_FALLBACK)],
                "cta": _CTA_FALLBACK[platform],
                "hashtags": "#hotproducts #amazonfinds #musthave",
            })

        return {
            "generated_at": datetime.now().isoformat(),
            "days": len(entries),
            "entries": entries,
        }

    # Build product pool for Claude
    top_products = products[:min(len(products), days * 2)]  # 2x pool for flexibility
    products_json = json.dumps(
        [
            {
                "name": p.get("name", "Unknown"),
                "category": p.get("category", "Various"),
                "price": p.get("price", "TBD"),
                "rating": p.get("rating", 4.0),
                "reviews": p.get("reviews", "100"),
            }
            for p in top_products
        ]
    )

    prompt = f"""Generate a {days}-day Amazon affiliate posting calendar from this product pool.
For each day, select the best product, pick a platform (alternate Instagram/TikTok),
and craft a hook + CTA specific to that day and platform.

Product pool:
{products_json}

Return ONLY a JSON array of objects matching this structure:
[
  {{
    "day": 1,
    "platform": "instagram",
    "product_index": 0,
    "hook": "...",
    "cta": "...",
    "hashtags": "#hotproducts #..."
  }}
]

Requirements:
- 1 entry per day
- Alternate platforms (day 1 instagram, day 2 tiktok, etc.)
- Hooks: 1-3 punchy words with emoji
- CTAs: Instagram = "Link in bio → $price 🛒", TikTok = "Comment LINK 👇"
- Hashtags: Always include #hotproducts and 2-3 relevant hashtags"""

    try:
        message = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS_CAL,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        calendar_data = json.loads(response_text)

        if isinstance(calendar_data, list) and len(calendar_data) > 0:
            for item in calendar_data[:days]:
                product_idx = item.get("product_index", 0)
                if product_idx < len(top_products):
                    product = top_products[product_idx]
                    entries.append({
                        "day": item.get("day", len(entries) + 1),
                        "date": (datetime.now() + timedelta(days=len(entries))).strftime("%Y-%m-%d"),
                        "platform": item.get("platform", "instagram"),
                        "product": product,
                        "hook": item.get("hook", _HOOKS_FALLBACK[0]),
                        "cta": item.get("cta", _CTA_FALLBACK["instagram"]),
                        "hashtags": item.get("hashtags", "#hotproducts #amazonfinds"),
                    })

            if len(entries) > 0:
                return {
                    "generated_at": datetime.now().isoformat(),
                    "days": len(entries),
                    "entries": entries,
                }
    except (json.JSONDecodeError, Exception):
        pass

    # Final fallback: deterministic round-robin
    for i in range(min(days, len(products))):
        product = products[i % len(products)]
        platform = "instagram" if i % 2 == 0 else "tiktok"

        entries.append({
            "day": i + 1,
            "date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
            "platform": platform,
            "product": product,
            "hook": _HOOKS_FALLBACK[i % len(_HOOKS_FALLBACK)],
            "cta": _CTA_FALLBACK[platform],
            "hashtags": "#hotproducts #amazonfinds #musthave",
        })

    return {
        "generated_at": datetime.now().isoformat(),
        "days": len(entries),
        "entries": entries,
    }


# ── Bio Optimizer ──────────────────────────────────────────────────
def generate_bio(platform: str = "instagram", niche: str = "Amazon affiliate") -> str:
    """
    Generate optimized Instagram/TikTok bio text.

    Args:
        platform: "instagram" or "tiktok"
        niche: optional context (default: "Amazon affiliate")

    Returns:
        bio string (under 150 chars for Instagram, under 500 for TikTok)

    Falls back to template if API unavailable.
    """
    if not anthropic:
        return _BIO_FALLBACK

    try:
        client = _get_client()
    except RuntimeError:
        return _BIO_FALLBACK

    limits = {
        "instagram": "150 characters",
        "tiktok": "500 characters",
    }
    char_limit = limits.get(platform.lower(), limits["instagram"])

    prompt = f"""Generate an optimized {platform} bio for an Amazon affiliate focused on {niche}.

Requirements:
- Under {char_limit}
- Include clear value proposition (what followers get)
- Include call-to-action (Link in bio, DM, etc.)
- Use emojis strategically (1-2 max)
- Make it conversion-focused

Return ONLY the bio text. No markdown, no quotes, no explanation."""

    try:
        message = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS_BIO,
            messages=[{"role": "user", "content": prompt}],
        )

        bio = message.content[0].text.strip()
        if bio and len(bio) < 600:  # sanity check
            return bio
    except Exception:
        pass

    return _BIO_FALLBACK
