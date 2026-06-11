#!/usr/bin/env python3
"""
Generate fresh product images via FAL with prompts optimized for clean product isolation.
Focuses on: isolated product, light background, no boxes or frames.
"""
import os
import json
from pathlib import Path

# Load FAL_KEY from .env before importing fal_client
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.startswith("FAL_KEY="):
                key = line.split("=", 1)[1].strip()
                os.environ["FAL_KEY"] = key
                break

import fal_client

FAL_KEY = os.environ.get("FAL_KEY")
if not FAL_KEY:
    raise ValueError("FAL_KEY not found in environment or .env")

fal_client.api_key = FAL_KEY

PRODUCTS = [
    {
        "name": "Apple AirPods Max",
        "prompt": "High-quality product photo of Apple AirPods Max wireless headphones, "
                  "isolated on a clean light background, professional studio lighting, "
                  "no boxes or frames, white or light gray seamless background, "
                  "sharp focus on the product, premium photography style",
        "slug": "airpods-max",
    },
    {
        "name": "Beats Studio3 Wireless",
        "prompt": "High-quality product photo of Beats Studio3 Wireless headphones, "
                  "isolated on a clean light background, professional studio lighting, "
                  "no boxes or frames, white or light gray seamless background, "
                  "sharp focus on the product, premium photography style",
        "slug": "beats-studio3",
    },
]

OUTPUT_DIR = Path("/mnt/e/GITHUB/hotproductsdot-v2/generated_images/fal_products_2026")

def generate_image(product: dict) -> str:
    """Generate image via FAL and return local path."""
    output_file = OUTPUT_DIR / f"{product['slug']}.jpg"
    output_dir = output_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🎨 Generating: {product['name']}")
    print(f"   Prompt: {product['prompt'][:80]}...")

    try:
        # Use FAL's standard image generation model
        result = fal_client.run(
            "fal-ai/flux-pro",  # High-quality image generation
            arguments={
                "prompt": product['prompt'],
                "image_size": {
                    "width": 1024,
                    "height": 1024
                },
                "num_inference_steps": 50,
                "guidance_scale": 7.5,
            },
        )

        if result and result.get("images"):
            image_url = result["images"][0].get("url")
            if image_url:
                print(f"   ✓ Generated: {image_url[:80]}...")

                # Download image
                import requests
                resp = requests.get(image_url, timeout=30)
                resp.raise_for_status()

                with open(output_file, "wb") as f:
                    f.write(resp.content)

                print(f"   ✓ Saved: {output_file}")
                return str(output_file)

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return None

def main():
    print("=" * 70)
    print("Generating product images with FAL (clean background, no boxes)")
    print("=" * 70)

    generated = {}
    for product in PRODUCTS:
        path = generate_image(product)
        if path:
            generated[product['slug']] = path

    print(f"\n✅ Generated {len(generated)} images:")
    for slug, path in generated.items():
        print(f"  {slug:30} → {path}")

    return generated

if __name__ == "__main__":
    main()
