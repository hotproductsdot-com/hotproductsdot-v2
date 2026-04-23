"""
HotProducts Instagram banner compositor.

Creates a 1080×1080 branded banner per the hotproducts-banner-style skill:
  - Dark radial gradient backdrop (#0f0f0f → #2c2c2c center glow)
  - Bold white display headline (product name, max 6 words)
  - Drawn star rating + review count subline
  - Price formatted with $ prefix in orange
  - Floating product image (auto: vignette blend for dark bg, white-removal for light bg)
  - Thin orange (#FF6B00) kinetic bezier curves in corners
  - Ambient orange glow behind product
  - Stat pills: brand name, category

Requires: Pillow>=10.0.0

Public upload:
  Use upload_to_imgbb(path, api_key, name="slug-banner") so ImgBB titles are per-product (not "banner").
  suitable for the Instagram Graph API. Set IMGBB_API_KEY in .env to enable.
"""
import re
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── Brand constants ───────────────────────────────────────────────────────────
CANVAS    = 1080
BG_DARK   = (15, 15, 15)
BG_LIFT   = (44, 44, 44)
ORANGE    = (255, 107, 0)
WHITE     = (255, 255, 255)
WHITE_DIM = (190, 190, 190)
PILL_BG   = (38, 38, 38)


# ── Font loader ───────────────────────────────────────────────────────────────

def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [
            "/mnt/c/Windows/Fonts/ariblk.ttf",
            "/mnt/c/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
        if bold
        else [
            "/mnt/c/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
    )
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── Text / layout helpers ─────────────────────────────────────────────────────

def _wrap(text: str, font: ImageFont.ImageFont, max_px: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_px:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _center_x(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw) -> int:
    return (CANVAS - draw.textbbox((0, 0), text, font=font)[2]) // 2


def _text_h(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _format_price(raw: str) -> str:
    """Normalise CSV price to $X,XXX format. Adds $ if missing."""
    p = str(raw or "").strip().lstrip("$").replace(",", "")
    try:
        val = float(p)
        if val <= 0:
            return "Check Price on Amazon"
        # Show cents only when not a round dollar amount
        return f"${val:,.2f}" if "." in p and not p.endswith(".00") else f"${int(val):,}"
    except ValueError:
        return raw if raw.startswith("$") else f"${raw}" if raw else "Check Price on Amazon"


# ── Star rating (drawn, no unicode dependency) ────────────────────────────────

def _draw_stars(draw: ImageDraw.ImageDraw, cx: int, y: int, rating: float,
                dot_r: int = 9, gap: int = 8) -> int:
    """
    Draw 5 star-dots centred at horizontal position cx.
    Filled orange = full star, half-filled = half star, outline = empty.
    Returns the y coordinate after the stars row.
    """
    total_w = 5 * (dot_r * 2) + 4 * gap
    x = cx - total_w // 2

    for i in range(5):
        left  = x + i * (dot_r * 2 + gap)
        right = left + dot_r * 2
        top   = y
        bot   = y + dot_r * 2

        filled = rating >= i + 1
        half   = (not filled) and rating >= i + 0.5

        if filled:
            draw.ellipse([left, top, right, bot], fill=ORANGE)
        elif half:
            # Filled circle then mask right half with dark
            draw.ellipse([left, top, right, bot], fill=ORANGE)
            mid = left + dot_r
            draw.rectangle([mid, top - 1, right + 1, bot + 1], fill=BG_DARK)
            draw.ellipse([left, top, right, bot], outline=ORANGE, width=2)
        else:
            draw.ellipse([left, top, right, bot], outline=(120, 120, 120), width=2)

    return y + dot_r * 2


# ── Bezier curves ─────────────────────────────────────────────────────────────

def _bezier(p0, p1, p2, p3, steps: int = 60) -> list[tuple[int, int]]:
    pts = []
    for i in range(steps + 1):
        t = i / steps; mt = 1 - t
        x = mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0]
        y = mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]
        pts.append((int(x), int(y)))
    return pts


# ── Compositing stages ────────────────────────────────────────────────────────

def _make_background() -> Image.Image:
    base = Image.new("RGBA", (CANVAS, CANVAS), (*BG_DARK, 255))
    glow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    cx, cy = CANVAS // 2, int(CANVAS * 0.22)
    gd.ellipse([cx - 500, cy - 230, cx + 500, cy + 230], fill=(*BG_LIFT, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=95))
    lift = Image.new("RGBA", (CANVAS, CANVAS), (*BG_LIFT, 255))
    return Image.composite(lift, base, glow)


def _add_orange_glow(canvas: Image.Image) -> Image.Image:
    glow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    cx, cy = CANVAS // 2, int(CANVAS * 0.68)
    gd.ellipse([cx - 320, cy - 110, cx + 320, cy + 110], fill=(*ORANGE, 42))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=65))
    return Image.alpha_composite(canvas, glow)


def _add_kinetic_curves(canvas: Image.Image) -> Image.Image:
    overlay = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    C = CANVAS
    curves = [
        ((0,        C * .82), (C * .12, C * .62), (C * .28, C * .78), (C * .14, C)),
        ((C,        C * .18), (C * .86, C * .04), (C * .70, C * .19), (C * .88, 0)),
        ((C * .62,  C),       (C * .76, C * .86), (C * .91, C * .91), (C,       C * .68)),
    ]
    for p0, p1, p2, p3 in curves:
        pts = _bezier(
            (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])),
            (int(p2[0]), int(p2[1])), (int(p3[0]), int(p3[1])),
        )
        for width, alpha in [(5, 50), (3, 75), (1, 110)]:
            draw.line(pts, fill=(*ORANGE, alpha), width=width)
    return Image.alpha_composite(canvas, overlay)


def _is_dark_background(img: Image.Image, threshold: int = 100) -> bool:
    """Sample four corners; if avg brightness < threshold the bg is dark."""
    w, h = img.size
    corners = [
        img.getpixel((8, 8)),
        img.getpixel((w - 8, 8)),
        img.getpixel((8, h - 8)),
        img.getpixel((w - 8, h - 8)),
    ]
    avg = sum(sum(c[:3]) / 3 for c in corners) / 4
    return avg < threshold


def _remove_white_bg(img: Image.Image, threshold: int = 228) -> Image.Image:
    """Replace near-white pixels with transparency."""
    rgba = img.convert("RGBA")
    data = rgba.getdata()
    rgba.putdata([
        (r, g, b, 0) if r > threshold and g > threshold and b > threshold else (r, g, b, a)
        for r, g, b, a in data
    ])
    return rgba.filter(ImageFilter.SMOOTH_MORE)


def _apply_ellipse_blend(img: Image.Image, feather: float = 0.12) -> Image.Image:
    """
    For dark-background images (fal.ai output): apply a soft elliptical alpha mask
    so the product fades into the canvas rather than leaving a hard rectangle.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    mask = Image.new("L", (w, h), 0)
    md   = ImageDraw.Draw(mask)
    px   = int(w * feather)
    py   = int(h * feather)
    md.ellipse([px, py, w - px, h - py], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(px, py) * 0.9))
    rgba.putalpha(mask)
    return rgba


def _add_product(canvas: Image.Image, product_img: Image.Image) -> Image.Image:
    """Composite product into lower portion of canvas."""
    dark_bg = _is_dark_background(product_img)
    prod    = _apply_ellipse_blend(product_img) if dark_bg else _remove_white_bg(product_img)

    max_w = int(CANVAS * 0.72)
    max_h = int(CANVAS * 0.60)
    prod.thumbnail((max_w, max_h), Image.LANCZOS)

    cx = (CANVAS - prod.width) // 2
    cy = int(CANVAS * 0.365)

    # Drop shadow
    shadow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    sd     = ImageDraw.Draw(shadow)
    sx     = cx + prod.width // 2
    sy     = cy + prod.height + 10
    sd.ellipse([sx - prod.width // 3, sy - 14, sx + prod.width // 3, sy + 14],
               fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
    canvas = Image.alpha_composite(canvas, shadow)

    canvas.paste(prod, (cx, cy), mask=prod.split()[3])
    return canvas


def _add_text(canvas: Image.Image, product: dict) -> Image.Image:
    draw = ImageDraw.Draw(canvas)

    name     = product.get("name", "")
    price    = product.get("price", "")
    rating   = float(product.get("rating", 4.5))
    reviews  = product.get("reviews", "")
    category = (product.get("category") or "").strip()

    words    = name.split()
    headline = " ".join(words[:6]) + ("..." if len(words) > 6 else "")

    f_headline = _load_font(70, bold=True)
    f_sub      = _load_font(28, bold=False)
    f_price    = _load_font(40, bold=True)
    f_pill     = _load_font(23, bold=True)
    tag_font   = _load_font(22, bold=True)

    margin = 58
    max_w  = CANVAS - margin * 2
    y      = 48

    # ── HOT DEAL pill ─────────────────────────────────────────────────────────
    tag_text = "HOT DEAL"
    tb  = draw.textbbox((0, 0), tag_text, font=tag_font)
    tw  = tb[2] - tb[0]
    th  = tb[3] - tb[1]
    tpx = (CANVAS - tw - 32) // 2
    draw.rounded_rectangle([tpx, y, tpx + tw + 32, y + th + 16],
                            radius=(th + 16) // 2, fill=(*ORANGE, 230))
    draw.text((tpx + 16, y + 8), tag_text, font=tag_font, fill=WHITE)
    y += th + 16 + 18

    # ── Headline (max 2 lines) ────────────────────────────────────────────────
    for line in _wrap(headline, f_headline, max_w, draw)[:2]:
        lx = _center_x(line, f_headline, draw)
        lh = _text_h(line, f_headline, draw)
        draw.text((lx + 2, y + 2), line, font=f_headline, fill=(0, 0, 0))
        draw.text((lx, y), line, font=f_headline, fill=WHITE)
        y += lh + 6
    y += 14

    # ── Star dots (DISABLED - remove orange rating dots) ──────────────────────
    # star_bottom = _draw_stars(draw, CANVAS // 2, y, rating, dot_r=9, gap=7)
    # y = star_bottom + 10

    # ── Review count + rating text ────────────────────────────────────────────
    try:
        rev_n   = int(re.sub(r"[^0-9]", "", str(reviews)) or "0")
        rev_str = f"{rev_n:,}" if rev_n else "many"
    except ValueError:
        rev_str = str(reviews) or "many"

    subline = f"{rating}/5  ·  {rev_str} verified reviews"
    sx      = _center_x(subline, f_sub, draw)
    draw.text((sx, y), subline, font=f_sub, fill=WHITE_DIM)
    y += _text_h(subline, f_sub, draw) + 14

    # ── Price ─────────────────────────────────────────────────────────────────
    price_text = _format_price(price)
    px         = _center_x(price_text, f_price, draw)
    draw.text((px, y), price_text, font=f_price, fill=ORANGE)

    # ── Bottom stat pills ─────────────────────────────────────────────────────
    pill_labels = ["hotproductsdot.com"]
    if category:
        pill_labels.append(category)

    pill_h   = 42
    gap      = 14
    pad      = 22
    total_pw = (
        sum(draw.textbbox((0, 0), t, font=f_pill)[2] + pad * 2 for t in pill_labels)
        + gap * (len(pill_labels) - 1)
    )
    px2 = (CANVAS - total_pw) // 2
    py2 = CANVAS - pill_h - 38

    for label in pill_labels:
        lw  = draw.textbbox((0, 0), label, font=f_pill)[2]
        pw2 = lw + pad * 2
        draw.rounded_rectangle(
            [px2, py2, px2 + pw2, py2 + pill_h],
            radius=pill_h // 2,
            fill=PILL_BG,
            outline=(*ORANGE, 90),
            width=1,
        )
        lh2 = draw.textbbox((0, 0), label, font=f_pill)[3]
        draw.text((px2 + pad, py2 + (pill_h - lh2) // 2), label, font=f_pill, fill=WHITE_DIM)
        px2 += pw2 + gap

    return canvas


# ── Public API ────────────────────────────────────────────────────────────────

def download_square_instagram_feed_jpeg(source_url: str, dest: Path, size: int = 1080) -> None:
    """
    Download an image URL and write a baseline size×size JPEG (cover crop).
    Instagram feed requires aspect ratio roughly between 4:5 and 1.91:1; a
    square (1:1) is valid. Raw product JPGs are often wider than tall.
    """
    resp = requests.get(source_url, timeout=30)
    resp.raise_for_status()
    im = Image.open(BytesIO(resp.content)).convert("RGB")
    w, h = im.size
    if w <= 0 or h <= 0:
        raise ValueError("Invalid image dimensions")

    scale = max(size / w, size / h)
    nw, nh = int(w * scale), int(h * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    left = (nw - size) // 2
    top = (nh - size) // 2
    im = im.crop((left, top, left + size, top + size))

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(
        str(dest),
        "JPEG",
        quality=93,
        optimize=True,
        progressive=False,
        subsampling=0,
    )


def compose_banner(
    product: dict,
    product_image_url_or_path: str,
    output_path: str | Path,
) -> str:
    src = str(product_image_url_or_path)
    if src.startswith("http"):
        resp = requests.get(src, timeout=30)
        resp.raise_for_status()
        prod_img = Image.open(BytesIO(resp.content)).convert("RGB")
    else:
        prod_img = Image.open(src).convert("RGB")

    canvas = _make_background()
    canvas = _add_orange_glow(canvas)
    canvas = _add_kinetic_curves(canvas)
    canvas = _add_product(canvas, prod_img)
    canvas = _add_text(canvas, product)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Baseline JPEG, 4:4:4 — Instagram Content Publishing rejects some progressive / odd subsampling.
    canvas.convert("RGB").save(
        str(out),
        "JPEG",
        quality=93,
        optimize=True,
        progressive=False,
        subsampling=0,
    )
    return str(out)


def _parse_cloudinary_url(url: str) -> tuple[str, str, str] | None:
    """Parse cloudinary://api_key:api_secret@cloud_name → (cloud_name, api_key, api_secret)."""
    m = re.match(r"^cloudinary://([^:]+):([^@]+)@(.+)$", url.strip())
    if not m:
        return None
    api_key, api_secret, cloud_name = m.group(1), m.group(2), m.group(3)
    return cloud_name, api_key, api_secret


def upload_to_cloudinary(local_path: str, cloudinary_url: str, *, public_id: str | None = None) -> str | None:
    """Signed upload to Cloudinary. Returns secure_url or None.

    Cloudinary is Meta-friendly (Instagram Graph API never rejects res.cloudinary.com).
    """
    import hashlib
    import time

    parsed = _parse_cloudinary_url(cloudinary_url)
    if not parsed:
        print("  [cloudinary upload failed: CLOUDINARY_URL malformed]")
        return None
    cloud_name, api_key, api_secret = parsed

    timestamp = int(time.time())
    pid = (public_id or Path(local_path).stem or "hotproducts-banner").strip()[:100]
    params_to_sign = f"public_id={pid}&timestamp={timestamp}"
    signature = hashlib.sha1((params_to_sign + api_secret).encode()).hexdigest()

    try:
        with open(local_path, "rb") as f:
            resp = requests.post(
                f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload",
                data={
                    "api_key": api_key,
                    "timestamp": timestamp,
                    "public_id": pid,
                    "signature": signature,
                },
                files={"file": f},
                timeout=60,
            )
        resp.raise_for_status()
        return resp.json().get("secure_url")
    except Exception as exc:
        print(f"  [cloudinary upload failed: {exc}]")
        return None


def upload_to_imgbb(local_path: str, api_key: str, *, name: str | None = None) -> str | None:
    import base64
    with open(local_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    # ImgBB "name" is the gallery title — local file is always banner.jpg, so pass a unique name.
    title = (name or Path(local_path).stem or "hotproducts-banner").strip()[:100] or "hotproducts-banner"
    try:
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={
                "key": api_key,
                "image": b64,
                "name": title,
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json().get("data") or {}
        # Prefer nested image.url (full-size JPEG) over top-level url when present.
        nested = (payload.get("image") or {}) if isinstance(payload.get("image"), dict) else {}
        return nested.get("url") or payload.get("url")
    except Exception as exc:
        print(f"  [imgbb upload failed: {exc}]")
        return None
