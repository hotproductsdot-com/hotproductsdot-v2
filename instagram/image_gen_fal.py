"""
FAL-based image generation module for HotProducts ad creatives.

Provides:
  - _build_fal_prompt(name, category)
  - _fal_generate_image(prompt, base_image_bytes|None)
  - _fal_text2img(prompt)

Wiring:
  ad_creative_gen.compose_ad_creative_banner() -> _fal_generate_image()
  Falls back to text2img when img2img is unavailable.
"""
from __future__ import annotations

import logging
import os
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

try:
    from instagram import banner_compose as banner_compose
except ImportError:
    banner_compose = None  # type: ignore[assignment]
from instagram.banner_compose import _fetch_image_bytes

logger = logging.getLogger(__name__)

FAL_MODEL = os.environ.get("FAL_MODEL_IMG2IMG", "fal-ai/nano-banana-2/edit")
FAL_MODEL_T2I = os.environ.get("FAL_MODEL_T2I", "fal-ai/flux/dev")
# Render at 2K and let _resize_to_canvas downsample to 1080 — small printed
# text on products (button labels, dials) comes out legible instead of the
# garbled glyphs 1K produced (Breville panel, 2026-06-10). Allowed values
# per the nano-banana-2 API: 0.5K, 1K, 2K, 4K.
FAL_IMG2IMG_RESOLUTION = os.environ.get("FAL_IMG2IMG_RESOLUTION", "2K")
FAL_FALLBACK_TIMEOUT = 120
REFERENCE_MAX_DIM = 1024

_PROMPT_BANNER = """You are a professional e-commerce product photographer specializing in \
high-converting affiliate marketing ads. Create a premium 1080x1080 square product image.

CRITICAL: Photograph the product "{name}" exactly as it appears — same shape, color, \
branding, every detail. Do NOT invent, modify, or add anything to the product itself.

Studio Setup:
- Dark charcoal gradient background (near-black edges, subtle gray center)
- Soft orange backlight glow (#FF6B00) behind and around the product
- Product sharp, centered, isolated with soft drop shadow
- Clean, professional, photorealistic lighting

Do NOT:
- Add white boxes, borders, frames, or backgrounds
- Add text, watermarks, logos, or captions
- Include other products, people, or scenes
- Use 3D renders, illustrations, or stylized effects
- Add anything except the product and its shadow

Keep 30% breathing room around the product for future text overlay. Square 1:1 only.
"""

_PROMPT_FALLBACK = """You are a professional product photographer. Create a 1080x1080 \
square image of {name}.

Photograph the product exactly as it is, isolated on a dark professional background \
with soft lighting. Product only — sharp, centered, no text, no borders, no additions. \
Dark charcoal backdrop with subtle orange accent light. Square 1:1, photorealistic.
"""


def _load_image_bytes(path_or_url: str) -> bytes | None:
    try:
        if path_or_url.startswith("http"):
            return _fetch_image_bytes(path_or_url, timeout=20)
        return Path(path_or_url).read_bytes()
    except Exception as exc:
        logger.warning("image load failed %s: %s", path_or_url, exc)
        return None


def _to_pil(data: bytes) -> Image.Image | None:
    try:
        return Image.open(BytesIO(data)).convert("RGB")
    except Exception as exc:
        logger.warning("PIL open failed (%d bytes): %s", len(data), exc)
        return None


def _publish_to_fal(pil: Image.Image) -> str | None:
    api_key = os.environ.get("FAL_KEY")
    if not api_key:
        logger.warning("FAL_KEY missing for upload")
        return None
    try:
        import fal_client
    except ImportError:
        logger.warning("fal_client not installed")
        return None
    try:
        return fal_client.upload_image(pil, format="jpeg")
    except Exception as exc:
        logger.warning("upload_image failed: %s", exc)
        return None


def _download_result(result: dict) -> bytes | None:
    images = ((result or {}).get("images") or [])
    if not images:
        return None
    url = images[0].get("url")
    if not url:
        return None
    return _fetch_image_bytes(url, timeout=40)


def _fal_subscribe(application: str, arguments: dict) -> dict | None:
    api_key = os.environ.get("FAL_KEY")
    if not api_key:
        return None
    try:
        import fal_client
    except ImportError:
        return None
    try:
        return fal_client.subscribe(
            application,
            arguments=arguments,
            with_logs=False,
            client_timeout=FAL_FALLBACK_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("subscribe(%s) failed: %s", application, exc)
        return None


def _fal_img2img(
    prompt: str,
    base_pil: Image.Image,
    ref_pils: tuple[Image.Image, ...] = (),
) -> bytes | None:
    image_url = _publish_to_fal(base_pil)
    if not image_url:
        logger.warning("FAL upload failed; img2img skipped")
        return None
    # First URL is the product photo; the rest are lifestyle/marketing
    # references. The prompt describes this ordering — a reference that
    # fails to upload is dropped rather than failing the generation.
    image_urls = [image_url]
    for ref in ref_pils:
        ref_url = _publish_to_fal(ref)
        if ref_url:
            image_urls.append(ref_url)
    result = _fal_subscribe(
        FAL_MODEL,
        {
            "prompt": prompt,
            "image_urls": image_urls,
            "aspect_ratio": "1:1",
            "resolution": FAL_IMG2IMG_RESOLUTION,
            "num_images": 1,
        },
    )
    if not result:
        return None
    return _download_result(result)


def _fal_text2img(prompt: str) -> bytes | None:
    result = _fal_subscribe(
        FAL_MODEL_T2I,
        {
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "num_images": 1,
        },
    )
    if not result:
        return None
    return _download_result(result)


def _fal_generate_image(
    prompt: str,
    base_image_bytes: bytes | None,
    reference_images: tuple[bytes, ...] | list[bytes] = (),
) -> bytes | None:
    """Dispatch img2img when we have a product photo; else text2img.

    ``reference_images`` are optional lifestyle/marketing JPEGs that ground
    the generation (Tavily / Facebook Ad Library). Unreadable entries are
    skipped.
    """
    pil = _to_pil(base_image_bytes) if base_image_bytes is not None else None
    if pil is not None:
        ref_pils = tuple(
            p for p in (_to_pil(b) for b in reference_images) if p is not None
        )
        out = _fal_img2img(prompt, pil, ref_pils)
        if out:
            return out
        logger.warning("img2img failed; falling back to text2img")
    return _fal_text2img(prompt)


def _build_fal_prompt(name: str, category: str) -> str:
    base = _PROMPT_BANNER if category else _PROMPT_FALLBACK
    return base.format(name=name, category=category or "Best Sellers")
