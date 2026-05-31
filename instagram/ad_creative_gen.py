"""AI-generated ad-creative banner via Gemini Nano Banana Pro, grounded on
Tavily-fetched real-world reference images.

Optional alternative to banner_compose.compose_banner. Activated via the
--ad-creative CLI flag on post_daily.py. Default behavior (white-card
pipeline) is unchanged.

Pipeline (adapted from Samin Yasar's "Claude Just Changed Marketing
Forever" tutorial):
  1. Tavily web search for the product → real-world lifestyle/marketing
     image URLs to ground the generation in real-world references.
  2. Send catalog photo + N reference images to Gemini Nano Banana Pro
     (multimodal input → image output).
  3. Resize to canvas, overlay the existing _add_text headline/price/pill
     stack, save JPEG.
  4. Run the AI vision gate as the final QA pass.

Falls back to compose_banner (white-card) on Tavily/Gemini failure so an
outage in either upstream can never halt the daily rotation.
"""
from __future__ import annotations

import base64
import logging
import os
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

try:
    from instagram import competitor_ads as competitor_ads
except ImportError:
    competitor_ads = None  # type: ignore[assignment]
from instagram.banner_compose import (
    CANVAS,
    BannerQualityError,
    _add_text,
    _ai_vision_validate_banner,
    _fetch_image_bytes,
    compose_banner,
)

logger = logging.getLogger(__name__)

# Gemini image generation model. The original "nano-banana-pro-preview" alias
# was a tutorial placeholder that stopped working ~2026-05-26. Use the stable
# gemini-2.5-flash-image model (confirmed live from Google AI docs 2026-05-31).
# Override via GEMINI_AD_MODEL env var if Google releases a newer model.
GEMINI_MODEL = os.environ.get("GEMINI_AD_MODEL", "gemini-2.5-flash-image")
GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
TAVILY_ENDPOINT = "https://api.tavily.com/search"
N_REFERENCES = 4
REFERENCE_MAX_DIM = 1024  # cap reference image size to keep payload sane

PROMPT_TEMPLATE = """You are an e-commerce ad creative director. Produce a single 1080x1080 square \
marketing image for the product "{name}" in the {category} category.

The FIRST attached image is the real product. Reproduce it faithfully — exact \
shape, color, branding, and proportions. Do not invent details that are not in \
the source.

The remaining attached images are lifestyle/marketing references showing the \
visual language (lighting, framing, mood, backdrop) of high-performing ads in \
this category. Match that visual language. Do NOT include any of the other \
products or scenes from the references — only the hero product.

Requirements:
- Square 1:1 framing, hero product front and center, sharp focus
- Premium studio look: soft shadow under the product, clean dark backdrop with \
a subtle warm orange glow behind the product
- Photorealistic only — no cartoon, illustration, 3D render, or text overlays
- No logos, watermarks, captions, or written words anywhere — text is added in \
post-processing
- Roughly 30% breathing room around the product so a headline can fit above \
and pricing/CTA below
"""


def _tavily_image_urls(query: str, n: int) -> list[str]:
    """Return up to n image URLs from Tavily search. Empty list on any failure."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []
    try:
        r = requests.post(
            TAVILY_ENDPOINT,
            json={
                "api_key": api_key,
                "query": query,
                "max_results": n,
                "include_images": True,
                "include_image_descriptions": False,
                "search_depth": "basic",
            },
            timeout=20,
        )
        r.raise_for_status()
        images = r.json().get("images", []) or []
        urls: list[str] = []
        for entry in images:
            url = entry if isinstance(entry, str) else entry.get("url")
            if url:
                urls.append(url)
        return urls[:n]
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Tavily search failed for %r: %s", query, exc)
        return []


def _normalize_to_jpeg(data: bytes, max_dim: int = REFERENCE_MAX_DIM) -> bytes | None:
    """Re-encode any image format to JPEG and clamp the longest side.

    Gemini accepts PNG/JPEG/WebP, but normalizing keeps the request payload
    predictable and small. Returns None on decode failure.
    """
    try:
        img = Image.open(BytesIO(data)).convert("RGB")
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, "JPEG", quality=85, optimize=True)
        return buf.getvalue()
    except Exception as exc:
        logger.warning("Could not normalize image (%d bytes): %s", len(data), exc)
        return None


def _load_image_bytes(path_or_url: str) -> bytes | None:
    try:
        if path_or_url.startswith("http"):
            return _fetch_image_bytes(path_or_url, timeout=20)
        return Path(path_or_url).read_bytes()
    except Exception as exc:
        logger.warning("Could not load image %s: %s", path_or_url, exc)
        return None


def _gemini_generate_image(prompt: str, jpeg_inputs: list[bytes]) -> bytes | None:
    """Call Gemini multimodal endpoint. Returns image bytes or None."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set; cannot generate ad creative")
        return None

    parts: list[dict] = [{"text": prompt}]
    for jpeg in jpeg_inputs:
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": base64.b64encode(jpeg).decode("ascii"),
            }
        })

    endpoint = GEMINI_ENDPOINT_TEMPLATE.format(model=GEMINI_MODEL)
    try:
        r = requests.post(
            endpoint,
            params={"key": api_key},
            json={"contents": [{"parts": parts}]},
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
    except requests.RequestException as exc:
        logger.warning("Gemini request failed: %s", exc)
        return None

    if not r.ok:
        logger.warning("Gemini HTTP %s: %s", r.status_code, r.text[:300])
        return None

    try:
        result = r.json()
    except ValueError:
        logger.warning("Gemini returned non-JSON body")
        return None

    candidates = result.get("candidates") or []
    if not candidates:
        logger.warning("Gemini returned no candidates: %s", str(result)[:300])
        return None

    parts_out = candidates[0].get("content", {}).get("parts", []) or []
    for p in parts_out:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])

    logger.warning("Gemini response had no inlineData image: %s", str(result)[:300])
    return None


def _resize_to_canvas(img_bytes: bytes) -> Image.Image:
    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    if img.size != (CANVAS, CANVAS):
        img = img.resize((CANVAS, CANVAS), Image.LANCZOS)
    return img


def compose_ad_creative_banner(
    product: dict,
    product_image_url_or_path: str,
    output_path: str | Path,
    competitor_brand: str | None = None,
) -> str:
    """Compose an AI-generated ad-creative banner.

    When ``competitor_brand`` is set, the reference image stack is sourced
    from the Facebook Ad Library via ScrapeCreators (high-impression active
    ads matching the brand or keyword) instead of generic Tavily web
    images. The competitor path falls back to Tavily, then to the
    white-card pipeline, so a single upstream outage cannot halt the
    daily rotation. Returns the output path.
    """
    name = product.get("name", "")
    category = (product.get("category") or "Best Sellers").strip()
    src = str(product_image_url_or_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    src_raw = _load_image_bytes(src)
    if src_raw is None:
        print("   [ad-creative] could not load product image; falling back to white-card")
        return compose_banner(product, src, out)

    src_jpeg = _normalize_to_jpeg(src_raw)
    if src_jpeg is None:
        print("   [ad-creative] product image unreadable; falling back to white-card")
        return compose_banner(product, src, out)

    ref_urls: list[str] = []
    ref_source = "tavily"
    if competitor_brand and competitor_brand.strip() and competitor_ads is not None:
        ref_urls = competitor_ads.collect_reference_image_urls(
            competitor_brand.strip(), N_REFERENCES
        )
        ref_source = "scrapecreators"
        if not ref_urls:
            print(
                f"   [ad-creative] ScrapeCreators returned 0 ads for "
                f"{competitor_brand!r}; falling back to Tavily"
            )
            ref_source = "tavily"
    if not ref_urls:
        query = f"{name} {category} product photo lifestyle"
        ref_urls = _tavily_image_urls(query, N_REFERENCES)
    ref_jpegs: list[bytes] = []
    for u in ref_urls:
        raw = _load_image_bytes(u)
        if raw is None:
            continue
        norm = _normalize_to_jpeg(raw)
        if norm is not None:
            ref_jpegs.append(norm)
    print(
        f"   [ad-creative] {ref_source}: {len(ref_urls)} URLs / "
        f"{len(ref_jpegs)} usable references"
    )

    prompt = PROMPT_TEMPLATE.format(name=name, category=category)
    gemini_bytes = _gemini_generate_image(prompt, [src_jpeg] + ref_jpegs)
    if gemini_bytes is None:
        print("   [ad-creative] Gemini returned no image; falling back to white-card")
        return compose_banner(product, src, out)

    canvas = _resize_to_canvas(gemini_bytes).convert("RGBA")
    canvas = _add_text(canvas, product)

    canvas.convert("RGB").save(
        str(out),
        "JPEG",
        quality=93,
        optimize=True,
        progressive=False,
        subsampling=0,
    )

    # Final-stage AI vision gate (BANNER_AI_GATE: off | shadow | enforce).
    mode = (os.environ.get("BANNER_AI_GATE") or "shadow").lower().strip()
    if mode != "off" and name:
        ai_ok, ai_reason = _ai_vision_validate_banner(out, name)
        if mode == "enforce":
            if not ai_ok:
                raise BannerQualityError(f"ai vision: {ai_reason}")
        else:
            verdict = "APPROVED" if ai_ok else f"REJECTED ({ai_reason})"
            print(f"   [ai-gate shadow] {verdict}")

    return str(out)
