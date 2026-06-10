#!/usr/bin/env python3
"""
Generate CTA button variants (A and B) of the test banners for click-rate optimization.

Version A: "CHECK PRICE ON AMAZON →" (text-only button)
Version B: "CHECK PRICE" (shorter, emphasizes action)
"""
import json
from pathlib import Path

from banner_compose import compose_banner

# Test products from the fal_test_2026-06-09 batch
PRODUCTS = [
    {
        "name": "Apple 2026 MacBook Neo 13-inch Laptop with A18",
        "price": "589.99",
        "rating": 4.7,
        "reviews": "many",
        "review_count": 2300,
        "category": "Laptops",
    },
    {
        "name": "Apple AirPods Max",
        "price": "449.99",
        "rating": 4.6,
        "reviews": "many",
        "review_count": 1500,
        "category": "Audio",
    },
    {
        "name": "Beats Studio3 Wireless",
        "price": "91.22",
        "rating": 4.6,
        "reviews": "many",
        "review_count": 3200,
        "category": "Headphones",
    },
]

SOURCE_IMAGES = [
    "/mnt/e/GITHUB/hotproductsdot-v2/generated_images/fal_test_2026-06-09/1/variant.jpg",
    "/mnt/e/GITHUB/hotproductsdot-v2/generated_images/fal_test_2026-06-09/2/variant.jpg",
    "/mnt/e/GITHUB/hotproductsdot-v2/generated_images/fal_test_2026-06-09/3/variant.jpg",
]

OUTPUT_BASE = Path("/mnt/e/GITHUB/hotproductsdot-v2/generated_images/fal_test_2026-06-09_cta_variants")


def generate_variants():
    """Generate Versions A and B for each product."""
    for i, (product, source_img_path) in enumerate(zip(PRODUCTS, SOURCE_IMAGES), start=1):
        try:
            # Check if source exists
            source_path = Path(source_img_path)
            if not source_path.exists():
                print(f"⚠️  Skipping product {i}: source image not found at {source_img_path}")
                continue

            # Create output dirs
            for variant in ["a", "b"]:
                variant_dir = OUTPUT_BASE / f"{i}_{variant}"
                variant_dir.mkdir(parents=True, exist_ok=True)

                output_file = variant_dir / "banner.jpg"

                print(f"Generating {i}/{variant} ({product['name'][:40]}...) → {output_file}")
                compose_banner(
                    product=product,
                    product_image_url_or_path=source_img_path,
                    output_path=output_file,
                    cta_version=variant,
                )
                print(f"  ✓ Created {output_file}")

        except Exception as e:
            print(f"✗ Error generating variants for product {i}: {e}")


if __name__ == "__main__":
    generate_variants()
    print("\n✅ CTA variants generated successfully!")
    print(f"📂 Output: {OUTPUT_BASE}")
