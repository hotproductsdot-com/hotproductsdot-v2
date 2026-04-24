"""
HotProducts TikTok vertical frame compositor.

Creates 1080×1920 (9:16) branded frames, one per variant index (0–4). Each
variant uses the same brand DNA (dark charcoal gradient + orange kinetic
curves) but a different hook + footer role so a 5-frame video feels like a
story rather than five copies of the same banner.

Reuses the 1080×1080 banner pipeline helpers (background, curves, product
compositing, badge logic) from `instagram.banner_compose`.
"""
import re
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter

from instagram import banner_compose as bc

# ── Canvas ────────────────────────────────────────────────────────────────────
CANVAS_W = 1080
CANVAS_H = 1920

BG_DARK   = bc.BG_DARK
BG_LIFT   = bc.BG_LIFT
ORANGE    = bc.ORANGE
WHITE     = bc.WHITE
WHITE_DIM = bc.WHITE_DIM
PILL_BG   = bc.PILL_BG


# ── Stage 1: background ───────────────────────────────────────────────────────

def _make_background() -> Image.Image:
    base = Image.new("RGBA", (CANVAS_W, CANVAS_H), (*BG_DARK, 255))
    glow = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = CANVAS_W // 2, int(CANVAS_H * 0.35)
    gd.ellipse([cx - 560, cy - 340, cx + 560, cy + 340], fill=(*BG_LIFT, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=120))
    lift = Image.new("RGBA", (CANVAS_W, CANVAS_H), (*BG_LIFT, 255))
    return Image.composite(lift, base, glow)


def _add_orange_glow(canvas: Image.Image) -> Image.Image:
    glow = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = CANVAS_W // 2, int(CANVAS_H * 0.55)
    gd.ellipse([cx - 380, cy - 170, cx + 380, cy + 170], fill=(*ORANGE, 52))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=90))
    return Image.alpha_composite(canvas, glow)


def _add_kinetic_curves(canvas: Image.Image) -> Image.Image:
    overlay = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    W, H = CANVAS_W, CANVAS_H
    curves = [
        ((0,       H * .22), (W * .18, H * .06), (W * .32, H * .25), (W * .10, H * .40)),
        ((W,       H * .08), (W * .78, H * .02), (W * .62, H * .22), (W * .92, H * .32)),
        ((W * .05, H),       (W * .22, H * .88), (W * .36, H * .96), (W * .14, H * .82)),
        ((W,       H * .62), (W * .78, H * .78), (W * .90, H * .92), (W, H)),
    ]
    for p0, p1, p2, p3 in curves:
        pts = bc._bezier(
            (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])),
            (int(p2[0]), int(p2[1])), (int(p3[0]), int(p3[1])),
        )
        for width, alpha in [(5, 55), (3, 85), (1, 120)]:
            draw.line(pts, fill=(*ORANGE, alpha), width=width)
    return Image.alpha_composite(canvas, overlay)


# ── Stage 2: product shot ─────────────────────────────────────────────────────

def _add_product(canvas: Image.Image, product_img: Image.Image) -> Image.Image:
    dark_bg = bc._is_dark_background(product_img)
    prod = bc._apply_ellipse_blend(product_img) if dark_bg else bc._remove_white_bg(product_img)

    max_w = int(CANVAS_W * 0.82)
    max_h = int(CANVAS_H * 0.44)
    prod.thumbnail((max_w, max_h), Image.LANCZOS)

    cx = (CANVAS_W - prod.width) // 2
    cy = int(CANVAS_H * 0.38)

    shadow = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sx = cx + prod.width // 2
    sy = cy + prod.height + 14
    sd.ellipse([sx - prod.width // 3, sy - 18, sx + prod.width // 3, sy + 18], fill=(0, 0, 0, 130))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=22))
    canvas = Image.alpha_composite(canvas, shadow)

    canvas.paste(prod, (cx, cy), mask=prod.split()[3])
    return canvas


# ── Stage 3: variant-specific text ────────────────────────────────────────────

# Five frames tell a mini-story: hook → proof → reaction → value → CTA.
FRAME_TEMPLATES: list[dict[str, str]] = [
    {"top": "STOP SCROLLING", "sub": "you need to see this",       "role": "BRAND"},
    {"top": "{reviews} REVIEWS", "sub": "can't all be wrong",      "role": "BRAND"},
    {"top": "LOOK AT THIS",   "sub": "{rating} stars. no cap.",    "role": "PRICE"},
    {"top": "GAME CHANGER",   "sub": "trending on amazon",         "role": "PRICE"},
    {"top": "LINK IN BIO",    "sub": "tap the link to grab yours", "role": "CTA"},
]


def _format_reviews(reviews: str | int) -> str:
    try:
        n = int(re.sub(r"[^0-9]", "", str(reviews)) or "0")
    except ValueError:
        return "MANY"
    if n >= 1_000_000:
        return f"{n // 1_000_000}M+"
    if n >= 1_000:
        return f"{n // 1_000}K+"
    return f"{n}+" if n else "MANY"


def _resolve_hook(template: dict[str, str], product: dict) -> tuple[str, str]:
    top = template["top"].format(
        reviews=_format_reviews(product.get("review_count") or product.get("reviews") or 0),
        rating=f'{float(product.get("rating") or 4.5):.1f}',
    )
    sub = template["sub"].format(
        reviews=_format_reviews(product.get("review_count") or product.get("reviews") or 0),
        rating=f'{float(product.get("rating") or 4.5):.1f}',
    )
    return top.upper(), sub


def _draw_top_block(canvas: Image.Image, product: dict, template: dict[str, str]) -> Image.Image:
    draw = ImageDraw.Draw(canvas)
    top_text, sub_text = _resolve_hook(template, product)

    # Badge
    badge_font = bc._load_font(28, bold=True)
    badge_text = bc._pick_badge(product)
    bb = draw.textbbox((0, 0), badge_text, font=badge_font)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    bx = (CANVAS_W - bw - 40) // 2
    by = 110
    draw.rounded_rectangle([bx, by, bx + bw + 40, by + bh + 22],
                           radius=(bh + 22) // 2, fill=(*ORANGE, 235))
    draw.text((bx + 20, by + 11), badge_text, font=badge_font, fill=WHITE)

    # Hook headline (up to 2 lines, shrink if needed)
    size = 130
    hook_font = bc._load_font(size, bold=True)
    while size > 72 and draw.textbbox((0, 0), top_text, font=hook_font)[2] > CANVAS_W - 80:
        size -= 8
        hook_font = bc._load_font(size, bold=True)

    lines = bc._wrap(top_text, hook_font, CANVAS_W - 80, draw)[:2]
    y = by + bh + 22 + 36
    for line in lines:
        tx = bc._center_x(line, hook_font, draw)
        # shadow
        draw.text((tx + 3, y + 3), line, font=hook_font, fill=(0, 0, 0))
        draw.text((tx, y), line, font=hook_font, fill=WHITE)
        y += bc._text_h(line, hook_font, draw) + 10

    # Subline
    sub_font = bc._load_font(38, bold=False)
    sx = bc._center_x(sub_text, sub_font, draw)
    draw.text((sx, y + 12), sub_text, font=sub_font, fill=WHITE_DIM)

    return canvas


def _draw_footer(canvas: Image.Image, product: dict, role: str) -> Image.Image:
    draw = ImageDraw.Draw(canvas)

    if role == "PRICE":
        price_text = bc._format_price(product.get("price", ""))
        label = "ONLY"
        label_font = bc._load_font(44, bold=True)
        price_font = bc._load_font(170, bold=True)

        label_w = draw.textbbox((0, 0), label, font=label_font)[2]
        price_w = draw.textbbox((0, 0), price_text, font=price_font)[2]
        block_y = int(CANVAS_H * 0.80)

        lx = (CANVAS_W - label_w) // 2
        draw.text((lx, block_y), label, font=label_font, fill=WHITE_DIM)

        px = (CANVAS_W - price_w) // 2
        py = block_y + 54
        # glow behind price
        glow = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([px - 60, py + 10, px + price_w + 60, py + 190], fill=(*ORANGE, 90))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=55))
        canvas = Image.alpha_composite(canvas, glow)
        draw = ImageDraw.Draw(canvas)
        draw.text((px + 3, py + 3), price_text, font=price_font, fill=(0, 0, 0))
        draw.text((px, py), price_text, font=price_font, fill=ORANGE)
        return canvas

    if role == "CTA":
        cta_text = "TAP LINK IN BIO"
        cta_font = bc._load_font(58, bold=True)
        cb = draw.textbbox((0, 0), cta_text, font=cta_font)
        cw, ch = cb[2] - cb[0], cb[3] - cb[1]
        pad_x, pad_y = 50, 32
        cx = (CANVAS_W - cw - pad_x * 2) // 2
        cy = int(CANVAS_H * 0.85)
        draw.rounded_rectangle(
            [cx, cy, cx + cw + pad_x * 2, cy + ch + pad_y * 2],
            radius=(ch + pad_y * 2) // 2, fill=(*ORANGE, 245),
        )
        draw.text((cx + pad_x, cy + pad_y - 4), cta_text, font=cta_font, fill=WHITE)

        brand_font = bc._load_font(32, bold=False)
        brand = "hotproductsdot.com"
        bx = bc._center_x(brand, brand_font, draw)
        draw.text((bx, cy + ch + pad_y * 2 + 24), brand, font=brand_font, fill=WHITE_DIM)
        return canvas

    # BRAND footer — pill with brand name
    pill_font = bc._load_font(32, bold=True)
    pill_label = "hotproductsdot.com"
    lw = draw.textbbox((0, 0), pill_label, font=pill_font)[2]
    pad = 28
    pill_h = 64
    pw = lw + pad * 2
    px = (CANVAS_W - pw) // 2
    py = int(CANVAS_H * 0.88)
    draw.rounded_rectangle(
        [px, py, px + pw, py + pill_h],
        radius=pill_h // 2, fill=PILL_BG, outline=(*ORANGE, 120), width=2,
    )
    lh = draw.textbbox((0, 0), pill_label, font=pill_font)[3]
    draw.text((px + pad, py + (pill_h - lh) // 2 - 2),
              pill_label, font=pill_font, fill=WHITE)
    return canvas


# ── Public API ────────────────────────────────────────────────────────────────

def _load_product_image(source: str | Path) -> Image.Image:
    src = str(source)
    if src.startswith("http"):
        resp = requests.get(src, timeout=30)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGB")
    return Image.open(src).convert("RGB")


def compose_frame(
    product: dict,
    product_image_url_or_path: str | Path,
    output_path: str | Path,
    variant_idx: int,
) -> str:
    """Render a single 1080×1920 frame and save as JPEG. variant_idx ∈ [0, 4]."""
    if not 0 <= variant_idx < len(FRAME_TEMPLATES):
        raise ValueError(f"variant_idx must be 0..{len(FRAME_TEMPLATES) - 1}")

    prod_img = _load_product_image(product_image_url_or_path)
    template = FRAME_TEMPLATES[variant_idx]

    canvas = _make_background()
    canvas = _add_orange_glow(canvas)
    canvas = _add_kinetic_curves(canvas)
    canvas = _add_product(canvas, prod_img)
    canvas = _draw_top_block(canvas, product, template)
    canvas = _draw_footer(canvas, product, template["role"])

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(
        str(out), "JPEG", quality=92, optimize=True,
        progressive=False, subsampling=0,
    )
    return str(out)


def compose_all_frames(
    product: dict,
    product_image_url_or_path: str | Path,
    output_dir: str | Path,
) -> list[str]:
    """Render all 5 frames for a product. Returns ordered list of file paths."""
    out_dir = Path(output_dir)
    paths = []
    for idx in range(len(FRAME_TEMPLATES)):
        p = out_dir / f"frame_{idx:02d}.jpg"
        compose_frame(product, product_image_url_or_path, p, idx)
        paths.append(str(p))
    return paths
