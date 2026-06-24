#!/usr/bin/env python3
"""attach_guide_products.py — LLM-curate Amazon products into product-less guides.

47% of generated guides ship with zero `productSlugs`, so the guide template
renders no affiliate links and they drive zero Amazon traffic. For each empty
guide this builds a candidate pool (catalog products in the guide's category)
and asks Claude — via the growth-engine's forced-tool client — to pick the 3-5
products that genuinely fit the guide's angle and budget, then injects their
slugs into the first section (cards surface high on the page + in the bottom
grid). Slugs are validated against the pool, so the model can't invent links.

Slug derivation mirrors site/app/lib/products.ts slugify() exactly.

Usage:
  venv/bin/python attach_guide_products.py [--per-guide 4] [--limit N] [--apply] [-v]
Default is DRY-RUN (prints picks + rationale, writes nothing).
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "growth-engine"))
from lib.claude_client import complete_with_tool  # noqa: E402
from lib.config import CONFIG  # noqa: E402

CSV_PATH = REPO / "products" / "top-1000.csv"
GUIDE_DIR = REPO / "site" / "content" / "guides-generated"
MODEL = CONFIG["article"]["model"]

SELECT_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_slugs": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 6,
            "description": "Product slugs, best-fit first, chosen ONLY from the candidate list.",
        },
        "rationale": {"type": "string", "description": "One sentence on why these fit the guide."},
    },
    "required": ["selected_slugs"],
}

SYSTEM = (
    "You are the editor of an Amazon affiliate buying-guide site. Given a guide "
    "and a list of candidate products (all from the guide's category), pick the "
    "products that genuinely belong in THIS guide. Respect the guide's specific "
    "angle and budget: a 'under $600' or 'budget' guide must pick affordable "
    "options, not premium flagships; a 'beginner'/'students' guide avoids pro-tier "
    "gear; a use-case guide (e.g. 'for YouTube', 'for travel') picks products that "
    "fit that use. Prefer items with strong ratings and review counts. Choose the "
    "best 3-5. Use ONLY slugs from the candidate list — never invent one."
)


def slugify(text: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", text.lower()))


def load_catalog() -> list[dict]:
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8-sig")))
    out, seen = [], set()
    for r in rows:
        name = (r.get("Product Name") or "").strip()
        if not name:
            continue
        slug = slugify(name)
        if slug in seen:
            continue
        seen.add(slug)
        out.append({
            "name": name,
            "slug": slug,
            "cat": slugify(r.get("Category") or ""),
            "price": (r.get("Price Range") or "").strip(),
            "rating": (r.get("Rating") or "").strip(),
            "reviews": (r.get("Review Count") or "").strip(),
        })
    return out


def curate(guide: dict, pool: list[dict], n: int) -> tuple[list[str], str]:
    headings = " | ".join(s.get("heading", "") for s in guide.get("sections", []))
    candidates = "\n".join(
        f"- slug={p['slug']} | {p['name']} | price={p['price']} | {p['rating']}★ {p['reviews']} reviews"
        for p in pool
    )
    user = (
        f"GUIDE TITLE: {guide.get('title')}\n"
        f"DESCRIPTION: {guide.get('description')}\n"
        f"SECTION HEADINGS: {headings}\n\n"
        f"CANDIDATE PRODUCTS (category: {guide.get('categorySlug')}):\n{candidates}\n\n"
        f"Select the best {min(n, 5)}–5 products for this guide."
    )
    result = complete_with_tool(
        system=SYSTEM,
        user=user,
        tool_name="select_products",
        tool_description="Return the most relevant product slugs for this buying guide.",
        input_schema=SELECT_SCHEMA,
        model=MODEL,
        temperature=0.3,
    )
    pool_slugs = {p["slug"] for p in pool}
    picked = [s for s in (result.get("selected_slugs") or []) if s in pool_slugs][:n]
    return picked, result.get("rationale", "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-guide", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0, help="cap guides processed (0 = all)")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    catalog = load_catalog()
    by_cat: dict[str, list[dict]] = {}
    for p in catalog:
        by_cat.setdefault(p["cat"], []).append(p)

    files = sorted(glob.glob(str(GUIDE_DIR / "*.json")))
    targets = []
    for f in files:
        g = json.load(open(f, encoding="utf-8"))
        existing = [s for sec in g.get("sections", []) for s in (sec.get("productSlugs") or [])]
        if not existing and g.get("sections"):
            targets.append((f, g))
    if args.limit:
        targets = targets[: args.limit]

    changed = no_match = 0
    for f, guide in targets:
        pool = by_cat.get(guide.get("categorySlug", ""), [])
        if not pool:
            no_match += 1
            print(f"  NO POOL  [{guide.get('categorySlug')}] {os.path.basename(f)}")
            continue
        picks, why = curate(guide, pool, args.per_guide)
        if not picks:
            no_match += 1
            print(f"  NO PICKS [{guide.get('categorySlug')}] {os.path.basename(f)}")
            continue
        guide["sections"][0]["productSlugs"] = picks
        changed += 1
        print(f"\n{guide.get('slug')}  [{guide.get('categorySlug')}]  ({len(picks)} picks)")
        for s in picks:
            print(f"    + {s}")
        if why:
            print(f"    → {why}")
        if args.apply:
            json.dump(guide, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"\n[{mode}] guides curated: {changed} | skipped (no pool/picks): {no_match} | model: {MODEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
