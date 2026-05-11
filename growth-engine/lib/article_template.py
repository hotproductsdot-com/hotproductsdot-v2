"""Builds a guide JSON object that matches site/app/lib/guides.ts schema.

The site schema is:
    {
      slug, title, description, category, categorySlug,
      sections: [{ heading, body, productSlugs?: string[] }]
    }

We extend it with optional metadata fields that are allowed by the type
(`unknown` extra keys are tolerated by Next.js since the type is loose).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .config import CONFIG


def slugify(text: str, max_len: int = 80) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    s = re.sub(r"-+", "-", s)
    return s[:max_len].rstrip("-")


def make_guide(
    *,
    title: str,
    description: str,
    category: str,
    category_slug: str,
    sections: List[Dict[str, Any]],
    target_keyword: str,
    related_keywords: List[str],
    faq: List[Dict[str, str]] | None = None,
    slug: str | None = None,
) -> Dict[str, Any]:
    """Assemble a guide dict ready to JSON-serialize.

    Sections are passed through as-is — they should already conform to
    {heading, body, productSlugs?}.
    """
    return {
        "slug": slug or slugify(title),
        "title": title.strip(),
        "description": description.strip(),
        "category": category.strip(),
        "categorySlug": category_slug.strip(),
        "publishedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "sections": sections,
        "_meta": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "model": CONFIG["article"]["model"],
            "targetKeyword": target_keyword,
            "relatedKeywords": related_keywords,
            "faq": faq or [],
            "wordCount": sum(len((s.get("body") or "").split()) for s in sections),
            "engine": "growth-engine v1",
        },
    }


def write_guide(guide: Dict[str, Any]) -> Path:
    out_dir = Path(CONFIG["paths"]["generated_guides_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{guide['slug']}.json"
    out_path.write_text(json.dumps(guide, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def list_generated_guides() -> List[Path]:
    out_dir = Path(CONFIG["paths"]["generated_guides_dir"])
    if not out_dir.exists():
        return []
    return sorted(out_dir.glob("*.json"))
