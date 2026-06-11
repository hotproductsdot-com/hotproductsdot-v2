#!/usr/bin/env python3
"""
Generate final banners for all three products with 90% cutout validation threshold.
Uses fresh FAL-generated source images for AirPods Max and Beats, custom Amazon image for MacBook.
"""
from pathlib import Path
from banner_compose import compose_banner

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

OUTPUT_BASE = Path("/mnt/e/GITHUB/hotproductsdot-v2/generated_images/final_banners_90pct")

def generate_all():
    """Generate final banners for all products."""
    print("=" * 70)
    print("Generating final banners (90% cutout validation, no white boxes)")
    print("=" * 70)

    for i, product in enumerate(PRODUCTS, start=1):
        try:
            variant_dir = OUTPUT_BASE / f"{i}_{product['name'].split()[0:2]}" / f"banner_{i}"
            variant_dir.mkdir(parents=True, exist_ok=True)

            output_file = variant_dir / "banner.jpg"

            print(f"\n[{i}/3] {product['name']}")
            print(f"      → {output_file}")

            # Use PRODUCT_IMAGE_OVERRIDE_BY_SLUG system
            compose_banner(
                product=product,
                product_image_url_or_path="",  # Will use override
                output_path=output_file,
                cta_version="b",  # "CHECK PRICE"
                use_card=False,   # No white box
            )

            print(f"      ✅ Success")

        except Exception as e:
            print(f"      ❌ Error: {e}")

    print(f"\n{'=' * 70}")
    print(f"✅ Banners saved to: {OUTPUT_BASE}")

if __name__ == "__main__":
    generate_all()
