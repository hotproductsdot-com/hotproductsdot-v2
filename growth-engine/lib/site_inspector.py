"""Reads the existing Next.js site to know which products + categories exist.
Used by the article generator to wire `productSlugs` to real items.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from .config import CONFIG, REPO_ROOT


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-+", "-", s)


def _find_products_csv() -> Optional[Path]:
    """Locate the products CSV. site/app/lib/products.ts reads
    ``../products/top-1000.csv`` relative to ``site/`` cwd, so the canonical
    path is repo-root/products/top-1000.csv. Falls back to a shallow scan
    of a few known content directories — never recurses into node_modules.
    """
    explicit = REPO_ROOT / "products" / "top-1000.csv"
    if explicit.exists():
        return explicit
    safe_dirs = [
        REPO_ROOT / "products",
        REPO_ROOT / "data",
        REPO_ROOT / "site" / "public",
        REPO_ROOT / "site" / "data",
        REPO_ROOT / "site" / "content",
    ]
    candidates: List[Path] = []
    for d in safe_dirs:
        if d.exists():
            candidates.extend(d.glob("*.csv"))
            candidates.extend(d.glob("*/*.csv"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_size)


def load_products() -> List[Dict[str, str]]:
    """Return list of {slug, name, category, categorySlug, ...} dicts."""
    csv_path = _find_products_csv()
    if not csv_path or not csv_path.exists():
        return []
    out: List[Dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Site CSV uses "Product Name", "Category", "Price Range", etc.
            name = (
                row.get("Product Name")
                or row.get("name")
                or row.get("Name")
                or ""
            ).strip()
            cat = (row.get("Category") or row.get("category") or "").strip()
            if not name or not cat:
                continue
            slug = (row.get("slug") or row.get("Slug") or "").strip() or _slugify(name)
            out.append(
                {
                    "name": name,
                    "slug": slug,
                    "category": cat,
                    "categorySlug": _slugify(cat),
                    "rating": (row.get("Rating") or row.get("rating") or "").strip(),
                    "reviewCount": (
                        row.get("Review Count")
                        or row.get("reviewCount")
                        or row.get("review_count")
                        or ""
                    ).strip(),
                    "priceRange": (
                        row.get("Price Range")
                        or row.get("priceRange")
                        or row.get("price_range")
                        or ""
                    ).strip(),
                }
            )
    return out


def products_by_category() -> Dict[str, List[Dict[str, str]]]:
    bucket: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for p in load_products():
        bucket[p["categorySlug"]].append(p)
    return bucket


def existing_guide_slugs() -> List[str]:
    """Read existing guide slugs from site/app/lib/guides.ts to avoid collisions."""
    guides_ts = REPO_ROOT / "site" / "app" / "lib" / "guides.ts"
    if not guides_ts.exists():
        return []
    text = guides_ts.read_text(encoding="utf-8")
    return re.findall(r'slug:\s*"([^"]+)"', text)


def existing_generated_guide_slugs() -> List[str]:
    """Slugs of guides we've already generated (to avoid duplicates)."""
    out_dir = Path(CONFIG["paths"]["generated_guides_dir"])
    if not out_dir.exists():
        return []
    return [p.stem for p in out_dir.glob("*.json")]


def all_known_guide_slugs() -> List[str]:
    return existing_guide_slugs() + existing_generated_guide_slugs()


def category_slugs() -> List[str]:
    """All category slugs the site knows about — from products + config."""
    found = {p["categorySlug"] for p in load_products()}
    for cat in CONFIG.get("target_categories", []):
        found.add(cat["slug"])
    return sorted(found)
