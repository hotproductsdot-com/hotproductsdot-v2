"""Generate a 30-day content plan for hotproductsdot.com.

Uses Claude tool-use to force a strict JSON schema response.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.claude_client import complete_with_tool  # noqa: E402
from lib.config import CONFIG, is_dry_run  # noqa: E402
from lib.seo import has_search_provider, search  # noqa: E402
from lib.site_inspector import all_known_guide_slugs  # noqa: E402


SYSTEM_PROMPT = """You are an SEO strategist for an Amazon affiliate site.
Produce a 30-day editorial calendar of buying-guide articles that will rank
on Google AND get cited by ChatGPT/Perplexity.

Rules:
- Every article must have clear commercial or informational-commercial intent.
- Titles MUST be specific, include the year (2026), avoid clickbait.
- Each brief maps to exactly one of the provided target_categories.
- Avoid topics already covered (you'll receive an exclusion list).
- Mix formats: 60% "best X" listicles, 25% comparisons, 15% how-to/explainers.
- Distribute briefs evenly across the target_categories.
- Never plan two articles about the same narrow sub-topic (e.g. "stand mixers") within 5 briefs of each other — interleave categories so no two consecutive briefs share the same product type.
- target_keyword: the primary commercial query (1-5 words).
- related_keywords: 3-6 secondary queries.
- suggested_outline: 4-6 H2 headings, no body text.
- intent: one of "commercial", "informational", "comparison".
- slug: kebab-case, unique, descriptive (e.g. "best-instant-pot-2026").

Always submit your full plan via the submit_content_plan tool — never reply
with prose.
"""


PLAN_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "briefs": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "title": {"type": "string"},
                    "target_keyword": {"type": "string"},
                    "related_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "intent": {
                        "type": "string",
                        "enum": ["commercial", "informational", "comparison"],
                    },
                    "target_category_slug": {"type": "string"},
                    "suggested_outline": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                    },
                    "rationale": {"type": "string"},
                },
                "required": [
                    "slug",
                    "title",
                    "target_keyword",
                    "related_keywords",
                    "intent",
                    "target_category_slug",
                    "suggested_outline",
                    "rationale",
                ],
            },
        }
    },
    "required": ["briefs"],
}


def _competitor_snippets(category_name: str, seed_keywords):
    if not has_search_provider():
        return []
    snips = []
    for kw in seed_keywords[:2]:
        for r in search(kw, max_results=5):
            snips.append({"title": r.title, "url": r.url, "snippet": r.snippet[:240]})
    return snips


def build_plan(count: int) -> list:
    cats = CONFIG["target_categories"]
    excluded = sorted(set(all_known_guide_slugs()))

    competitor_intel = {}
    for cat in cats:
        competitor_intel[cat["slug"]] = _competitor_snippets(
            cat["name"], cat["seed_keywords"]
        )

    user_payload = {
        "site": CONFIG["site"],
        "target_categories": cats,
        "exclude_slugs": excluded,
        "competitor_serp_snippets": competitor_intel,
        "count": count,
    }
    user_msg = (
        f"Produce {count} article briefs for the next 30 days. Use the SERP "
        f"snippets to identify gaps competitors haven't covered well. Submit "
        f"the plan via the submit_content_plan tool.\n\nINPUT:\n"
        + json.dumps(user_payload, indent=2)
    )

    if is_dry_run():
        return _stub_plan(cats, count)

    result = complete_with_tool(
        system=SYSTEM_PROMPT,
        user=user_msg,
        tool_name="submit_content_plan",
        tool_description="Submit the 30-day editorial calendar.",
        input_schema=PLAN_TOOL_SCHEMA,
        max_tokens=12000,
        temperature=0.5,
    )
    briefs = result.get("briefs", [])
    if not isinstance(briefs, list) or not briefs:
        raise RuntimeError(f"submit_content_plan returned no briefs: {result!r}")
    return briefs


def _stub_plan(cats, count):
    out = []
    for i in range(count):
        cat = cats[i % len(cats)]
        out.append(
            {
                "slug": f"stub-{cat['slug']}-{i+1}",
                "title": f"Stub Article {i+1} for {cat['name']} (2026)",
                "target_keyword": cat["seed_keywords"][0],
                "related_keywords": cat["seed_keywords"][:3],
                "intent": "commercial",
                "target_category_slug": cat["slug"],
                "suggested_outline": [
                    "What to look for",
                    "Top picks",
                    "Comparison",
                    "Buying tips",
                    "FAQ",
                ],
                "rationale": "Stub for dry-run.",
            }
        )
    return out


def save_plan(plan: list, refresh: bool) -> Path:
    path = Path(CONFIG["paths"]["content_plan"])
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if path.exists() and not refresh:
        try:
            existing = json.loads(path.read_text(encoding="utf-8")).get("briefs", [])
        except Exception:
            existing = []

    kept = [b for b in existing if b.get("status") == "published"]
    kept_slugs = {b["slug"] for b in kept}
    new_briefs = [
        {**b, "status": "pending", "addedAt": datetime.now(timezone.utc).isoformat()}
        for b in plan
        if b.get("slug") not in kept_slugs
    ]

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "site": CONFIG["site"]["domain"],
        "briefs": kept + new_briefs,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser(description="Generate a content plan via tool-use.")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--count", type=int, default=30)
    args = ap.parse_args()

    print(f"[planner] Building plan with {args.count} briefs...")
    if not has_search_provider() and not is_dry_run():
        print("[planner] No TAVILY_API_KEY/SERPER_API_KEY — skipping competitor SERP intel.")
    plan = build_plan(args.count)
    out = save_plan(plan, refresh=args.refresh)
    print(f"[planner] Saved {len(plan)} briefs to {out}")


if __name__ == "__main__":
    main()
