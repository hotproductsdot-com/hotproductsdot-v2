#!/usr/bin/env python3
"""Run 3 local Instagram post test draws through FAL.AI + text overlay.

Pipeline per product (mirrors ad_creative_gen.compose_ad_creative_banner):
  1. Load the real catalog product photo (site/public/products/{slug}.jpg).
  2. FAL img2img grounded on that photo — the actual product is rendered,
     never a text2img hallucination (the 2026-06-10 Beats banner showed a
     Skullcandy headphone because text2img got no product image).
  3. Resize the FAL render to the full 1080x1080 canvas and overlay the
     headline/rating/price text stack directly — NO white card, no box.
"""

from __future__ import annotations

import csv, os, re, sys
from pathlib import Path
from datetime import datetime

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

ENV_PATH = REPO / ".env"
if ENV_PATH.exists():
    for raw_line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if re.match(r"^[A-Z][A-Z0-9_]*$", key.strip()):
            os.environ[key.strip()] = value.strip()

from instagram.image_gen_fal import _build_fal_prompt, _fal_generate_image
from instagram.banner_compose import CANVAS, _add_text
from PIL import Image
from io import BytesIO


def load_products(n=3):
    p = REPO / "products" / "top-1000.csv"
    rows = []
    with p.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("Product Name") or "").strip()
            if not name:
                continue
            try:
                rating = float((row.get("Rating") or "0").strip() or "0")
            except ValueError:
                rating = 0.0
            reviews_raw = (row.get("Review Count") or "").strip()
            reviews = int("".join(ch for ch in reviews_raw if ch.isdigit()) or "0")
            amazon = (row.get("Amazon URL") or "").strip()
            # Upper bound matters: a corrupted row once carried rating=16685
            # (a review count written into the Rating column) and `>= 4.5`
            # alone let it straight onto a banner as "16685.0/5".
            if not (4.5 <= rating <= 5.0) or reviews < 100 or not amazon:
                continue
            slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
            photo = REPO / "site" / "public" / "products" / f"{slug}.jpg"
            if not photo.is_file():
                continue  # img2img needs the real product photo
            rows.append({
                "name": name,
                "slug": slug,
                "category": (row.get("Category") or "Best Sellers").strip(),
                "price": (row.get("Price Range") or "Check price").strip(),
                "rating": rating,
                "reviews": str(reviews),
                "review_count": reviews,
                "amazon_url": amazon,
                "photo": str(photo),
            })
            if len(rows) >= n:
                break
    return rows


def _short_review_count(n: int) -> str:
    if n >= 1000:
        return f"{n/1000:.1f}k reviews"
    return f"{n} reviews"


def caption(product: dict) -> str:
    review_line = f"⭐ {product['rating']}/5  ·  {_short_review_count(product['review_count'])}"
    return "\n".join([
        "Stop scrolling. This gadget just made our shortlist 👀",
        "",
        review_line,
        f"💰 {product['price']}",
        "",
        "Save this one for when you finally pull the trigger 💾",
        "",
        "🔗 Tap the link in our bio for the full review + best price",
        "",
        " ".join([
            "#hotproducts", "#hotproductsdaily", "#amazonfinds", "#amazonmusthaves",
            "#productreview", "#dealoftheday", "#bestofamazon",
        ]),
    ])


def _pad_for_breathing_room(photo_bytes: bytes) -> bytes:
    """Re-frame the product photo with margin before sending it to FAL.

    nano-banana edit preserves the input composition: a frame-filling
    catalog photo comes back frame-filling and collides with the
    headline/price overlay. Scaling the product to ~58% of a white
    1080x1080 canvas (lower-center) makes the render keep that breathing
    room; FAL repaints the uniform white background to the dark studio
    look, so no box or seam survives.
    """
    img = Image.open(BytesIO(photo_bytes)).convert("RGB")
    max_side = int(CANVAS * 0.58)
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    base = Image.new("RGB", (CANVAS, CANVAS), (255, 255, 255))
    x = (CANVAS - img.width) // 2
    y = int(CANVAS * 0.60) - img.height // 2
    base.paste(img, (x, y))
    buf = BytesIO()
    base.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def compose(fal_bytes: bytes, product: dict, out_path: Path) -> None:
    """FAL render → full-canvas background + text overlay. No card, no box."""
    img = Image.open(BytesIO(fal_bytes)).convert("RGB")
    if img.size != (CANVAS, CANVAS):
        img = img.resize((CANVAS, CANVAS), Image.LANCZOS)
    canvas = _add_text(img.convert("RGBA"), product)
    canvas.convert("RGB").save(
        str(out_path), "JPEG",
        quality=93, optimize=True, progressive=False, subsampling=0,
    )


def main() -> int:
    products = load_products(3)
    print(f"Selected {len(products)} products")
    out_root = REPO / "generated_images" / f"fal_test_{datetime.now().date().isoformat()}"

    for idx, product in enumerate(products, start=1):
        out_dir = out_root / str(idx)
        out_dir.mkdir(parents=True, exist_ok=True)
        prompt = _build_fal_prompt(product["name"], product["category"])
        print(f"\n[{idx}/3] {product['name']}")
        print(f"  PROMPT: {prompt[:120]}...")
        base_bytes = _pad_for_breathing_room(Path(product["photo"]).read_bytes())
        img_bytes = _fal_generate_image(prompt, base_bytes)
        if not img_bytes:
            print("  FAL returned nothing")
            continue
        variant = out_dir / "variant.jpg"
        variant.write_bytes(img_bytes)
        banner = out_dir / "banner.jpg"
        compose(img_bytes, product, banner)
        print(f"  variant -> {variant}")
        print(f"  banner  -> {banner}")
        print("\n  CAPTION:")
        print(f"  {caption(product).replace(chr(10), chr(10) + '  ')}")

    print(f"\nOutputs: {out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
