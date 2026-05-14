"""Generate one article from the next pending brief in the content plan.
Uses Claude tool-use to force a strict article schema response.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.article_template import make_guide, slugify, write_guide  # noqa: E402
from lib.claude_client import complete_with_tool  # noqa: E402
from lib.config import CONFIG, is_dry_run  # noqa: E402
from lib.site_inspector import (  # noqa: E402
    all_known_guide_slugs,
    products_by_category,
)


SYSTEM_PROMPT = """You are a senior product reviewer writing for an Amazon affiliate site.
Tone: direct, expert, no-nonsense. Cuts through marketing fluff. Honest about
trade-offs. Always factual — no invented stats. Targets buyers who already
intend to buy and need help choosing.

Hard rules:
- Only reference products whose slug appears in available_product_slugs.
  If the category has zero available slugs, omit productSlugs entirely.
- Never fabricate prices, ratings, or specs not commonly known.
- Word count target: between min_word_count and max_word_count total.
- Plain prose only — NO markdown formatting in body fields.
- Open the first section with the target_keyword phrased naturally.
- Include a comparison/decision framework section.
- Include a concrete recommendation list section.
- categorySlug must equal the provided category_slug.

Always submit your article via the submit_article tool — never reply with prose.
"""


ARTICLE_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "maxLength": 80},
        "description": {"type": "string", "minLength": 100, "maxLength": 200},
        "category": {"type": "string"},
        "categorySlug": {"type": "string"},
        "sections": {
            "type": "array",
            "minItems": 4,
            "maxItems": 7,
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "body": {"type": "string", "minLength": 200},
                    "productSlugs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["heading", "body"],
            },
        },
        "faq": {
            "type": "array",
            "minItems": 3,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string", "minLength": 80},
                },
                "required": ["question", "answer"],
            },
        },
    },
    "required": ["title", "description", "category", "categorySlug", "sections", "faq"],
}


def _load_plan() -> Dict[str, Any]:
    path = Path(CONFIG["paths"]["content_plan"])
    if not path.exists():
        raise FileNotFoundError(
            f"No plan at {path}. Run scripts/1_keyword_research.py first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _save_plan(plan: Dict[str, Any]) -> None:
    Path(CONFIG["paths"]["content_plan"]).write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )


_SLUG_STOPWORDS = {"2026", "best", "vs", "for", "the", "a", "an", "of", "in", "and", "or", "to"}


def _slug_tokens(slug: str) -> set:
    return {t for t in slug.replace("-", " ").split() if t not in _SLUG_STOPWORDS and len(t) > 2}


def _recent_published(plan: Dict[str, Any], window: int = 3) -> List[Dict[str, Any]]:
    published = [b for b in plan["briefs"] if b.get("status") == "published"]
    published.sort(key=lambda b: b.get("publishedAt", ""), reverse=True)
    return published[:window]


def _too_similar(brief: Dict[str, Any], recent: List[Dict[str, Any]]) -> bool:
    """Return True if this brief's category or slug tokens overlap with any recent article."""
    cat = brief.get("target_category_slug", "")
    tokens = _slug_tokens(brief["slug"])
    for r in recent:
        if r.get("target_category_slug", "") == cat:
            return True
        if tokens & _slug_tokens(r["slug"]):
            return True
    return False


def _next_brief(
    plan: Dict[str, Any],
    slug: Optional[str],
    skip_slugs: set,
) -> Optional[Dict[str, Any]]:
    if slug:
        for b in plan["briefs"]:
            if b["slug"] == slug:
                return b
        return None

    reconciled = False
    pending: List[Dict[str, Any]] = []
    for b in plan["briefs"]:
        if b.get("status", "pending") != "pending":
            continue
        if b["slug"] in skip_slugs:
            b["status"] = "published"
            reconciled = True
            continue
        pending.append(b)
    if reconciled:
        _save_plan(plan)

    if not pending:
        return None

    recent = _recent_published(plan)
    # Prefer a brief that isn't topically close to recent articles.
    for b in pending:
        if not _too_similar(b, recent):
            return b
    # All pending briefs are similar to recent ones — fall back to first pending.
    print(f"[generator] Warning: all {len(pending)} pending briefs overlap with recent articles; picking first anyway.")
    return pending[0]


def _stub_article(brief: Dict[str, Any], available_slugs: List[str]) -> Dict[str, Any]:
    return {
        "title": brief["title"],
        "description": (brief.get("rationale") or brief["title"])[:160].ljust(120, " "),
        "category": brief["target_category_slug"].replace("-", " ").title(),
        "categorySlug": brief["target_category_slug"],
        "sections": [
            {
                "heading": h,
                "body": f"Stub body for section '{h}'. " * 30,
                "productSlugs": available_slugs[:1] if available_slugs else [],
            }
            for h in brief.get("suggested_outline", ["Overview", "Picks", "Tips", "FAQ"])[:4]
        ],
        "faq": [
            {"question": f"What is the best {brief['target_keyword']}?", "answer": "Stub answer." * 8},
            {"question": "How much should I spend?", "answer": "Stub answer." * 8},
            {"question": "Are there alternatives?", "answer": "Stub answer." * 8},
        ],
    }


def generate_article(brief: Dict[str, Any]) -> Dict[str, Any]:
    cat_slug = brief["target_category_slug"]
    products = products_by_category().get(cat_slug, [])
    available_slugs = [p["slug"] for p in products[:30]]

    user_payload = {
        "site": CONFIG["site"],
        "brief": brief,
        "category_slug": cat_slug,
        "available_product_slugs": available_slugs,
        "products_per_article": CONFIG["article"]["products_per_article"],
        "min_word_count": CONFIG["article"]["min_word_count"],
        "max_word_count": CONFIG["article"]["max_word_count"],
        "internal_link_targets": [
            f"/best/{cat_slug}",
            f"/category/{cat_slug}",
        ],
    }

    if is_dry_run():
        article = _stub_article(brief, available_slugs)
    else:
        article = complete_with_tool(
            system=SYSTEM_PROMPT,
            user="Write the article and submit it via the submit_article tool.\n\nINPUT:\n"
            + json.dumps(user_payload, indent=2),
            tool_name="submit_article",
            tool_description="Submit the finished buying-guide article.",
            input_schema=ARTICLE_TOOL_SCHEMA,
            max_tokens=12000,
            temperature=0.6,
        )

    for field in ["title", "description", "category", "categorySlug", "sections"]:
        if field not in article:
            raise ValueError(f"Generated article missing required field: {field}")
    allowed = set(available_slugs)
    for sec in article["sections"]:
        sec["productSlugs"] = [s for s in (sec.get("productSlugs") or []) if s in allowed]

    slug = brief.get("slug") or slugify(article["title"])
    known = set(all_known_guide_slugs())
    base = slug
    n = 2
    while slug in known:
        slug = f"{base}-{n}"
        n += 1

    return make_guide(
        slug=slug,
        title=article["title"],
        description=article["description"],
        category=article["category"],
        category_slug=article["categorySlug"],
        sections=article["sections"],
        target_keyword=brief.get("target_keyword", ""),
        related_keywords=brief.get("related_keywords", []),
        faq=article.get("faq") or [],
    )


def main():
    ap = argparse.ArgumentParser(description="Generate articles from the content plan.")
    ap.add_argument("--slug", help="Generate a specific brief by slug.")
    ap.add_argument("--count", type=int, default=1)
    args = ap.parse_args()

    plan = _load_plan()
    known_slugs = set(all_known_guide_slugs())
    written: List[Path] = []
    for _ in range(args.count):
        brief = _next_brief(plan, args.slug, known_slugs)
        if not brief:
            print("[generator] No pending briefs.")
            break
        print(f"[generator] Writing article for brief: {brief['slug']!r}")
        try:
            guide = generate_article(brief)
        except Exception as e:
            print(f"[generator] FAILED on {brief['slug']}: {e}")
            brief["status"] = "failed"
            brief["error"] = str(e)
            _save_plan(plan)
            break

        if is_dry_run():
            print(f"[generator] [DRY RUN] Would write {guide['slug']} ({sum(len((s.get('body') or '').split()) for s in guide['sections'])} words)")
        else:
            out = write_guide(guide)
            written.append(out)
            brief["status"] = "published"
            brief["publishedAt"] = datetime.now(timezone.utc).isoformat()
            brief["outputPath"] = str(out)
            _save_plan(plan)
        if args.slug:
            break

    print(f"[generator] Done. {len(written)} articles written.")
    for p in written:
        print(f"  - {p}")


if __name__ == "__main__":
    main()
