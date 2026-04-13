"""
ModelsLab FLUX image generation for Instagram post images.

Strategy for accuracy:
  1. Passes the actual product photo URL from the site to ModelsLab as image_url
     — the model restyling the real product photo, not hallucinating one
  2. Falls back to text-to-image if the product photo URL is inaccessible
  3. Claude (haiku) writes tailored prompts for each style variant

ModelsLab returns public URLs, so no separate image hosting is needed.
Images are also saved locally in save_dir for dry-run preview.

Required env vars:
  MODELSLAB_KEY    — ModelsLab API key (get at modelslab.com)
  ANTHROPIC_API_KEY — optional, improves prompt quality
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

import anthropic
import requests

MODELSLAB_API_BASE = "https://modelslab.com/api/v6"
MODEL_ID           = "flux"
SITE_URL           = "https://hotproductsdot.com"

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
            model="claude-haiku-4-5-20251001",
            max_tokens=700,
            system=(
                f"You write concise ModelsLab FLUX image prompts. {instruction} "
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
                "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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

    payload = json.dumps({
        "model":      "claude-haiku-4-5-20251001",
        "max_tokens": 200,
        "system":     "You describe physical product appearances for image generation. Be specific about colors, shape, size, materials, and key visual features. One concise paragraph, no markdown.",
        "messages":   [{"role": "user", "content": f"Describe the exact visual appearance of: {product['name']}"}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"].strip()
    except Exception:
        return product["name"]


def _call_modelslab_api(
    prompt: str,
    api_key: str,
    image_url: str | None = None,
    model: str = "flux",
    width: int = 1024,
    height: int = 1024,
) -> str | None:
    """
    POST to ModelsLab API. Returns image URL or None on failure.
    If image_url is provided, uses image-to-image (img2img) mode.
    Otherwise uses text-to-image (text2img) mode.
    """
    if image_url:
        # Image-to-image (edit) mode
        endpoint = f"{MODELSLAB_API_BASE}/images/img2img"
        payload = {
            "key": api_key,
            "model_id": model,
            "prompt": prompt,
            "image_url": image_url,
            "strength": 0.75,
            "width": width,
            "height": height,
            "samples": 1,
            "num_inference_steps": 30,
        }
    else:
        # Text-to-image mode
        endpoint = f"{MODELSLAB_API_BASE}/images/text2img"
        payload = {
            "key": api_key,
            "model_id": model,
            "prompt": prompt,
            "width": width,
            "height": height,
            "samples": 1,
            "num_inference_steps": 30,
        }

    try:
        resp = requests.post(
            endpoint,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if not resp.ok:
            print(f"FAILED (HTTP {resp.status_code}: {resp.text[:300]})")
            return None
        data = resp.json()
        if data.get("status") != "success":
            print(f"FAILED (API error: {data.get('message', 'unknown')})")
            return None
        output = data.get("output", [])
        if not output:
            print("FAILED (empty output list)")
            return None
        return output[0]
    except requests.RequestException as exc:
        print(f"FAILED ({exc})")
        return None


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_product_images(
    product: dict,
    n: int = 5,
    save_dir: Path | None = None,
) -> list[dict]:
    """
    Generate n styled image variants for a product using ModelsLab FLUX.

    Returns list of dicts:
        {index, style, url, local_path (str|None), prompt}

    Raises ValueError if MODELSLAB_KEY is missing.
    """
    modelslab_key = os.environ.get("MODELSLAB_KEY", "")
    if not modelslab_key:
        raise ValueError("MODELSLAB_KEY not set — add it to .env to generate images")

    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    # Try to get the real Amazon product image for accurate image-edit mode
    print("  Fetching Amazon product image...", end=" ", flush=True)
    product_img_url = _fetch_amazon_image_url(product)
    if product_img_url:
        print("OK — image-edit mode")
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

    styles  = _STYLES[:n]
    results: list[dict] = []

    for i, style in enumerate(styles):
        prompt = prompts[style]
        print(f"  [{i + 1}/{n}] {style:10s} ... ", end="", flush=True)

        url = _call_modelslab_api(prompt, modelslab_key, image_url=product_img_url)
        if not url:
            continue

        local_path: str | None = None
        if save_dir:
            dest = save_dir / f"variant_{i + 1}_{style}.jpg"
            try:
                img = requests.get(url, timeout=30)
                img.raise_for_status()
                dest.write_bytes(img.content)
                local_path = str(dest)
                print(f"saved → {dest.name}")
            except Exception as exc:
                print(f"OK (local save failed: {exc})")
        else:
            print("OK")

        results.append({
            "index":      i + 1,
            "style":      style,
            "url":        url,
            "local_path": local_path,
            "prompt":     prompt,
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
            raw    = input(f"\nPick image [{lo}-{hi}] (0 = catalog site photo, no AI): ").strip()
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
