"""Dry-run the banner pipeline for today's 4 slugs and report which path
each one takes (composed vs quality-blocked). This mirrors the runner's
exact code path through banner_compose, including the rembg model resolution
and the validator gates."""
import os
import sys
from pathlib import Path

sys.path.insert(0, "/mnt/e/GITHUB/hotproductsdot-v2")
os.chdir("/mnt/e/GITHUB/hotproductsdot-v2")

from PIL import Image

from instagram import banner_compose

SLUGS = [
    "husqvarna-automower-450x-robotic-lawn-mower",
    "apple-mac-mini-m4-2024",
    "sony-a7r-v-camera",
    "horow-black-smart-toilet-with-pump-and-bidet-built-in",
]

for slug in SLUGS:
    src = f"/mnt/e/GITHUB/hotproductsdot-v2/site/public/products/{slug}.jpg"
    out = f"/tmp/pipe_{slug}.jpg"
    print(f"\n{slug}")

    rembg_model = banner_compose.REMBG_MODEL_BY_SLUG.get(slug)
    print(f"  rembg_model_override: {rembg_model!r}")

    img = Image.open(src).convert("RGB")
    if not rembg_model:
        ok, reason = banner_compose._validate_source_image(img)
        print(f"  source check (no override): ok={ok} reason={reason!r}")
    else:
        print(f"  source check skipped (override present)")

    p = {"slug": slug, "name": slug.replace("-", " "), "category": "Test", "rating": 4.5, "reviews": 100, "review_count": 100, "price": "100"}
    try:
        banner_compose.compose_banner(p, src, out)
        print(f"  RESULT: composed → {out}")
    except banner_compose.BannerQualityError as exc:
        print(f"  RESULT: QUARANTINED ({exc.reason})")
    except Exception as exc:
        print(f"  RESULT: ERROR {type(exc).__name__}: {exc}")
