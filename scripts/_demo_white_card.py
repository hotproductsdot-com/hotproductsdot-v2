"""Demo: white-card-on-dark-canvas banner approach.

No rembg, no cutout, no validators needed for product isolation. The
catalog image — whatever it is, multi-product collage or scene shot —
sits on its original white background, framed as a clean rounded white
card on the dark canvas. Predictable output for every source image.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, "/mnt/e/GITHUB/hotproductsdot-v2")
os.chdir("/mnt/e/GITHUB/hotproductsdot-v2")

from PIL import Image, ImageDraw, ImageFilter

from instagram import banner_compose
from instagram.banner_compose import (
    CANVAS,
    _add_kinetic_curves,
    _add_orange_glow,
    _add_text,
    _make_background,
)


def compose_white_card_banner(product: dict, src_path: str, out_path: str) -> str:
    src_img = Image.open(src_path).convert("RGB")

    # Card geometry: roughly 70% of canvas wide, ~55% tall, centered laterally
    # and pushed below the title block.
    card_w = 760
    card_h = 600
    padding = 28
    card_x = (CANVAS - card_w) // 2
    card_y = int(CANVAS * 0.33)

    # Scale source to fit inside card minus padding.
    inner_w = card_w - padding * 2
    inner_h = card_h - padding * 2
    src_img.thumbnail((inner_w, inner_h), Image.LANCZOS)

    canvas = _make_background()
    canvas = _add_orange_glow(canvas)
    canvas = _add_kinetic_curves(canvas)

    # Soft drop shadow behind the card.
    shadow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [card_x - 4, card_y + 12, card_x + card_w + 4, card_y + card_h + 22],
        radius=28,
        fill=(0, 0, 0, 140),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
    canvas = Image.alpha_composite(canvas, shadow)

    # White card with rounded corners.
    card_layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_layer)
    cd.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=24,
        fill=(255, 255, 255, 255),
    )
    canvas = Image.alpha_composite(canvas, card_layer)

    # Paste the source image centered inside the card.
    img_x = card_x + (card_w - src_img.width) // 2
    img_y = card_y + (card_h - src_img.height) // 2
    canvas.paste(src_img, (img_x, img_y))

    canvas = _add_text(canvas, product)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(
        str(out),
        "JPEG",
        quality=93,
        optimize=True,
        progressive=False,
        subsampling=0,
    )
    return str(out)


CASES = [
    {
        "product": {
            "name": "Husqvarna Automower 450X Robotic Lawn Mower",
            "category": "Gardening",
            "price": "1799.99",
            "rating": 4.6,
            "reviews": 2800,
            "review_count": 2800,
            "bsr": 4,
            "slug": "husqvarna-automower-450x-robotic-lawn-mower",
        },
        "src_slug": "husqvarna-automower-450x-robotic-lawn-mower",
    },
    {
        "product": {
            "name": "Shark Stratos Vacuum",
            "category": "Home",
            "price": "139.99",
            "rating": 4.6,
            "reviews": 4318,
            "review_count": 4318,
            "slug": "shark-stratos-vacuum",
        },
        "src_slug": "shark-stratos-vacuum",
    },
    {
        "product": {
            "name": "Autonomous Standing Desk",
            "category": "Furniture",
            "price": "169.99",
            "rating": 4.7,
            "reviews": 461,
            "review_count": 461,
            "slug": "autonomous-standing-desk",
        },
        "src_slug": "autonomous-standing-desk",
    },
    {
        "product": {
            "name": "Apple Mac Mini M4 (2024)",
            "category": "Desktops & Mini PCs",
            "price": "599",
            "rating": 4.8,
            "reviews": 2779,
            "review_count": 2779,
            "slug": "apple-mac-mini-m4-2024",
        },
        "src_slug": "apple-mac-mini-m4-2024",
    },
]

for case in CASES:
    src = f"/mnt/e/GITHUB/hotproductsdot-v2/site/public/products/{case['src_slug']}.jpg"
    out = f"/tmp/whitecard_{case['src_slug']}.jpg"
    print(f"compose: {case['product']['name']}")
    compose_white_card_banner(case["product"], src, out)
    print(f"  -> {out}")
