"""
Google Generative AI (Gemini) image generation for Instagram post images.

Uses the Nano Banana Pro Preview model from Google's Generative AI API.

Strategy for accuracy:
  1. Passes the actual product photo URL from the site to Gemini as context
     — the model restyling the real product photo
  2. Falls back to text-to-image if the product photo URL is inaccessible
  3. Claude (haiku) writes tailored prompts for each style variant

Gemini returns image data directly, saved locally in save_dir.

Required env vars:
  GEMINI_API_KEY    — Google Generative AI API key
  ANTHROPIC_API_KEY — optional, improves prompt quality (Claude for prompt generation)
"""
import json
import os
import sys
from pathlib import Path

import requests

try:
    from google import genai
except ImportError:
    genai = None

import anthropic

# Note: We use the REST API directly for image generation, so the genai SDK
# is optional but kept for future expansion (e.g., text generation, vision
# APIs). The new SDK is `google-genai` (replaces the deprecated
# `google-generativeai` package).

SITE_URL = "https://hotproductsdot.com"

# Brand visual DNA: dark charcoal studio backdrop + orange (#FF6B00) accent lighting
# Matches the HotProducts banner style: dark radial gradient, premium affiliate editorial feel
_STYLES = ["banner", "studio_dark", "lifestyle", "vibrant", "detail"]

# Edit-mode prompts — product name injected at runtime via .format(name=...)
_EDIT_PROMPTS: dict[str, str] = {
    "banner": (
        "Premium affiliate marketing photo of {name} on a dark charcoal gradient background "
        "(near-black #0f0f0f edges, #2c2c2c center glow). "
        "Soft orange (#FF6B00) glow light behind the product, cinematic rim lighting. "
        "Product sharp, centered, floating with a soft drop shadow. "
        "Keep the product shape, color, and branding 100% identical."
    ),
    "studio_dark": (
        "Professional studio photo of {name} on a deep graphite background (#1c1c1c). "
        "Dramatic side lighting with warm orange-tinted rim light, "
        "premium commerce photography. "
        "Keep the product shape, color, and branding 100% identical."
    ),
    "lifestyle": (
        "Photo of {name} in a sleek modern home setting, "
        "moody amber lighting, dark tones, upscale editorial Instagram aesthetic. "
        "Keep the product shape, color, and branding 100% identical."
    ),
    "vibrant": (
        "Bold social media photo of {name} on a dark background with vibrant "
        "orange (#FF6B00) accent light, dynamic Gen-Z Instagram energy. "
        "Keep the product shape, color, and branding 100% identical."
    ),
    "detail": (
        "Close-up macro photo of {name} on a dark matte charcoal background, "
        "shallow depth of field, orange-tinted rim lighting, "
        "premium product photography emphasising texture and quality. "
        "Keep the product shape, color, and branding 100% identical."
    ),
}

# Text-to-image fallback prompts (no base image available)
_TEXT_PROMPTS: dict[str, str] = {
    "banner": (
        "Premium affiliate marketing photo of {name} on a dark charcoal gradient background "
        "(near-black edges, lighter gray center glow). "
        "Soft orange (#FF6B00) backlight glow, product centered and sharp. "
        "No text, no watermarks."
    ),
    "studio_dark": (
        "Professional product photo of {name} on a deep graphite background, "
        "dramatic cinematic lighting, orange-tinted rim light, premium commerce style. "
        "No text, no watermarks."
    ),
    "lifestyle": (
        "Lifestyle photo of {name} in a sleek modern home, "
        "moody amber side lighting, dark tones, upscale editorial aesthetic. "
        "No text, no watermarks."
    ),
    "vibrant": (
        "Bold social media shot of {name} on dark background, "
        "vibrant orange accent light, dynamic Gen-Z Instagram energy. "
        "No text, no watermarks."
    ),
    "detail": (
        "Close-up macro of {name} on dark matte background, "
        "shallow depth of field, orange-tinted rim lighting, premium feel. "
        "No text, no watermarks."
    ),
}


# ── Prompt building ───────────────────────────────────────────────────────────

def _build_prompts_claude(product: dict, edit_mode: bool) -> dict[str, str]:
    """Ask Claude haiku for tailored prompts. Falls back to static templates."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        base = _EDIT_PROMPTS if edit_mode else _TEXT_PROMPTS
        return {s: t.format(name=product["name"]) for s, t in base.items()}

    styles_list = ", ".join(_STYLES)
    if edit_mode:
        instruction = (
            "Write image-edit prompts that restyle an existing product photo into different photography styles. "
            "Each prompt must explicitly end with: 'Keep the product shape, color, and branding identical.' "
            "Each prompt must be under 250 characters."
        )
    else:
        instruction = (
            f"Write text-to-image prompts for a product called '{product['name']}' in different photography styles. "
            "Each prompt must describe the product accurately and end with 'No text, no watermarks.' "
            "Each prompt must be under 250 characters."
        )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=700,
            system=(
                f"You write concise Gemini image prompts. {instruction} "
                "Return valid JSON only — no markdown, no explanation."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Product: {product['name']}\n"
                    f"Category: {product.get('category', 'consumer product')}\n\n"
                    f"Write one prompt for each style: {styles_list}.\n"
                    f"Return a JSON object with those exact keys."
                ),
            }],
        )
        text = response.content[0].text.strip()
        # Strip markdown code blocks if present
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json\n").rstrip("\n")
        prompts = json.loads(text)
        if all(s in prompts for s in _STYLES):
            return prompts
    except Exception as exc:
        print(f"  [claude prompt error: {exc} — using templates]")

    base = _EDIT_PROMPTS if edit_mode else _TEXT_PROMPTS
    return {s: t.format(name=product["name"]) for s, t in base.items()}


# ── Product image resolution ──────────────────────────────────────────────────

def _fetch_amazon_image_url(product: dict) -> str | None:
    """
    Scrape the og:image from the Amazon product page.
    Returns the main product image URL or None if unreachable.
    """
    amazon_url = product.get("amazon_url", "")
    if not amazon_url:
        return None
    try:
        resp = requests.get(
            amazon_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=15,
        )
        if not resp.ok:
            return None
        import re
        # og:image meta tag — most reliable
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', resp.text)
        if m:
            return m.group(1)
        # Amazon CDN image from data blob
        m = re.search(r'"large"\s*:\s*"(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"', resp.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _describe_product_visually(product: dict) -> str:
    """
    Ask Claude to describe exactly what the product looks like.
    Used as a rich prompt when no reference image is available.
    Returns a detailed visual description string.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return product["name"]

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            system="You describe physical product appearances for image generation. Be specific about colors, shape, size, materials, and key visual features. One concise paragraph, no markdown.",
            messages=[{"role": "user", "content": f"Describe the exact visual appearance of: {product['name']}"}],
        )
        return response.content[0].text.strip()
    except Exception:
        return product["name"]


def _call_gemini_api(
    prompt: str,
    api_key: str,
    image_url: str | None = None,
    model: str = "nano-banana-pro-preview",
    width: int = 1024,
    height: int = 1024,
) -> bytes | None:
    """
    Call Gemini API for image generation via REST endpoint.
    Returns image bytes or None on failure.
    Uses nano-banana-pro-preview model from Google AI Pro.
    """
    import base64
    import json

    # Nano Banana models are accessed via the REST API endpoint
    # https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    headers = {
        "Content-Type": "application/json",
    }

    # Build the request payload
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    try:
        # Make the API request with the API key as a query parameter
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            params={"key": api_key},
            timeout=60,
        )

        if not response.ok:
            error_text = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", error_text)
            except:
                error_msg = error_text
            print(f"FAILED ({response.status_code}: {error_msg})")
            return None

        # Parse response
        result = response.json()

        # Check for successful image generation
        if "candidates" not in result or not result["candidates"]:
            print("FAILED (no candidates in response)")
            return None

        candidate = result["candidates"][0]

        # Image data is returned as base64 in the content
        if "content" not in candidate or "parts" not in candidate["content"]:
            print("FAILED (no content parts in response)")
            return None

        parts = candidate["content"]["parts"]
        if not parts:
            print("FAILED (empty parts)")
            return None

        # Extract the image data (could be inlineData or inline_data or a URL)
        for part in parts:
            # Try both camelCase (inlineData) and snake_case (inline_data) for compatibility
            data_dict = part.get("inlineData") or part.get("inline_data")
            if data_dict:
                # Base64 encoded image data
                image_data_b64 = data_dict.get("data", "")
                if image_data_b64:
                    return base64.b64decode(image_data_b64)
            elif "image" in part and "url" in part["image"]:
                # Image URL returned by the API
                img_url = part["image"]["url"]
                try:
                    img_resp = requests.get(img_url, timeout=15)
                    img_resp.raise_for_status()
                    return img_resp.content
                except Exception as exc:
                    print(f"FAILED (couldn't download image URL: {exc})")
                    return None

        print("FAILED (no image data in response)")
        return None

    except Exception as exc:
        print(f"FAILED ({exc})")
        return None


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_product_images(
    product: dict,
    n: int = 5,
    save_dir: Path | None = None,
    model: str = "nano-banana-pro-preview",
) -> list[dict]:
    """
    Generate n styled image variants for a product using Google Gemini.

    Args:
        product: Product dict with 'name', 'amazon_url', etc.
        n: Number of variants to generate
        save_dir: Optional Path to save images locally
        model: Gemini model ("nano-banana-pro-preview" or other available models)

    Returns list of dicts:
        {index, style, url, local_path (str|None), prompt}

    Raises ValueError if GEMINI_API_KEY is missing.
    """
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY not set — add it to .env to generate images")

    if not genai:
        raise ValueError("google-genai not installed — run: pip install google-genai")

    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    # Try to get the real Amazon product image for context
    print("  Fetching Amazon product image...", end=" ", flush=True)
    product_img_url = _fetch_amazon_image_url(product)
    if product_img_url:
        print("OK — using as visual reference")
        edit_mode = True
    else:
        print("unavailable — text-to-image mode")
        edit_mode = False
        # Ask Claude to describe the product visually so prompts are product-specific
        print("  Asking Claude to describe product appearance...", end=" ", flush=True)
        visual_desc = _describe_product_visually(product)
        print("OK")
        # Inject visual description into the text prompts
        product = {**product, "name": f"{product['name']} ({visual_desc})"}

    using_claude = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"  Building prompts {'with Claude' if using_claude else 'from templates'}...")
    prompts = _build_prompts_claude(product, edit_mode=edit_mode)

    styles = _STYLES[:n]
    results: list[dict] = []

    for i, style in enumerate(styles):
        prompt = prompts[style]
        print(f"  [{i + 1}/{n}] {style:10s} ... ", end="", flush=True)

        image_bytes = _call_gemini_api(prompt, gemini_key, image_url=product_img_url, model=model)
        if not image_bytes:
            continue

        local_path: str | None = None
        if save_dir:
            dest = save_dir / f"variant_{i + 1}_{style}.jpg"
            try:
                dest.write_bytes(image_bytes)
                local_path = str(dest)
                print(f"saved → {dest.name}")
            except Exception as exc:
                print(f"OK (local save failed: {exc})")
        else:
            print("OK")

        results.append({
            "index": i + 1,
            "style": style,
            "url": None,  # Gemini returns bytes, not a URL; images are stored locally
            "local_path": local_path,
            "prompt": prompt,
        })

    return results


def pick_image(variants: list[dict]) -> dict | None:
    """
    Interactive picker. Auto-selects variant 1 in non-TTY environments (CI).

    In a TTY, enter 1–N to choose a variant, or 0 to skip AI images and use
    the catalog product photo URL from the site instead.
    """
    if not variants:
        raise RuntimeError("No image variants to pick from")

    if not sys.stdin.isatty():
        print("[non-interactive] Auto-selecting variant 1")
        return variants[0]

    print()
    print("Generated images:")
    for v in variants:
        path_hint = f"  → {v['local_path']}" if v["local_path"] else ""
        print(f"  [{v['index']}] {v['style']}{path_hint}")

    lo, hi = 0, len(variants)
    while True:
        try:
            raw = input(f"\nPick image [{lo}-{hi}] (0 = catalog site photo, no AI): ").strip()
            choice = int(raw)
            if choice == 0:
                return None
            match = next((v for v in variants if v["index"] == choice), None)
            if match:
                return match
            print(f"  Enter {lo} (catalog) or a variant index from 1 to {hi}")
        except (ValueError, EOFError):
            print("  Invalid input — try again")
        except KeyboardInterrupt:
            print("\nAborted.")
            raise
