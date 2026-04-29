"""Investigation helper: regenerate today's 4 IG banners locally so we can
see the actual defects the user is reporting on Instagram.

Today's 4 posts (per marketing-campaigns/post_log.csv on origin/main):
  1. Husqvarna Automower 450X Robotic Lawn Mower
  2. Apple Mac Mini M4 (2024)
  3. Sony A7R V Camera
  4. HOROW Black Smart Toilet with Pump and Bidet Built In

Outputs go to /tmp/banner_*.jpg for inspection.
"""
import os
import sys

sys.path.insert(0, "/mnt/e/GITHUB/hotproductsdot-v2")
os.chdir("/mnt/e/GITHUB/hotproductsdot-v2")

from instagram import banner_compose

TODAY = [
    {
        "name": "Husqvarna Automower 450X Robotic Lawn Mower",
        "category": "Gardening",
        "price": "1799.99",
        "rating": 4.6,
        "reviews": 2800,
        "review_count": 2800,
        "bsr": 4,
        "potential": 8,
        "slug": "husqvarna-automower-450x-robotic-lawn-mower",
    },
    {
        "name": "Apple Mac Mini M4 (2024)",
        "category": "Desktops & Mini PCs",
        "price": "599",
        "rating": 4.8,
        "reviews": 2779,
        "review_count": 2779,
        "bsr": 3,
        "potential": 9,
        "slug": "apple-mac-mini-m4-2024",
    },
    {
        "name": "Sony A7R V Camera",
        "category": "Photography",
        "price": "3298",
        "rating": 4.6,
        "reviews": 273,
        "review_count": 273,
        "bsr": 2,
        "potential": 8,
        "slug": "sony-a7r-v-camera",
    },
    {
        "name": "HOROW Black Smart Toilet with Pump and Bidet Built In",
        "category": "Smart Home",
        "price": "990",
        "rating": 4.6,
        "reviews": 189,
        "review_count": 189,
        "bsr": 1,
        "potential": 9,
        "slug": "horow-black-smart-toilet-with-pump-and-bidet-built-in",
    },
]

for p in TODAY:
    src = f"/mnt/e/GITHUB/hotproductsdot-v2/site/public/products/{p['slug']}.jpg"
    out = f"/tmp/banner_{p['slug']}.jpg"
    print(f"compose: {p['name']}")
    try:
        banner_compose.compose_banner(p, src, out)
        print(f"  ok -> {out}")
    except banner_compose.BannerQualityError as exc:
        print(f"  REJECTED: {exc.reason}")
