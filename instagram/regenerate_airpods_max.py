#!/usr/bin/env python3
"""Regenerate AirPods Max with more specific prompt."""
import os
from pathlib import Path

# Load FAL_KEY
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.startswith("FAL_KEY="):
                os.environ["FAL_KEY"] = line.split("=", 1)[1].strip()
                break

import fal_client
import requests

fal_client.api_key = os.environ.get("FAL_KEY")

OUTPUT_FILE = Path("/mnt/e/GITHUB/hotproductsdot-v2/generated_images/fal_products_2026/airpods-max.jpg")

# More specific prompt: emphasize OVER-EAR, not earbuds
PROMPT = (
    "Professional product photo of Apple AirPods Max over-ear wireless headphones. "
    "Silver aluminum headband design with ear cups. "
    "NOT earbuds, NOT AirPods Pro. Large over-the-head style headphones. "
    "Isolated on clean light gray background, studio lighting, no boxes or frames, "
    "sharp focus, premium photography style"
)

print("🎨 Regenerating AirPods Max (over-ear headphones)")
print(f"   Prompt: {PROMPT[:80]}...")

try:
    result = fal_client.run(
        "fal-ai/flux-pro",
        arguments={
            "prompt": PROMPT,
            "image_size": {"width": 1024, "height": 1024},
            "num_inference_steps": 50,
            "guidance_scale": 7.5,
        },
    )

    if result and result.get("images"):
        image_url = result["images"][0].get("url")
        if image_url:
            print(f"   ✓ Generated: {image_url[:80]}...")

            # Download
            resp = requests.get(image_url, timeout=30)
            resp.raise_for_status()

            OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(OUTPUT_FILE, "wb") as f:
                f.write(resp.content)

            print(f"   ✓ Saved: {OUTPUT_FILE}")

except Exception as e:
    print(f"   ✗ Error: {e}")

