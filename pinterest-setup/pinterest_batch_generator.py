"""
pinterest_batch_generator.py — generate a day's worth of Pinterest pins.

Bypasses the Pinterest API approval bottleneck (3-5 day wait) by producing
upload-ready assets:

  1. 1000x1500 vertical PNG pin images (Pinterest's preferred 2:3 ratio)
  2. A CSV manifest you paste into Pinterest's bulk-upload web scheduler
     OR feed to pinterest_poster_stub.py once API access lands

Output structure:
  pinterest-setup/batches/2026-05-01/
    01-vitamix-5200-professional-blender.png
    02-ninja-foodi-9-in-1-pressure-cooker.png
    ...
    manifest.csv   (title, description, image, link, board, alt_text)

Usage:
  python pinterest-setup/pinterest_batch_generator.py --category kitchen --count 5
  python pinterest-setup/pinterest_batch_generator.py --board "Best Kitchen Gadgets 2026" --count 10
  python pinterest-setup/pinterest_batch_generator.py --all-boards --count 5

Pinterest's web bulk uploader expects the CSV columns:
  Title, Description, Media URL or local path, Link, Board, Alt text

Affiliate tag is `hotproduct033-20` (matches site/app/lib/constants.ts).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from instagram import banner_compose as bc
from PIL import Image, ImageDraw, ImageFilter

AFFILIATE_TAG = "hotproduct033-20"
SITE_URL = "https://hotproductsdot.com"
SCHEDULER_HASHTAG = "#affiliate"

PIN_W = 1000
PIN_H = 1500

PRODUCTS_JSON = REPO_ROOT / "site" / "products.json"
BOARDS_CSV = REPO_ROOT / "pinterest-setup" / "BOARDS.csv"
BATCHES_DIR = REPO_ROOT / "pinterest-setup" / "batches"


@dataclass(frozen=True)
class Product:
    name: str
    slug: str
    category: str
    category_slug: str
    price_range: str
    rating: float
    review_count: int
    affiliate_potential: int
    amazon_url: str
    image_url: str
    badge: str | None


@dataclass(frozen=True)
class Board:
    name: str
    site_path: str
    description: str
    keywords: str


@dataclass(frozen=True)
class PinManifestRow:
    title: str
    description: str
    image_path: str
    link: str
    board: str
    alt_text: str


def load_products() -> list[Product]:
    raw = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    return [
        Product(
            name=p["name"],
            slug=p["slug"],
            category=p["category"],
            category_slug=p["categorySlug"],
            price_range=p.get("priceRange", "Check Price"),
            rating=float(p.get("rating") or 0),
            review_count=int(p.get("reviewCount") or 0),
            affiliate_potential=int(p.get("affiliatePotential") or 0),
            amazon_url=p["amazonUrl"],
            image_url=p.get("imageUrl", ""),
            badge=p.get("badge"),
        )
        for p in raw
    ]


def load_boards() -> list[Board]:
    with BOARDS_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            Board(
                name=row["Board Name"].strip(),
                site_path=row["Site URL (link from board)"].strip(),
                description=row["Description (200-500 char)"].strip(),
                keywords=row["Primary Keywords"].strip(),
            )
            for row in reader
        ]


def board_for_category(boards: list[Board], category_slug: str) -> Board | None:
    target = f"/best/{category_slug}"
    for b in boards:
        if b.site_path == target:
            return b
    return None


MIN_REVIEWS_FOR_TRUST = 50  # avoid pinning products with thin review signal


def top_products(products: list[Product], category_slug: str, count: int) -> list[Product]:
    pool = [p for p in products if p.category_slug == category_slug]
    trusted = [p for p in pool if p.review_count >= MIN_REVIEWS_FOR_TRUST]
    if len(trusted) >= count:
        pool = trusted
    pool.sort(key=lambda p: (-p.affiliate_potential, -p.rating, -p.review_count))
    return pool[:count]


def build_destination_url(board: Board, product: Product, *, mode: str = "site") -> str:
    """
    mode='site'   → /best/<category> (preferred — site enforces correct tag)
    mode='direct' → Amazon URL with ascsubtag (use sparingly, hot/seasonal)
    """
    today = date.today().strftime("%Y%m%d")
    pin_slug = product.slug[:60]

    if mode == "site":
        utm = (
            f"?utm_source=pinterest&utm_medium=social"
            f"&utm_campaign={board.site_path.strip('/').replace('/', '-')}"
            f"&utm_content=pin-{pin_slug}"
        )
        return f"{SITE_URL}{board.site_path}{utm}"

    sep = "&" if "?" in product.amazon_url else "?"
    url = product.amazon_url
    if "tag=" not in url:
        url = f"{url}{sep}tag={AFFILIATE_TAG}"
        sep = "&"
    board_slug = board.name.lower().replace(" ", "-")[:40]
    return f"{url}{sep}ascsubtag=pin-{board_slug}-{today}"


def make_pin_title(product: Product, board: Board) -> str:
    """40 char max — Pinterest weights this most for search."""
    name = product.name
    short = name.split(",")[0].split("|")[0].strip()
    if len(short) > 38:
        short = short[:35].rstrip() + "..."
    return short


def make_pin_description(product: Product, board: Board) -> str:
    """500 char max. Follows the 5-part formula in PIN_DESCRIPTIONS.md."""
    rating_str = f"{product.rating:.1f}★ ({product.review_count:,} reviews)" if product.review_count else ""
    price_str = product.price_range if product.price_range != "Check Price" else ""

    hook = _hook_for(product, board)

    body = (
        f"{product.name}. "
        f"{'Rated ' + rating_str + ' on Amazon. ' if rating_str else ''}"
        f"{'Currently around ' + price_str + '. ' if price_str else ''}"
        f"One of the most-bought picks in {product.category.lower()} this month."
    )

    cta = "Tap the pin to see today's price on Amazon →"

    keywords = ", ".join(f"#{w.strip().replace(' ', '')}" for w in board.keywords.split(",")[:4])
    tags = f"{keywords} #amazonfinds {SCHEDULER_HASHTAG}"

    desc = f"{hook}\n\n{body}\n\n{cta}\n\n{tags}"
    return desc[:497] + "..." if len(desc) > 500 else desc


def _hook_for(product: Product, board: Board) -> str:
    cat = product.category.lower()
    name_lower = product.name.lower()
    if "kitchen" in cat or "coffee" in cat:
        return f"The {product.name.split(' ')[0]} that quietly took over my counter ✨"
    if "beauty" in cat or "skincare" in cat:
        return f"Skin-people will not stop saving this 💧"
    if "gaming" in cat:
        return f"Setup-of-the-month material 🎮"
    if "fitness" in cat or "health" in cat:
        return f"Cardio days suddenly fun again 💪"
    if "drone" in cat or "photo" in cat:
        return f"Shots that look way more expensive than they are 📸"
    if "smart" in cat or "security" in cat:
        return f"Renter-friendly smart home glow-up 🏠"
    return f"Adding this to my cart for real 🛒"


def make_alt_text(product: Product) -> str:
    """Accessibility + SEO. Describe the image."""
    return f"{product.name} — {product.category} on Amazon"[:500]


def compose_pin_image(product: Product) -> Image.Image:
    """Build a 1000x1500 vertical pin reusing banner_compose primitives."""
    canvas = Image.new("RGBA", (PIN_W, PIN_H), (*bc.BG_DARK, 255))

    glow = Image.new("RGBA", (PIN_W, PIN_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = PIN_W // 2, int(PIN_H * 0.38)
    gd.ellipse([cx - 520, cy - 320, cx + 520, cy + 320], fill=(*bc.BG_LIFT, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=110))
    canvas = Image.alpha_composite(canvas, glow)

    orange = Image.new("RGBA", (PIN_W, PIN_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orange)
    od.ellipse([cx - 360, cy + 160, cx + 360, cy + 480], fill=(*bc.ORANGE, 48))
    orange = orange.filter(ImageFilter.GaussianBlur(radius=85))
    canvas = Image.alpha_composite(canvas, orange)

    if product.image_url:
        product_img = _load_product_image(product)
        if product_img is not None:
            canvas = _paste_centered_product(canvas, product_img)

    canvas = _draw_pin_text(canvas, product)
    return canvas.convert("RGB")


def _load_product_image(product: Product) -> Image.Image | None:
    if product.image_url.startswith("/"):
        local = REPO_ROOT / "site" / "public" / product.image_url.lstrip("/").split("?")[0]
        if local.exists():
            try:
                return Image.open(local).convert("RGBA")
            except Exception:
                return None
        return None
    try:
        raw = bc._fetch_image_bytes(product.image_url)  # noqa: SLF001
        from io import BytesIO
        return Image.open(BytesIO(raw)).convert("RGBA")
    except Exception:
        return None


def _paste_centered_product(canvas: Image.Image, prod: Image.Image) -> Image.Image:
    target_w = int(PIN_W * 0.72)
    target_h = int(PIN_H * 0.45)
    scale = min(target_w / prod.width, target_h / prod.height)
    new_w, new_h = int(prod.width * scale), int(prod.height * scale)
    prod = prod.resize((new_w, new_h), Image.LANCZOS)

    x = (PIN_W - new_w) // 2
    y = int(PIN_H * 0.18)
    canvas.alpha_composite(prod, (x, y))
    return canvas


def _draw_pin_text(canvas: Image.Image, product: Product) -> Image.Image:
    draw = ImageDraw.Draw(canvas)

    title_font = bc._load_font(64, bold=True)  # noqa: SLF001
    sub_font = bc._load_font(36)  # noqa: SLF001
    pill_font = bc._load_font(28, bold=True)  # noqa: SLF001

    title = product.name.split(",")[0]
    if len(title) > 60:
        title = title[:57].rstrip() + "..."
    lines = bc._wrap(title, title_font, PIN_W - 100, draw)  # noqa: SLF001

    y = int(PIN_H * 0.70)
    for line in lines[:3]:
        x = bc._center_x(line, title_font, draw)  # noqa: SLF001
        draw.text((x, y), line, font=title_font, fill=(*bc.WHITE, 255))
        y += bc._text_h(line, title_font, draw) + 6  # noqa: SLF001

    if product.price_range and product.price_range != "Check Price":
        sub = product.price_range
        sx = bc._center_x(sub, sub_font, draw)  # noqa: SLF001
        draw.text((sx, y + 16), sub, font=sub_font, fill=(*bc.ORANGE, 255))

    pill_text = "hotproductsdot.com"
    pw = draw.textlength(pill_text, font=pill_font) + 56
    ph = 60
    px = (PIN_W - pw) // 2
    py = PIN_H - 110
    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=30, fill=(*bc.PILL_BG, 220))
    tx = px + (pw - draw.textlength(pill_text, font=pill_font)) // 2
    ty = py + (ph - 36) // 2
    draw.text((tx, ty), pill_text, font=pill_font, fill=(*bc.WHITE, 255))

    return canvas


def generate_batch(
    boards: list[Board],
    products: list[Product],
    target_boards: list[Board],
    per_board: int,
    out_dir: Path,
) -> list[PinManifestRow]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[PinManifestRow] = []
    counter = 1

    for board in target_boards:
        category_slug = board.site_path.removeprefix("/best/").removeprefix("/")
        picks = top_products(products, category_slug, per_board)
        if not picks:
            print(f"  [skip] {board.name}: no products for slug '{category_slug}'", file=sys.stderr)
            continue

        for product in picks:
            img = compose_pin_image(product)
            filename = f"{counter:02d}-{product.slug}.png"
            img_path = out_dir / filename
            img.save(img_path, "PNG", optimize=True)

            mode = "site" if counter % 10 < 7 else "direct"
            link = build_destination_url(board, product, mode=mode)

            try:
                rel = img_path.relative_to(REPO_ROOT)
                image_path_str = str(rel)
            except ValueError:
                image_path_str = str(img_path)
            rows.append(
                PinManifestRow(
                    title=make_pin_title(product, board),
                    description=make_pin_description(product, board),
                    image_path=image_path_str,
                    link=link,
                    board=board.name,
                    alt_text=make_alt_text(product),
                )
            )
            counter += 1
            print(f"  [{counter - 1:02d}] {product.slug} → {board.name} ({mode})")

    return rows


def write_manifest(rows: list[PinManifestRow], out_dir: Path) -> Path:
    manifest_path = out_dir / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Title", "Description", "Image Path", "Link", "Board", "Alt Text"])
        for r in rows:
            writer.writerow([r.title, r.description, r.image_path, r.link, r.board, r.alt_text])
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Pinterest pin batch.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--category", help="categorySlug (e.g., 'kitchen', 'gaming-pcs')")
    g.add_argument("--board", help="exact board name from BOARDS.csv")
    g.add_argument("--all-boards", action="store_true", help="generate for every board")
    parser.add_argument("--count", type=int, default=5, help="pins per board (default 5)")
    parser.add_argument("--out", type=Path, help="output dir (default batches/<today>/)")
    return parser.parse_args()


def resolve_target_boards(args, boards: list[Board]) -> list[Board]:
    if args.category:
        b = board_for_category(boards, args.category)
        if not b:
            sys.exit(f"No board for category slug '{args.category}'. Check BOARDS.csv.")
        return [b]
    if args.board:
        for b in boards:
            if b.name.lower() == args.board.lower():
                return [b]
        sys.exit(f"No board named '{args.board}'. Check BOARDS.csv.")
    return boards


def main() -> None:
    args = parse_args()
    products = load_products()
    boards = load_boards()
    targets = resolve_target_boards(args, boards)

    out_dir = args.out or (BATCHES_DIR / date.today().isoformat())
    print(f"Generating {args.count} pin(s) per board across {len(targets)} board(s) → {out_dir}")

    rows = generate_batch(boards, products, targets, args.count, out_dir)
    if not rows:
        sys.exit("No pins generated. Check product/board configuration.")

    manifest = write_manifest(rows, out_dir)
    print(f"\nDone. {len(rows)} pins generated.")
    print(f"Manifest: {manifest}")
    print(f"Images:   {out_dir}")
    print("\nNext steps:")
    print("  1. Open Pinterest → Create → upload PNGs from this batch")
    print("  2. Use manifest.csv columns for title/description/link/board/alt_text")
    print("  3. Schedule across 8-11 AM/PM ET windows for max reach")


if __name__ == "__main__":
    main()
