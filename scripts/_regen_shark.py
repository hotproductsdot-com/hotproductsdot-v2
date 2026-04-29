"""Regen the Shark Stratos banner to verify the multi-component collage
defect (Image #4 the user reported) is fixed by _keep_largest_component."""
import os
import sys

sys.path.insert(0, "/mnt/e/GITHUB/hotproductsdot-v2")
os.chdir("/mnt/e/GITHUB/hotproductsdot-v2")

from instagram import banner_compose

product = {
    "name": "Shark Stratos Vacuum",
    "slug": "shark-stratos-vacuum",
    "category": "Home",
    "rating": 4.6,
    "reviews": 4318,
    "review_count": 4318,
    "price": "139.99",
}
src = "/mnt/e/GITHUB/hotproductsdot-v2/site/public/products/shark-stratos-vacuum.jpg"
out = "/tmp/banner_shark-stratos-vacuum.jpg"
try:
    banner_compose.compose_banner(product, src, out)
    print(f"composed → {out}")
except banner_compose.BannerQualityError as exc:
    print(f"REJECTED: {exc.reason}")
