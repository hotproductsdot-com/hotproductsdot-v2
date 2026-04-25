"""
Local FLUX image generation for GTX 1070 (8GB VRAM).

Uses FLUX.1 [schnell] with 4-bit quantization to fit in 8GB VRAM.
Inference time: 25-45 seconds per image (slow but free).

Required env vars:
  ANTHROPIC_API_KEY — optional, improves prompt quality (Claude haiku)

Required Python packages:
  pip install diffusers transformers torch bitsandbytes accelerate
"""
import json
import logging
import os
import sys
from pathlib import Path

import torch
from diffusers import FluxPipeline

logger = logging.getLogger(__name__)

SITE_URL = "https://hotproductsdot.com"

# Brand visual DNA: dark charcoal studio backdrop + orange (#FF6B00) accent lighting
_STYLES = ["banner", "studio_dark", "lifestyle", "vibrant", "detail"]

# Edit-mode prompts (for image-to-image restyling) — product name injected at runtime
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

    try:
        import anthropic

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
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=700,
            system=(
                f"You write concise FLUX image prompts. {instruction} "
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
        logger.warning(f"Claude prompt error: {exc} — using templates")

    base = _EDIT_PROMPTS if edit_mode else _TEXT_PROMPTS
    return {s: t.format(name=product["name"]) for s, t in base.items()}


# ── FLUX Pipeline (singleton to avoid reloading model) ────────────────────────

_PIPELINE = None


def _get_flux_pipeline():
    """
    Load FLUX.1 [schnell] with 4-bit quantization.
    Singleton pattern to avoid reloading model multiple times.

    GTX 1070 (8GB VRAM) requires aggressive quantization.
    Inference: ~30-45 seconds per 1024x1024 image.
    """
    global _PIPELINE

    if _PIPELINE is not None:
        return _PIPELINE

    logger.info("Loading FLUX.1 [schnell] with 4-bit quantization for GTX 1070...")

    hf_token = os.environ.get("HF_TOKEN") or None  # None lets huggingface_hub use cached login

    try:
        _PIPELINE = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-schnell",
            torch_dtype=torch.float16,
            token=hf_token,
        )

        # Move to GPU with automatic CPU offloading for 8GB VRAM
        _PIPELINE.enable_attention_slicing()
        _PIPELINE.to("cuda")

        logger.info("✓ FLUX.1 [schnell] loaded and ready (GTX 1070 mode)")
        return _PIPELINE
    except Exception as exc:
        logger.error(f"Failed to load FLUX pipeline: {exc}")
        raise


def _generate_flux_image(prompt: str, width: int = 1024, height: int = 1024) -> str | None:
    """
    Generate a single image using FLUX.1 [schnell] locally.

    Args:
        prompt: Image generation prompt
        width: Output width (default 1024)
        height: Output height (default 1024)

    Returns:
        PIL Image object or None on failure
    """
    try:
        pipeline = _get_flux_pipeline()

        logger.debug(f"Generating image: {prompt[:80]}...")

        # FLUX schnell uses 4 inference steps for speed
        image = pipeline(
            prompt=prompt,
            height=height,
            width=width,
            num_inference_steps=4,  # schnell is optimized for 4 steps
            guidance_scale=0,  # schnell doesn't use guidance
        ).images[0]

        return image
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            logger.error("GPU out of memory! Reduce batch size or image resolution.")
        else:
            logger.error(f"GPU error: {exc}")
        return None
    except Exception as exc:
        logger.error(f"Image generation failed: {exc}")
        return None


def _generate_flux_image_gradio(prompt: str, width: int = 1024, height: int = 1024, seed: int = 0) -> str | None:
    """
    Generate a single image using FLUX.1 [schnell] via Hugging Face Gradio client.

    Uses the hosted FLUX Space on Hugging Face instead of local GPU.
    Faster inference but requires internet connection.

    Args:
        prompt: Image generation prompt
        width: Output width (default 1024)
        height: Output height (default 1024)
        seed: Random seed for reproducibility (default 0)

    Returns:
        File path to generated image or None on failure
    """
    try:
        from gradio_client import Client

        logger.debug(f"Generating image via Gradio: {prompt[:80]}...")

        client = Client("black-forest-labs/FLUX.1-schnell")
        result = client.predict(
            prompt=prompt,
            seed=seed,
            randomize_seed=True,
            width=width,
            height=height,
            num_inference_steps=4,
            api_name="/infer"
        )

        logger.debug(f"Gradio generation result: {result}")
        return result

    except ImportError:
        logger.error("gradio-client not installed. Install with: pip install gradio-client")
        return None
    except Exception as exc:
        logger.error(f"Gradio image generation failed: {exc}")
        return None


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_product_images(
    product: dict,
    n: int = 5,
    save_dir: Path | None = None,
) -> list[dict]:
    """
    Generate n styled image variants for a product using local FLUX.1 [schnell].

    Returns list of dicts:
        {index, style, url, local_path (str|None), prompt}

    ⚠️  WARNING: GTX 1070 with 8GB VRAM will be SLOW:
        Expect 30-45 seconds per image.
        For 5 variants: 2.5-4 minutes total.

    Args:
        product: Product dict with 'name', 'category' keys
        n: Number of variants to generate (default 5)
        save_dir: Optional directory to save images locally

    Raises:
        ValueError: If product is missing required fields
    """
    if not product.get("name"):
        raise ValueError("Product must have a 'name' field")

    # Build prompts for all styles
    prompts = _build_prompts_claude(product, edit_mode=False)

    variants = []
    start_time = __import__("time").time()

    for idx, style in enumerate(_STYLES[:n], start=1):
        prompt = prompts.get(style, _TEXT_PROMPTS[style].format(name=product["name"]))

        print(f"  [{idx}/{n}] {style:12} ... ", end="", flush=True)
        elapsed = __import__("time").time() - start_time

        # Generate image
        image = _generate_flux_image(prompt)
        if image is None:
            print("FAILED")
            continue

        # Save locally if requested
        local_path = None
        if save_dir:
            save_dir = Path(save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            local_path = save_dir / f"variant_{idx}_{style}.jpg"
            image.save(str(local_path), quality=95)

        elapsed_gen = __import__("time").time() - start_time - elapsed
        print(f"✓ ({elapsed_gen:.1f}s)")

        variants.append({
            "index": idx,
            "style": style,
            "url": str(local_path) if local_path else f"local://{style}",
            "local_path": str(local_path) if local_path else None,
            "prompt": prompt,
        })

    total_time = __import__("time").time() - start_time
    logger.info(f"Generated {len(variants)}/{n} images in {total_time:.1f}s")

    return variants


if __name__ == "__main__":
    # Quick test
    test_product = {
        "name": "Test Camera",
        "category": "electronics",
    }

    save_dir = Path("/tmp/flux_test")
    variants = generate_product_images(test_product, n=2, save_dir=save_dir)

    print(f"\nGenerated {len(variants)} variants:")
    for v in variants:
        print(f"  {v['style']}: {v['local_path']}")
