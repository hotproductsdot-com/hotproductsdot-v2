#!/usr/bin/env python3
"""
Test banner generation with loosened cutout validation (90% threshold).
"""
from pathlib import Path
from banner_compose import compose_banner

# Test products with MacBook override
PRODUCTS = [
    {
        "name": "Apple 2026 MacBook Neo 13-inch Laptop with A18",
        "price": "589.99",
        "rating": 4.7,
        "reviews": "many",
        "review_count": 2300,
        "category": "Laptops",
    },
]

OUTPUT_BASE = Path("/mnt/e/GITHUB/hotproductsdot-v2/generated_images/test_banners_90pct_validation")

def test_generation():
    """Generate test banners with loosened validation."""
    for i, product in enumerate(PRODUCTS, start=1):
        try:
            variant_dir = OUTPUT_BASE / f"{i}_macbook_test"
            variant_dir.mkdir(parents=True, exist_ok=True)

            output_file = variant_dir / "banner.jpg"

            print(f"\n[{i}] {product['name']}")
            print(f"  Generating → {output_file}")

            # compose_banner will use PRODUCT_IMAGE_OVERRIDE_BY_SLUG
            # MacBook override is already defined
            compose_banner(
                product=product,
                product_image_url_or_path="",  # Will use override
                output_path=output_file,
                cta_version="b",  # Version B: "CHECK PRICE"
                use_card=False,  # Test direct placement without card
            )

            print(f"  ✓ Success - check {output_file}")

        except Exception as e:
            print(f"  ✗ Failed: {e}")

if __name__ == "__main__":
    print("=" * 70)
    print("Testing banner generation with 90% cutout validation threshold")
    print("=" * 70)
    test_generation()
    print(f"\n✅ Output directory: {OUTPUT_BASE}")
