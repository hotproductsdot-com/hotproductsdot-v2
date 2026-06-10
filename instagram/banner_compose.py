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
import base64
import json
import os
import re
import time
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def _fetch_image_bytes(url: str, timeout: int = 30) -> bytes:
    """GET an image URL, retrying once on 403 for hotproductsdot.com.

    Hostinger's bot-protection occasionally returns 403 to the GitHub Actions
    runner (e.g. the 15:49 cron on 2026-04-27). The block is short-lived, so
    a single 45s wait + retry recovers without exponential backoff.
    """
    resp = requests.get(url, timeout=timeout)
    if resp.status_code == 403 and "hotproductsdot.com" in url:
        time.sleep(45)
        resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


class BannerQualityError(Exception):
    """Raised when an automated quality check rejects a generated banner.

    Treated as a permanent skip by post_daily.py — re-running won't help
    because the source catalog image is the root cause (extreme aspect
    ratio, lifestyle scene with floor/walls, fully-erased low-contrast
    body, etc). Surfaces a `.reason` so the post log row explains why.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _validate_source_image(img: Image.Image) -> tuple[bool, str]:
    """Pre-render sanity check on the catalog source image.

    The white-card pipeline frames the source on its original background, so
    lifestyle vs. catalog no longer matters — both compose cleanly. Extreme
    aspect ratios still don't, since a 3:1 strip becomes a thin band of
    pixels inside the square-ish card with most of the card empty.
    """
    w, h = img.size
    aspect = w / h
    if aspect > 3.0 or aspect < 0.33:
        return False, f"source aspect {aspect:.2f} composes to a strip"
    return True, ""


def _ai_vision_validate_banner(
    banner_path: str | Path, product_name: str
) -> tuple[bool, str]:
    """Final-stage AI gate that catches defects heuristics can't see.

    Heuristic validators handle pixel-level failures (lifestyle scenes,
    extreme aspect ratios, fully erased products, multi-component
    collages). They miss semantic failures:
      - Cluttered scene compositions (Autonomous standing desk + 8
        accessories all on one connected blob).
      - Catalog brand mismatches (a desk titled "Autonomous" showing
        an OffiGo monitor in the source image).
      - Wrong product entirely (Amazon's main image being for a
        different SKU than the title implies).
      - Cropped product (head missing, etc.) where the cutout coverage
        is fine but the result looks broken.

    Sends the composed banner JPG + product name to Claude Haiku 4.5
    with a strict-mode prompt: approve only if the banner shows a
    single, clean, recognizable instance of the named product.

    Returns (ok, reason). Reason is empty when approved.

    Defensive about API problems: a missing ANTHROPIC_API_KEY, network
    error, or unparseable response all return (True, "") so the gate
    fails open. Catching real defects matters more than blocking on
    API outages — the heuristic checks already ran by this point.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return True, ""

    try:
        import anthropic  # type: ignore
    except ImportError:
        return True, ""

    try:
        with open(banner_path, "rb") as f:
            jpg_b64 = base64.standard_b64encode(f.read()).decode("ascii")
    except OSError:
        return True, ""

    prompt = (
        f'You are an unforgiving QA reviewer for a brand Instagram account. '
        f'The banner below has the product title: "{product_name}".\n\n'
        f'BRAND DESIGN CONTEXT (these are INTENTIONAL — never flag them):\n'
        f'- The banner uses a dark gradient background by design.\n'
        f'- A soft warm orange ambient glow sits behind the product to lift '
        f'  it off the canvas. This is the brand\'s signature light treatment, '
        f'  NOT a cutout halo or artifact.\n'
        f'- Thin orange bezier curves loop in the corners as decorative motion '
        f'  graphics. NOT artifacts.\n'
        f'- White display headline at the top, orange price, pill-shaped tags '
        f'  at the bottom — all part of the template.\n\n'
        f'Walk through these checks IN ORDER and write your findings to the '
        f'"checks" object. After each check, decide approve/reject. Only set '
        f'approved=true if EVERY check passes.\n\n'
        f'CHECK 1 — Single product (no duplicates):\n'
        f'  Count distinct instances of the named product. The same product '
        f'  shown more than once (vacuum + 4 detail shots of the head) → '
        f'  "fail: N copies". A product naturally containing multiple parts '
        f'  (Fire TV stick + remote, lens + bag) is fine.\n\n'
        f'CHECK 2 — Scene clutter:\n'
        f'  List every NON-product object visible. Banner-template elements '
        f'  (orange glow, bezier curves, headline, price, pills) are NOT '
        f'  clutter. Accessories that ship in-box with the named product '
        f'  (remote, charger, cables, power adapter, stand, wall mount, '
        f'  mounting hardware, manual, replacement parts, sensors, base '
        f'  station, hub, or any bundled add-on that appears in the '
        f'  official Amazon product listing photo) are PART of the '
        f'  product and NOT clutter — even when visually separated from '
        f'  the main unit. A neutral lifestyle surface (desk, table, '
        f'  countertop, hand holding the product) is also NOT clutter. '
        f'  Set check2 to "fail: <list>" ONLY for unrelated competing '
        f'  objects that have no relationship to the named product '
        f'  (e.g. an unrelated laptop next to a smart display, a plant '
        f'  beside an air fryer, a coffee cup next to headphones).\n\n'
        f'CHECK 3 — Brand identity:\n'
        f'  Read every visible logo/text on objects. If any logo contradicts '
        f'  the title brand (e.g. "OffiGo" on an "Autonomous" desk), set '
        f'  check3 to "fail: <wrong brand>". A title brand mismatch is a hard '
        f'  reject. The template typography (headline, price, pills) is not '
        f'  a brand check.\n\n'
        f'CHECK 4 — Real cutout artifacts (NOT the brand glow):\n'
        f'  Look for: jagged edges along the product silhouette, leftover '
        f'  rectangular background patches, ghost fragments floating away '
        f'  from the product, or parts of the product body erased / made '
        f'  transparent. The intentional warm orange glow described above '
        f'  is NOT an artifact; do not flag it. Only set check4 to "fail" '
        f'  for genuine pixel-level errors visible against the dark canvas.\n\n'
        f'Reply with ONLY a single JSON object, no markdown fences, no preamble:\n'
        f'{{"checks": {{"check1": "...", "check2": "...", "check3": "...", "check4": "..."}}, '
        f'"approved": true|false, "reason": "<one short sentence; required when approved=false>"}}'
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": jpg_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        response_text = msg.content[0].text.strip()
    except Exception:
        return True, ""

    try:
        # Tolerate the model wrapping JSON in ```json fences.
        cleaned = re.sub(r"^```(?:json)?|```$", "", response_text, flags=re.MULTILINE).strip()
        data = json.loads(cleaned)
        approved = bool(data.get("approved"))
        reason = str(data.get("reason") or "").strip()
        if approved:
            return True, ""
        return False, reason or "AI vision rejected banner (no reason given)"
    except (json.JSONDecodeError, AttributeError, KeyError, TypeError):
        return True, ""


def _validate_cutout(prod: Image.Image) -> tuple[bool, str]:
    """Post-cutout sanity check on the rembg alpha output.

    Catches:
      - Product fully erased (silver Mac Mini under isnet — coverage near 0).
      - Background fully retained (lifestyle scene rembg couldn't isolate —
        coverage near 100% means nothing was removed).
    """
    a = np.asarray(prod.split()[3], dtype=np.float32)
    total = a.size
    if total == 0:
        return False, "empty cutout"
    opaque = float((a > 200).sum() / total)
    if opaque < 0.05:
        return False, f"product mostly erased ({opaque:.1%} opaque after cutout)"
    if opaque > 0.90:
        return False, f"background retained ({opaque:.1%} opaque — cutout failed to isolate)"
    return True, ""


def _alpha_centroid(prod: Image.Image) -> tuple[float, float]:
    """Alpha-weighted centroid in product-local pixel coords.

    For asymmetric products (e.g. Fire TV Stick + remote, or a lens with
    a bag accessory), the alpha bounding-box center sits in empty space
    between the components. Centroid weighting puts the placement anchor
    on actual visual mass, which keeps the composition balanced.
    """
    a = np.asarray(prod.split()[3], dtype=np.float32)
    total = a.sum()
    if total <= 0:
        return prod.width / 2, prod.height / 2
    ys, xs = np.indices(a.shape)
    cx = float((xs * a).sum() / total)
    cy = float((ys * a).sum() / total)
    return cx, cy

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


def _remove_white_bg(
    img: Image.Image,
    threshold: int = 228,
    rembg_model: str | None = None,
) -> Image.Image:
    """Cut a product out of a white/light catalog backdrop.

    Two model options:
      - default (None) → rembg `u2net` + hybrid recovery: keeps non-white
        pixels rembg drops. Safe for low-contrast products (silver iPads,
        white earbuds, tan coolers) where isnet erases the body.
      - "isnet-general-use" → cleaner cut on high-contrast products with
        small accessories (Canon lens with hood + cap, Instant Pot with
        accessories around it). Used when caller passes `rembg_model`
        in the product dict.

    Without rembg, falls back to per-pixel threshold.
    """
    rgba_src = img.convert("RGBA")

    try:
        from rembg import remove, new_session  # type: ignore
        if rembg_model:
            session = new_session(rembg_model)
            rembg_out = remove(rgba_src, session=session)
            return rembg_out.filter(ImageFilter.SMOOTH)
        rembg_out = remove(rgba_src)
    except ImportError:
        data = rgba_src.getdata()
        rgba_src.putdata([
            (r, g, b, 0) if r > threshold and g > threshold and b > threshold else (r, g, b, a)
            for r, g, b, a in data
        ])
        return rgba_src.filter(ImageFilter.SMOOTH_MORE)

    src_pixels = list(rgba_src.getdata())
    rembg_pixels = list(rembg_out.getdata())
    merged: list[tuple[int, int, int, int]] = []
    for (sr, sg, sb, _sa), (rr, rg, rb, ra) in zip(src_pixels, rembg_pixels):
        if ra > 0:
            merged.append((rr, rg, rb, ra))
        elif sr > threshold and sg > threshold and sb > threshold:
            merged.append((sr, sg, sb, 0))
        else:
            merged.append((sr, sg, sb, 255))

    out = Image.new("RGBA", rgba_src.size)
    out.putdata(merged)
    return out.filter(ImageFilter.SMOOTH)


def _remove_dark_bg(img: Image.Image) -> Image.Image:
    """Cut a product out of a dark studio backdrop.

    Uses rembg (u2net) when available — the only reliable option for dark-on-dark cases
    where color-distance fails because the product (e.g. a black camera body) shares its
    luminance with the backdrop.

    Falls back to a soft radial alpha that dims the image's perimeter into the canvas.
    The fallback is visibly worse but prevents a crash if rembg isn't installed.
    """
    try:
        from rembg import remove  # type: ignore
        cut = remove(img.convert("RGBA"))
        return cut.filter(ImageFilter.SMOOTH)
    except ImportError:
        pass

    rgba = img.convert("RGBA")
    w, h = rgba.size
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    feather = 0.18
    px = int(w * feather)
    py = int(h * feather)
    md.ellipse([px, py, w - px, h - py], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(px, py) * 1.2))
    rgba.putalpha(mask)
    return rgba


# Per-product rembg model overrides. Keyed by slug (matches what
# `post_daily.py` and `preview_repost_banners.py` already pass through).
# Default `None` → u2net + hybrid recovery. Override only when isnet wins.
REMBG_MODEL_BY_SLUG: dict[str, str] = {
    # High-contrast products with small accessories that u2net's hybrid
    # recovery brings back as ghosts. isnet's cleaner saliency keeps the
    # accessories sharp without leaving the product body bitten.
    "canon-rf-70-200mm-f-2-8":                          "isnet-general-use",
    "instant-pot-duo-7-in-1-electric-pressure-cooker":  "isnet-general-use",
    # Multi-tool/combo-kit products — multiple metallic protrusions that
    # u2net treats as separate objects, leaving floating "shrapnel" fragments
    # in the cutout. Leatherman shipped that artifact in run #55 (deleted).
    # Milwaukee combo kits include drill + impact driver + batteries + charger
    # in one image, same failure mode. isnet handles these much better.
    "leatherman-wave-plus-multi-tool":                  "isnet-general-use",
    "milwaukee-m18-fuel-drill-combo-kit":               "isnet-general-use",
    # 2026-04-29 batch — u2net + hybrid recovery shipped three broken cutouts:
    #   Husqvarna mower: catalog drop-shadow merged back in (bright white halo
    #     under the product on the dark canvas).
    #   Sony A7R V: black hand-grip on the left half partially erased — half
    #     of the camera body became transparent.
    #   HOROW Smart Toilet: lifestyle source (wood floor + wall + door frame),
    #     hybrid recovery preserves the entire scene around the product.
    # isnet's saliency cuts cleanly on all three.
    #
    # NOTE: Mac Mini M4 (2024) is also broken with u2net (frayed silver edges)
    # but isnet is WORSE — it erases the silver body entirely and only two
    # USB-C ports survive. The flat front-face source image is the real
    # problem (silver-on-white, no perspective). Needs a 3/4 hero shot from
    # Amazon's image gallery before it can be fixed at the cutout layer.
    "husqvarna-automower-450x-robotic-lawn-mower":      "isnet-general-use",
    "sony-a7r-v-camera":                                "isnet-general-use",
    "horow-black-smart-toilet-with-pump-and-bidet-built-in": "isnet-general-use",
}

# Manual image URL overrides for products where og:image is not the best angle.
# Use when Amazon's default image (first in listing) is inferior to an
# alternative from the product's image gallery. Keyed by slug (matches REMBG_MODEL_BY_SLUG).
PRODUCT_IMAGE_OVERRIDE_BY_SLUG: dict[str, str] = {
    "apple-2026-macbook-neo-13-inch-laptop-with-a18": "https://m.media-amazon.com/images/I/619PNoEsnSL._AC_SL1500_.jpg",
    "apple-airpods-max": "/mnt/e/GITHUB/hotproductsdot-v2/site/public/products/apple-airpods-max.jpg",
    "beats-studio3-wireless": "/mnt/e/GITHUB/hotproductsdot-v2/site/public/products/beats-studio3-wireless.jpg",
}


def _cutout_product(
    product_img: Image.Image,
    rembg_model: str | None = None,
) -> Image.Image:
    """Run the appropriate background removal for the source backdrop.

    Split out from _add_product so compose_banner can run quality checks
    against the alpha mask before the placement step.
    """
    dark_bg = _is_dark_background(product_img)
    if dark_bg:
        # For dark products, try isnet-general-use for better saliency
        return _remove_dark_bg(product_img)
    else:
        # For light/white backgrounds, use rembg default (u2net + hybrid recovery)
        # unless specific model is set in REMBG_MODEL_BY_SLUG
        model_override = rembg_model or None
        return _remove_white_bg(product_img, rembg_model=model_override)


def _keep_largest_component(prod: Image.Image, min_components: int = 4) -> Image.Image:
    """When the cutout has many disconnected regions, keep only the largest.

    Defends against Amazon catalog images that are multi-product collages —
    e.g. Shark Stratos vacuum's catalog jpg shows the main vacuum plus 4
    repeated detail shots and 2 accessory thumbnails. rembg correctly cuts
    the white background but leaves all 7 foreground regions, producing a
    banner with ghosted duplicates around the main product.

    Heuristic: if the alpha mask has ≥ `min_components` distinct connected
    regions, the source is almost certainly a collage. Keep only the largest
    region (the main hero shot) and zero the rest. For 1–3 components we
    leave the cutout alone — those are legitimate multi-part products
    (Fire TV Stick + remote, lens + bag) where preserving all parts is
    correct.

    Falls back to a no-op if scipy isn't available — better to let the
    cutout-coverage validator catch the failure than crash the pipeline.
    """
    try:
        from scipy import ndimage
    except ImportError:
        return prod

    a = np.asarray(prod.split()[3], dtype=np.uint8)
    binary = a > 200
    labels, num_components = ndimage.label(binary)
    if num_components < min_components:
        return prod

    # Bin label sizes; index 0 is background, skip it.
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    largest_label = int(sizes.argmax())

    keep_mask = labels == largest_label
    new_alpha = np.where(keep_mask, a, 0).astype(np.uint8)

    rgba = np.array(prod.convert("RGBA"))
    rgba[..., 3] = new_alpha
    return Image.fromarray(rgba, "RGBA")


def _add_product(
    canvas: Image.Image,
    prod: Image.Image,
) -> Image.Image:
    """Composite an already-cutout product into the lower portion of canvas.

    TODO(banner-centering, 2026-04-25): improve composition for asymmetric
    products (e.g. Canon RF lens with bag + accessories). Plan:
      1. Replace bbox-center with alpha-weighted centroid: compute
         np.array(prod)[:,:,3] mean coordinate and translate so centroid
         lands at canvas (50%, 60%). Avoids sparse outliers (stray lens
         cap) shifting the whole composition.
      2. Adaptive cy: drop the fixed 0.365 placement and target a
         consistent visual mid-point regardless of product height.
      3. Per-slug nudge override (CENTERING_NUDGE_BY_SLUG dict, mirrors
         REMBG_MODEL_BY_SLUG above).
      4. Add `--center-grid` flag to preview_repost_banners.py that draws
         faint crosshairs so misalignment is immediately visible.
    """
    # Crop to the alpha bounding box so the visible product (not the original
    # source dimensions, which may have wide transparent margins after cutout)
    # is what gets centered on the canvas.
    bbox = prod.getbbox()
    if bbox:
        prod = prod.crop(bbox)

    max_w = int(CANVAS * 0.72)
    max_h = int(CANVAS * 0.60)
    prod.thumbnail((max_w, max_h), Image.LANCZOS)

    # Alpha-weighted centroid for horizontal placement; clamped to canvas.
    # Asymmetric products (Fire Stick + remote, lens + bag) used to drift
    # because bbox-center didn't reflect actual visual mass.
    local_cx, _ = _alpha_centroid(prod)
    cx = int(round(CANVAS // 2 - local_cx))
    cx = max(0, min(cx, CANVAS - prod.width))
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


def _pick_badge(product: dict) -> str:
    """Derive a social-proof badge from product fields.

    Ordered by strength of claim — stronger signal wins, so 'VIRAL' beats
    'EDITOR'S PICK' when both apply.
    """
    try:
        review_count = int(str(product.get("review_count") or product.get("reviews") or "0").replace(",", ""))
    except (ValueError, TypeError):
        review_count = 0
    try:
        rating = float(product.get("rating") or 0)
    except (ValueError, TypeError):
        rating = 0.0
    try:
        bsr = int(product.get("bsr") or 0)
    except (ValueError, TypeError):
        bsr = 0
    try:
        potential = int(product.get("potential") or 0)
    except (ValueError, TypeError):
        potential = 0

    if review_count >= 10000:
        return "VIRAL"
    if 0 < bsr <= 10:
        return "AMAZON #1"
    if rating >= 4.8 and review_count >= 1000:
        return "EDITOR'S PICK"
    if potential >= 9:
        return "TOP PICK"
    return "HOT DEAL"


def _add_text(canvas: Image.Image, product: dict, cta_version: str = "none") -> Image.Image:
    draw = ImageDraw.Draw(canvas)

    name     = product.get("name", "")
    price    = product.get("price", "")
    rating   = float(product.get("rating", 4.5))
    reviews  = product.get("reviews", "")
    category = (product.get("category") or "").strip()

    # ── Headline cleanup ─────────────────────────────────────────────────
    # CSV product names often include bracketed metadata ("[GPS + Cellular 49mm]")
    # and parenthetical suffixes ("(2nd Gen)", "(2023)"). The original
    # `name.split()[:6]` truncation cut mid-bracket and produced things like
    # "Apple Watch Ultra 3 [GPS +" (visibly broken; shipped in run #55, deleted).
    # Three-stage cleanup before truncation:
    #   1. Strip [...] and (...) content — adds noise, no headline value.
    #   2. Take first 8 words (was 6) — _wrap() below still folds to 2 lines
    #      on the 1080-wide canvas; 8 gives products like Owala / Apple Watch
    #      enough room to read coherently.
    #   3. Strip stray trailing punctuation/stop-words so the headline doesn't
    #      end mid-clause ("Owala ... Water Bottle with" → "...Water Bottle").
    clean_name = re.sub(r"\s*[\[\(].*?[\]\)]\s*", " ", name)
    clean_name = re.sub(r"\s+", " ", clean_name).strip()
    words      = clean_name.split()
    headline   = " ".join(words[:8])
    headline   = re.sub(r"[,;:\-+&]+\s*$", "", headline)
    headline   = re.sub(
        r"\s+(with|and|for|in|on|the|a|an|by|of)\s*$",
        "",
        headline,
        flags=re.IGNORECASE,
    ).strip()

    # Headline reduced from 70 → 56 to give the product image more breathing room.
    f_headline = _load_font(56, bold=True)
    f_sub      = _load_font(28, bold=False)
    f_price    = _load_font(40, bold=True)
    f_pill     = _load_font(23, bold=True)
    tag_font   = _load_font(22, bold=True)

    margin = 58
    max_w  = CANVAS - margin * 2
    y      = 48

    # ── Social-proof badge pill (VIRAL / AMAZON #1 / EDITOR'S PICK / TOP PICK / HOT DEAL) ──
    tag_text = _pick_badge(product)
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
    y += _text_h(price_text, f_price, draw) + 24

    # ── CTA Button (A/B versions for click-rate testing) ──────────────────────
    if cta_version in ("a", "b"):
        f_cta = _load_font(32, bold=True)
        cta_text = "CHECK PRICE" if cta_version == "b" else "CHECK PRICE ON AMAZON →"

        cta_bbox = draw.textbbox((0, 0), cta_text, font=f_cta)
        cta_w = cta_bbox[2] - cta_bbox[0]
        cta_h = cta_bbox[3] - cta_bbox[1]

        btn_w = cta_w + 32
        btn_h = cta_h + 18
        btn_x = (CANVAS - btn_w) // 2
        btn_y = y

        draw.rounded_rectangle(
            [btn_x, btn_y, btn_x + btn_w, btn_y + btn_h],
            radius=12,
            fill=(*ORANGE, 255),
            outline=ORANGE,
            width=2,
        )

        # Center text within button - account for textbbox offset
        button_center_x = btn_x + btn_w // 2
        button_center_y = btn_y + btn_h // 2
        # textbbox returns (left, top, right, bottom), left/top may not be 0
        text_offset_x = cta_bbox[0]
        text_offset_y = cta_bbox[1]
        cta_tx = button_center_x - cta_w // 2 - text_offset_x
        cta_ty = button_center_y - cta_h // 2 - text_offset_y
        draw.text((cta_tx, cta_ty), cta_text, font=f_cta, fill=(255, 255, 255))

        y += btn_h + 24

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
    im = Image.open(BytesIO(_fetch_image_bytes(source_url))).convert("RGB")
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


def _extract_inner_box(img: Image.Image) -> Image.Image | None:
    """Extract the dark inner box area from images with white frames.

    For images like: white border → dark background with product,
    this crops to just the inner dark region.
    """
    arr = np.array(img)
    h, w = arr.shape[:2]

    # Find white frame boundaries (pixels > 240 brightness)
    gray = np.mean(arr, axis=2)
    white_mask = gray > 240

    # Find where white pixels start/end horizontally and vertically
    white_rows = np.where(white_mask.any(axis=1))[0]
    white_cols = np.where(white_mask.any(axis=0))[0]

    if len(white_rows) == 0 or len(white_cols) == 0:
        return None

    # Crop to inner region (skip white border)
    y_min, y_max = white_rows[0], white_rows[-1]
    x_min, x_max = white_cols[0], white_cols[-1]

    # Only use if there's a meaningful inner region
    inner_h = y_max - y_min
    inner_w = x_max - x_min
    if inner_h < 100 or inner_w < 100:
        return None

    # Add small margin inside the white border
    margin = 20
    crop_box = (
        max(0, x_min + margin),
        max(0, y_min + margin),
        min(w, x_max - margin),
        min(h, y_max - margin),
    )

    return img.crop(crop_box)


def _add_product_direct(canvas: Image.Image, src_img: Image.Image) -> Image.Image:
    """Place product image directly on canvas with background removed, no box/border."""
    # Try to extract inner box first (for images with white frames)
    inner = _extract_inner_box(src_img)
    img_to_cut = inner if inner else src_img

    # Remove white/background from product image using rembg
    prod = _cutout_product(img_to_cut)

    # Validate cutout quality
    ok, reason = _validate_cutout(prod)
    if not ok:
        raise BannerQualityError(f"product cutout failed: {reason}")

    # Keep only largest component (removes duplicate/collage images)
    prod = _keep_largest_component(prod)

    # Crop to alpha bounding box for clean placement
    bbox = prod.getbbox()
    if bbox:
        prod = prod.crop(bbox)

    max_w = int(CANVAS * 0.75)
    max_h = int(CANVAS * 0.70)
    prod.thumbnail((max_w, max_h), Image.LANCZOS)

    # Subtle drop shadow
    shadow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    img_x = (CANVAS - prod.width) // 2
    img_y = int(CANVAS * 0.38)

    shadow_x = img_x + prod.width // 2
    shadow_y = img_y + prod.height + 25
    sd.ellipse(
        [shadow_x - prod.width // 3 - 10, shadow_y - 16,
         shadow_x + prod.width // 3 + 10, shadow_y + 16],
        fill=(0, 0, 0, 120)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
    canvas = Image.alpha_composite(canvas, shadow)

    # Place cutout product with transparency directly on canvas
    canvas.paste(prod, (img_x, img_y), mask=prod.split()[3])

    return canvas


def _add_white_card(canvas: Image.Image, src_img: Image.Image) -> Image.Image:
    """Frame the source image as a rounded white card on the dark canvas.

    Replaces the rembg cutout pipeline. The catalog image — multi-product
    collage, scene shot, or clean isolate — sits on its original white
    background, framed by a card with a soft drop shadow and a thin orange
    brand-accent border that ties it to the banner's accent palette.
    """
    card_w = 760
    card_h = 600
    padding = 28
    border_w = 3
    card_x = (CANVAS - card_w) // 2
    card_y = int(CANVAS * 0.33)

    src_fit = src_img.copy()
    src_fit.thumbnail((card_w - padding * 2, card_h - padding * 2), Image.LANCZOS)
    if src_fit.mode != "RGB":
        src_fit = src_fit.convert("RGB")

    shadow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [card_x - 4, card_y + 12, card_x + card_w + 4, card_y + card_h + 22],
        radius=28,
        fill=(0, 0, 0, 140),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
    canvas = Image.alpha_composite(canvas, shadow)

    card_layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_layer)
    cd.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=24,
        fill=(255, 255, 255, 255),
        outline=(*ORANGE, 255),
        width=border_w,
    )
    canvas = Image.alpha_composite(canvas, card_layer)

    img_x = card_x + (card_w - src_fit.width) // 2
    img_y = card_y + (card_h - src_fit.height) // 2
    canvas.paste(src_fit, (img_x, img_y))

    return canvas


def compose_banner(
    product: dict,
    product_image_url_or_path: str,
    output_path: str | Path,
    cta_version: str = "none",
    use_card: bool = True,
) -> str:
    # Check for manual image URL override
    product_slug = re.sub(r"[^a-z0-9]+", "-", str(product.get("name", "")).lower()).strip("-")
    if product_slug in PRODUCT_IMAGE_OVERRIDE_BY_SLUG:
        src = PRODUCT_IMAGE_OVERRIDE_BY_SLUG[product_slug]
    else:
        src = str(product_image_url_or_path)
    if src.startswith("http"):
        prod_img = Image.open(BytesIO(_fetch_image_bytes(src))).convert("RGB")
    else:
        prod_img = Image.open(src).convert("RGB")

    # Source-image tripwire: extreme aspect ratios and lifestyle scenes
    # still look wrong even framed inside a white card. The cutout-stage
    # validators are gone (no cutout to check); this is the only heuristic
    # gate before the AI vision pass.
    src_ok, src_reason = _validate_source_image(prod_img)
    if not src_ok:
        raise BannerQualityError(f"source image: {src_reason}")

    canvas = _make_background()
    canvas = _add_orange_glow(canvas)
    canvas = _add_kinetic_curves(canvas)
    if use_card:
        canvas = _add_white_card(canvas, prod_img)
    else:
        # Direct product placement - no fallback, must work or fail
        canvas = _add_product_direct(canvas, prod_img)
    canvas = _add_text(canvas, product, cta_version)

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

    # Final-stage AI vision gate — catches semantic defects the heuristic
    # validators miss (scene clutter, brand mismatches, miscropped products,
    # subtle cutout artifacts that pass the alpha-coverage check).
    #
    # Mode is controlled by BANNER_AI_GATE env var:
    #   "off"     → skip the API call entirely (free, no protection)
    #   "shadow"  → call the API and PRINT the verdict, but never raise.
    #               Use to iterate on the prompt and validate model accuracy
    #               before you trust it to block posts. THIS IS THE DEFAULT.
    #   "enforce" → call the API and raise BannerQualityError on rejection.
    #               Switch to this once shadow-mode logs prove the model
    #               is reliably distinguishing good from bad banners.
    #
    # Always fails open on missing API key / network / parse errors so an
    # Anthropic outage can never halt the pipeline.
    mode = (os.environ.get("BANNER_AI_GATE") or "shadow").lower().strip()
    name = product.get("name", "")
    if mode != "off" and name:
        ai_ok, ai_reason = _ai_vision_validate_banner(out, name)
        if mode == "enforce":
            if not ai_ok:
                raise BannerQualityError(f"ai vision: {ai_reason}")
        else:
            verdict = "APPROVED" if ai_ok else f"REJECTED ({ai_reason})"
            print(f"   [ai-gate shadow] {verdict}")

    return str(out)


def _parse_cloudinary_url(url: str) -> tuple[str, str, str] | None:
    """Parse cloudinary://api_key:api_secret@cloud_name → (cloud_name, api_key, api_secret).

    Strips optional surrounding quotes/whitespace which secret managers sometimes add.
    """
    cleaned = url.strip().strip('"').strip("'")
    # Cloudinary dashboard often shows the full export line (CLOUDINARY_URL=cloudinary://...).
    # Strip that prefix if a user pasted the whole thing into the secret value.
    if cleaned.upper().startswith("CLOUDINARY_URL="):
        cleaned = cleaned.split("=", 1)[1].strip().strip('"').strip("'")
    m = re.match(r"^cloudinary://([^:]+):([^@]+)@([^/?#\s]+)", cleaned)
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

    if not cloudinary_url:
        print("  [cloudinary upload failed: CLOUDINARY_URL is empty]")
        return None
    parsed = _parse_cloudinary_url(cloudinary_url)
    if not parsed:
        prefix = cloudinary_url.strip()[:20] if cloudinary_url else "<empty>"
        print(f"  [cloudinary upload failed: CLOUDINARY_URL malformed (got prefix '{prefix}…', expected 'cloudinary://KEY:SECRET@CLOUD')]")
        return None
    cloud_name, api_key, api_secret = parsed

    timestamp = int(time.time())
    pid = (public_id or Path(local_path).stem or "hotproducts-banner").strip()[:100]
    # Sign overwrite + invalidate so re-uploading the same public_id always
    # bumps the version and busts the CDN cache. Without these, Cloudinary
    # hash-dedupes silently — a re-uploaded banner that happens to be
    # bit-identical to a prior asset (or any retry path Cloudinary thinks is
    # equivalent) returns the prior URL, so Instagram fetches the OLD banner.
    # 2026-04-29 16:00 UTC's broken Mac Mini banner (v1777478330) kept
    # resurfacing on later workflow runs because of this.
    # Signed params must be sorted alphabetically for the SHA1 to match.
    params_to_sign = (
        f"invalidate=true&overwrite=true&public_id={pid}&timestamp={timestamp}"
    )
    signature = hashlib.sha1((params_to_sign + api_secret).encode()).hexdigest()

    try:
        with open(local_path, "rb") as f:
            resp = requests.post(
                f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload",
                data={
                    "api_key": api_key,
                    "timestamp": timestamp,
                    "public_id": pid,
                    "overwrite": "true",
                    "invalidate": "true",
                    "signature": signature,
                },
                files={"file": f},
                timeout=60,
            )
        if resp.status_code >= 400:
            print(f"  [cloudinary upload failed: HTTP {resp.status_code} body={resp.text[:300]}]")
            return None
        payload = resp.json()
        secure_url = payload.get("secure_url")
        if not secure_url:
            print(f"  [cloudinary upload returned no secure_url; payload keys={list(payload.keys())}]")
        return secure_url
    except Exception as exc:
        print(f"  [cloudinary upload failed ({type(exc).__name__}): {exc}]")
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
