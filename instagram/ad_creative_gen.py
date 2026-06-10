"""AI-generated ad-creative banner via FAL.AI, grounded on
Tavily-fetched real-world reference images.

Optional alternative to banner_compose.compose_banner. Activated via the
--ad-creative CLI flag on post_daily.py. Default behavior (white-card
pipeline) is unchanged.

Pipeline:
  1. Tavily web search for the product -> real-world lifestyle/marketing
     image URLs to ground the generation in real-world references.
  2. Compose a HotProducts-style prompt from the product photo + N reference
     images and dispatch it through image_gen_fal.py (FAL.AI).
  3. Resize to canvas, overlay the existing _add_text headline/price/pill
     stack, save JPEG.
  4. Run the AI vision gate as the final QA pass.

Falls back to compose_banner (white-card) on Tavily/FAL failure so an
outage in either upstream can never halt the daily rotation.
"""
from __future__ import annotations

import logging
import os
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

TAVILY_ENDPOINT = "https://api.tavily.com/search"
N_REFERENCES = 4
REFERENCE_MAX_DIM = 1024

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
    """Re-encode any image format to JPEG and clamp the longest side."""
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


def _resize_to_canvas(img_bytes: bytes) -> Image.Image:
    img = Image.open(img_bytes).convert("RGB") if hasattr(img_bytes, "read") else Image.open(BytesIO(img_bytes)).convert("RGB")
    if img.size != (CANVAS, CANVAS):
        img = img.resize((CANVAS, CANVAS), Image.LANCZOS)
    return img


def compose_ad_creative_banner(
    product: dict,
    product_image_url_or_path: str,
    output_path: str | Path,
    competitor_brand: str | None = None,
) -> str:
    """Compose an FAL.AI-generated ad-creative banner.

    When ``competitor_brand`` is set, the reference image stack is sourced
    from the Facebook Ad Library via ScrapeCreators (high-impression active
    ads matching the brand or keyword) instead of generic Tavily web
    images. The competitor path falls back to Tavily, then to the
    white-card pipeline, so a single upstream outage cannot halt the
    daily rotation. Returns the output path.
    """
    try:
        from instagram.image_gen_fal import _build_fal_prompt, _fal_generate_image
    except ImportError as exc:
        raise ImportError("image_gen_fal module is required for FAL.AI ad creatives") from exc

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
    out_bytes = _fal_generate_image(prompt, src_jpeg)
    if out_bytes is None:
        print("   [ad-creative] FAL returned no image; falling back to white-card")
        return compose_banner(product, src, out)

    canvas = _resize_to_canvas(out_bytes).convert("RGBA")
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
