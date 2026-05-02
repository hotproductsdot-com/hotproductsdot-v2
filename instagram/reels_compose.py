"""
reels_compose.py — convert a 1080x1080 banner into a 1080x1920 vertical Reel.

Why this exists:
  - IG Reels reach is ~3x feed posts on cold accounts. We already generate
    1080x1080 banners every day via banner_compose. This module re-pots them
    into 9:16 video with subtle ken-burns motion + a hook overlay so they
    qualify as Reels and get the algorithmic boost.
  - No new branding work needed — the banner is the source of truth and
    we frame it inside the dark/orange canvas the brand already uses.

Pipeline:
  1. Composite the source 1080x1080 banner onto a 1080x1920 dark canvas
     (banner centered, vertical safe zones for caption + CTA).
  2. Render a hook caption above and a "🛒 link in bio" badge below.
  3. Use ffmpeg to apply ken-burns zoom + crossfade and encode H.264 mp4.
     Format: yuv420p, 30fps, 5.5s, IG-Reels-compliant.

Usage:
  python -m instagram.reels_compose \\
    --banner site/public/products/vitamix-5200-professional-blender.jpg \\
    --hook "The blender that quietly took over my counter" \\
    --out  /tmp/vitamix-reel.mp4

Output: H.264 mp4, ~1-2 MB, ready for IG Reels API or manual upload.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from instagram import banner_compose as bc

REEL_W = 1080
REEL_H = 1920
DURATION_SECONDS = 5.5
FPS = 30


def assert_ffmpeg_present() -> None:
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg not on PATH. Install: sudo apt install ffmpeg")


def make_reel_canvas(banner_path: Path, hook: str) -> Image.Image:
    """Compose the still frame that ffmpeg will animate."""
    canvas = Image.new("RGBA", (REEL_W, REEL_H), (*bc.BG_DARK, 255))

    glow = Image.new("RGBA", (REEL_W, REEL_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = REEL_W // 2, int(REEL_H * 0.50)
    gd.ellipse([cx - 540, cy - 360, cx + 540, cy + 360], fill=(*bc.BG_LIFT, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=120))
    canvas = Image.alpha_composite(canvas, glow)

    orange = Image.new("RGBA", (REEL_W, REEL_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orange)
    od.ellipse([cx - 380, cy + 120, cx + 380, cy + 460], fill=(*bc.ORANGE, 50))
    orange = orange.filter(ImageFilter.GaussianBlur(radius=90))
    canvas = Image.alpha_composite(canvas, orange)

    banner = Image.open(banner_path).convert("RGBA")
    if banner.size != (1080, 1080):
        banner = banner.resize((1080, 1080), Image.LANCZOS)
    banner_y = int((REEL_H - 1080) * 0.42)
    canvas.alpha_composite(banner, (0, banner_y))

    canvas = _draw_hook(canvas, hook)
    canvas = _draw_cta_badge(canvas)
    return canvas.convert("RGB")


def _draw_hook(canvas: Image.Image, hook: str) -> Image.Image:
    if not hook:
        return canvas
    draw = ImageDraw.Draw(canvas)
    font = bc._load_font(54, bold=True)  # noqa: SLF001
    max_px = REEL_W - 120
    lines = bc._wrap(hook, font, max_px, draw)[:3]  # noqa: SLF001

    pad_x, pad_y = 36, 22
    line_h = bc._text_h("Mg", font, draw)  # noqa: SLF001
    block_h = line_h * len(lines) + pad_y * 2 + (len(lines) - 1) * 8

    block_w = max(int(draw.textlength(ln, font=font)) for ln in lines) + pad_x * 2
    bx = (REEL_W - block_w) // 2
    by = int(REEL_H * 0.06)

    pill = Image.new("RGBA", (block_w, block_h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill)
    pd.rounded_rectangle([0, 0, block_w, block_h], radius=36, fill=(0, 0, 0, 200))
    canvas.paste(pill, (bx, by), pill)

    y = by + pad_y
    for line in lines:
        x = (REEL_W - int(draw.textlength(line, font=font))) // 2
        draw.text((x, y), line, font=font, fill=(*bc.WHITE, 255))
        y += line_h + 8
    return canvas


def _draw_cta_badge(canvas: Image.Image) -> Image.Image:
    draw = ImageDraw.Draw(canvas)
    font = bc._load_font(40, bold=True)  # noqa: SLF001
    text = "🛒 link in bio for the deal"
    tw = int(draw.textlength(text, font=font))
    pad_x, pad_y = 38, 22
    bw = tw + pad_x * 2
    bh = 80
    bx = (REEL_W - bw) // 2
    by = REEL_H - 220
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=40, fill=(*bc.ORANGE, 240))
    tx = bx + (bw - tw) // 2
    ty = by + (bh - 44) // 2
    draw.text((tx, ty), text, font=font, fill=(*bc.WHITE, 255))
    return canvas


def render_video(canvas_path: Path, out_path: Path, duration: float = DURATION_SECONDS) -> None:
    """Apply ken-burns zoom and encode to H.264 mp4 via ffmpeg.

    The zoompan filter scales the still up by 1.10x over the clip, recentered
    so the product stays in frame. This avoids the static-slideshow look that
    IG's algorithm de-prioritizes.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total_frames = int(duration * FPS)
    zoom_step = 0.0006

    vf = (
        f"scale=2160:3840,"
        f"zoompan=z='min(zoom+{zoom_step},1.10)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={total_frames}:s={REEL_W}x{REEL_H}:fps={FPS},"
        f"format=yuv420p"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(canvas_path),
        "-vf", vf,
        "-t", f"{duration}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "20",
        "-movflags", "+faststart",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"ffmpeg failed:\n{result.stderr[-2000:]}")


def compose_reel(banner_path: Path, hook: str, out_path: Path) -> Path:
    assert_ffmpeg_present()
    canvas = make_reel_canvas(banner_path, hook)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        canvas.save(tmp_path, "PNG", optimize=True)
        render_video(tmp_path, out_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return out_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compose 1080x1920 IG Reel from a banner.")
    p.add_argument("--banner", required=True, type=Path, help="source 1080x1080 banner JPG/PNG")
    p.add_argument("--hook", default="", help="hook caption shown top-of-frame")
    p.add_argument("--out", required=True, type=Path, help="output mp4 path")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not args.banner.exists():
        sys.exit(f"Banner not found: {args.banner}")
    out = compose_reel(args.banner, args.hook, args.out)
    print(f"Reel written: {out}")
    print(f"Duration: {DURATION_SECONDS}s @ {FPS}fps, {REEL_W}x{REEL_H}")


if __name__ == "__main__":
    main()
