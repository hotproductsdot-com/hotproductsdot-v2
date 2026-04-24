#!/usr/bin/env python3
"""
TikTok video content pipeline.

End-to-end: pick a product → render 5 branded 1080×1920 vertical frames →
stitch into a 14–15 s H.264 MP4 with Ken-Burns zoompan + xfade crossfades.
Silent output by design — TikTok's auto-add-music fills the audio track.

Usage:
    # Pick today's top-ranked product
    python tiktok_video_pipeline.py

    # Pick by slug (matches site/public/products/<slug>.jpg)
    python tiktok_video_pipeline.py --slug 1more-sonoflow-wireless-headphones

    # Pick by rank in the composite-score list (1 = highest)
    python tiktok_video_pipeline.py --rank 3

    # Custom output
    python tiktok_video_pipeline.py --out /tmp/test.mp4

Requirements:
    ffmpeg on PATH (>= 5.0 for xfade), Pillow, instagram/banner_compose.py

Exit codes:
    0 on success, 1 on usage/product error, 2 on ffmpeg error.
"""
from __future__ import annotations

import argparse
import csv
import logging
import math
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from instagram import video_frame_compose as vfc

CSV_PATH = Path(__file__).parent / "products" / "top-1000.csv"


def slugify(text: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", text.lower()))


def _parse_price(raw: str) -> float:
    m = re.search(r"[\d,]+(?:\.\d+)?", (raw or "").strip())
    if not m:
        return 0.0
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return 0.0


def _parse_bsr(raw: str) -> int | None:
    cleaned = re.sub(r"[^0-9]", "", (raw or "").strip())
    return int(cleaned) if cleaned else None


def _score(p: dict) -> float:
    bsr_factor = 1.0 / math.log(p["bsr"] + 2) if p["bsr"] is not None else 0.5
    return (
        p["rating"]
        * math.log(max(p["review_count"], 1))
        * math.log(max(p["price_num"], 1.0) + 1)
        * bsr_factor
    )


def load_top_products(n: int | None = None) -> list[dict]:
    """Mirror of post_daily.load_top_products without the heavy imports."""
    products: list[dict] = []
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("Product Name") or "").strip()
            amazon_url = (row.get("Amazon URL") or "").strip()
            if not name or not amazon_url:
                continue
            try:
                rating = float((row.get("Rating") or "0").strip() or "0")
            except ValueError:
                rating = 0.0
            if not (4.5 <= rating <= 5.0):
                continue
            try:
                review_count = int(re.sub(r"[^0-9]", "", (row.get("Review Count") or "0")))
            except ValueError:
                review_count = 0
            if review_count < 100:
                continue
            product = {
                "name":         name,
                "slug":         slugify(name),
                "category":     (row.get("Category") or "").strip(),
                "price":        (row.get("Price Range") or "Check price").strip(),
                "price_num":    _parse_price(row.get("Price Range") or ""),
                "rating":       rating,
                "reviews":      str(review_count),
                "review_count": review_count,
                "bsr":          _parse_bsr(row.get("BSR") or ""),
                "amazon_url":   amazon_url,
            }
            product["_score"] = _score(product)
            products.append(product)
    products.sort(key=lambda x: x["_score"], reverse=True)
    return products[:n] if n is not None else products

logger = logging.getLogger(__name__)

# ── Video spec ────────────────────────────────────────────────────────────────
FRAME_COUNT        = 5
CLIP_SECONDS       = 3.2          # per-frame zoompan duration
CROSSFADE_SECONDS  = 0.5
FPS                = 30
VIDEO_W, VIDEO_H   = 1080, 1920   # 9:16 TikTok vertical

PRODUCTS_DIR = Path(__file__).parent / "site" / "public" / "products"
OUTPUT_ROOT  = Path(__file__).parent / "generated_videos"


# ── Product resolution ────────────────────────────────────────────────────────

def _resolve_product(slug: str | None, rank: int | None) -> dict:
    """Return a product dict. Priority: explicit slug > rank > top-1."""
    products = load_top_products()
    if not products:
        raise RuntimeError("No products passed the availability filter in top-1000.csv")

    if slug:
        wanted = slugify(slug)
        for p in products:
            if p["slug"] == wanted:
                return p
        raise RuntimeError(f"Slug not found in top-1000 CSV: {slug}")

    if rank is not None:
        idx = rank - 1
        if not 0 <= idx < len(products):
            raise RuntimeError(f"Rank out of range (1..{len(products)}): {rank}")
        return products[idx]

    return products[0]


def _find_product_image(product: dict) -> Path:
    """Locate a local product JPEG. Falls back to trying alternative extensions."""
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = PRODUCTS_DIR / f"{product['slug']}{ext}"
        if candidate.exists():
            return candidate
    raise RuntimeError(
        f"No local image for '{product['slug']}' in {PRODUCTS_DIR}. "
        f"Run download-images.js or autofix-images.js first."
    )


# ── ffmpeg orchestration ──────────────────────────────────────────────────────

def _run(cmd: list[str]) -> None:
    logger.debug("$ %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffmpeg failed (exit %d)\nSTDERR:\n%s",
                     result.returncode, result.stderr[-1500:])
        raise SystemExit(2)


def _ensure_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("✗ ffmpeg not found on PATH. Install with `apt install ffmpeg`.")


# Alternating zoompan directions so consecutive frames don't feel identical.
# z_expr and xy_exprs drive a subtle ~1.0→1.15 zoom + pan.
_ZOOM_PATTERNS: list[dict[str, str]] = [
    # 0: slow zoom in, centered
    {"z": "min(zoom+0.0014,1.15)", "x": "iw/2-(iw/zoom/2)",       "y": "ih/2-(ih/zoom/2)"},
    # 1: zoom out from left
    {"z": "if(lte(zoom,1.0),1.15,max(1.001,zoom-0.0012))",
     "x": "iw*0.25-(iw/zoom/2)",  "y": "ih/2-(ih/zoom/2)"},
    # 2: pan right with slight zoom
    {"z": "min(zoom+0.0010,1.12)",
     "x": "iw*0.30+(iw*0.20)*on/duration", "y": "ih/2-(ih/zoom/2)"},
    # 3: pan up with zoom
    {"z": "min(zoom+0.0012,1.14)",
     "x": "iw/2-(iw/zoom/2)",
     "y": "ih*0.60-(ih*0.20)*on/duration"},
    # 4: gentle zoom in for CTA
    {"z": "min(zoom+0.0008,1.08)", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},
]


def _zoompan_clip(frame_path: Path, clip_path: Path, idx: int) -> None:
    """Render one still → zoompan MP4 of length CLIP_SECONDS."""
    frames_total = int(round(CLIP_SECONDS * FPS))
    pat = _ZOOM_PATTERNS[idx % len(_ZOOM_PATTERNS)]
    # No pre-upsample: zoompan on 1080x1920 input is fast and visually indistinguishable
    # from the upsampled path for our gentle 1.0→1.15 zoom range.
    zoompan = (
        f"zoompan=z='{pat['z']}':x='{pat['x']}':y='{pat['y']}':"
        f"d={frames_total}:s={VIDEO_W}x{VIDEO_H}:fps={FPS},"
        f"format=yuv420p"
    )
    _run([
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", str(FPS),
        "-t", f"{CLIP_SECONDS:.3f}",
        "-i", str(frame_path),
        "-vf", zoompan,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-preset", "veryfast", "-crf", "23",
        "-r", str(FPS),
        "-movflags", "+faststart",
        str(clip_path),
    ])


def _xfade_concat(clips: list[Path], out_path: Path) -> None:
    """Concatenate clips with fade transitions. Produces silent AAC for TikTok compat."""
    if len(clips) < 2:
        raise ValueError("Need at least 2 clips to crossfade")

    # Build xfade chain: [0][1]xfade=…[v01]; [v01][2]…
    filter_parts: list[str] = []
    prev = "[0:v]"
    offset = CLIP_SECONDS - CROSSFADE_SECONDS
    for i in range(1, len(clips)):
        tag = f"[v{i:02d}]"
        filter_parts.append(
            f"{prev}[{i}:v]xfade=transition=fade:"
            f"duration={CROSSFADE_SECONDS}:offset={offset:.3f}{tag}"
        )
        prev = tag
        offset += CLIP_SECONDS - CROSSFADE_SECONDS

    final_video_tag = prev
    total_duration = (
        CLIP_SECONDS * len(clips) - CROSSFADE_SECONDS * (len(clips) - 1)
    )

    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    # Silent stereo track — TikTok's auto-add-music replaces this, but some
    # uploaders/CDNs reject pure-video files.
    cmd += [
        "-f", "lavfi", "-t", f"{total_duration:.3f}",
        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-filter_complex", ";".join(filter_parts),
        "-map", final_video_tag,
        "-map", f"{len(clips)}:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-shortest",
        str(out_path),
    ]
    _run(cmd)


# ── Pipeline ──────────────────────────────────────────────────────────────────

def build_video(product: dict, source_image: Path, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ttvid_") as tmp:
        tmp_dir = Path(tmp)

        # Stage 1 — composite 5 still frames
        print(f"→ Rendering {FRAME_COUNT} frames in {tmp_dir}")
        frames: list[Path] = []
        for idx in range(FRAME_COUNT):
            frame_path = tmp_dir / f"frame_{idx:02d}.jpg"
            vfc.compose_frame(product, source_image, frame_path, idx)
            frames.append(frame_path)
            print(f"  ✓ frame {idx}  ({frame_path.stat().st_size // 1024} KB)")

        # Stage 2 — each still → zoompan clip
        print(f"→ Rendering {FRAME_COUNT} zoompan clips")
        clips: list[Path] = []
        for idx, frame in enumerate(frames):
            clip = tmp_dir / f"clip_{idx:02d}.mp4"
            _zoompan_clip(frame, clip, idx)
            clips.append(clip)
            print(f"  ✓ clip  {idx}  ({clip.stat().st_size // 1024} KB)")

        # Stage 3 — concat with crossfades
        print("→ Concatenating with crossfades")
        _xfade_concat(clips, out_path)

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"✓ {out_path} ({size_mb:.1f} MB)")
    return out_path


def _default_output(product: dict) -> Path:
    return OUTPUT_ROOT / date.today().isoformat() / f"{product['slug']}.mp4"


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", help="Product slug (matches product image filename)")
    parser.add_argument("--rank", type=int, help="Pick Nth product by composite score (1 = highest)")
    parser.add_argument("--out",  type=Path, help="Output MP4 path (default: generated_videos/YYYY-MM-DD/<slug>.mp4)")
    parser.add_argument("--image", type=Path, help="Override source product image path")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    _ensure_ffmpeg()

    try:
        product = _resolve_product(args.slug, args.rank)
    except RuntimeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    source_image = args.image or _find_product_image(product)
    out_path = args.out or _default_output(product)

    print(f"Product: {product['name']}")
    print(f"  slug  : {product['slug']}")
    print(f"  price : {product['price']}")
    print(f"  rating: {product['rating']}  reviews: {product['review_count']}")
    print(f"  image : {source_image}")
    print(f"  output: {out_path}")

    build_video(product, Path(source_image), Path(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
