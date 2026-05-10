"""Find niche-relevant backlink prospects and draft outreach emails.
Uses Claude tool-use for guaranteed structured scoring + outreach output.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

import tldextract

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.claude_client import complete_with_tool  # noqa: E402
from lib.config import CONFIG, is_dry_run  # noqa: E402
from lib.seo import has_search_provider, search  # noqa: E402
from lib.tracking import init_backlinks, list_backlinks, upsert_backlink  # noqa: E402


SCORE_PROMPT = """You score backlink prospects for an Amazon affiliate site.
For each prospect, decide:
- score (1-10): niche fit + likelihood of accepting a link
  9-10: niche-perfect, accepts guest posts/roundups, real audience
  7-8:  relevant, plausible link, may need creative angle
  4-6:  tangentially related
  1-3:  irrelevant, spammy, or impossible (forum, social, big retailer)
- rationale: <= 30 words
- outreach_subject: <= 60 chars, references their actual content (only if score >= 7)
- outreach_body: 80-140 words, plain text, signed by from_name (only if score >= 7)

If score < 7, return outreach_subject and outreach_body as empty strings.

Always submit your scores via the submit_scores tool — never reply with prose.
"""


SCORE_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "scored": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "score": {"type": "integer", "minimum": 1, "maximum": 10},
                    "rationale": {"type": "string"},
                    "outreach_subject": {"type": "string"},
                    "outreach_body": {"type": "string"},
                },
                "required": ["domain", "score", "rationale", "outreach_subject", "outreach_body"],
            },
        }
    },
    "required": ["scored"],
}


def _root_domain(url: str) -> str:
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}".lower() if ext.domain and ext.suffix else url


def _build_queries() -> List[str]:
    out: List[str] = []
    for cat in CONFIG["target_categories"]:
        for kw in cat["seed_keywords"][:1]:
            for mod in CONFIG["backlinks"]["search_modifiers"][:2]:
                out.append(f"{kw} {mod}")
    return out


def find_prospects(target_count: int) -> List[Dict]:
    if not has_search_provider() and not is_dry_run():
        print("[backlinks] No TAVILY/SERPER key — cannot find prospects.")
        return []

    excluded = set(CONFIG["backlinks"]["exclude_domains"])
    seen: set[str] = set()
    raw: List[Dict] = []
    for q in _build_queries():
        results = search(q, max_results=8) if not is_dry_run() else []
        for r in results:
            domain = _root_domain(r.url)
            if not domain or domain in excluded or domain in seen:
                continue
            if any(x in domain for x in excluded):
                continue
            seen.add(domain)
            raw.append({
                "query": q,
                "domain": domain,
                "url": r.url,
                "title": r.title,
                "snippet": (r.snippet or "")[:300],
            })
            if len(raw) >= target_count * 3:
                break
        if len(raw) >= target_count * 3:
            break

    if is_dry_run():
        return [
            {
                "domain": f"stub-blog-{i}.com",
                "url": f"https://stub-blog-{i}.com/best-products",
                "title": f"Stub Blog {i}",
                "snippet": "Stub snippet.",
                "score": 8,
                "rationale": "Stub.",
                "outreach_subject": f"Suggestion for your roundup #{i}",
                "outreach_body": "Stub outreach body.",
            }
            for i in range(target_count)
        ]

    if not raw:
        return []

    scored: List[Dict] = []
    batch_size = 8
    for i in range(0, len(raw), batch_size):
        batch = raw[i : i + batch_size]
        payload = {
            "site": CONFIG["site"],
            "from_name": CONFIG["backlinks"]["outreach_from_name"],
            "from_email": CONFIG["backlinks"]["outreach_from_email"],
            "prospects": batch,
        }
        try:
            res = complete_with_tool(
                system=SCORE_PROMPT,
                user="Score and draft outreach via the submit_scores tool.\n\nINPUT:\n"
                + json.dumps(payload, indent=2),
                tool_name="submit_scores",
                tool_description="Submit scored backlink prospects with outreach drafts.",
                input_schema=SCORE_TOOL_SCHEMA,
                max_tokens=6000,
                temperature=0.4,
            )
        except Exception as e:
            print(f"[backlinks] Scoring batch failed: {e}")
            continue

        items = res.get("scored", []) if isinstance(res, dict) else []
        if not items:
            continue
        by_domain = {p["domain"]: p for p in batch}
        for s in items:
            base = by_domain.get(s.get("domain"))
            if base:
                scored.append({**base, **s})

    scored.sort(key=lambda x: x.get("score", 0), reverse=True)
    return scored[:target_count]


def _export_csv() -> Path:
    rows = list_backlinks(status="prospect", limit=500)
    out = Path(CONFIG["paths"]["data_dir"]) / "backlink_outreach_queue.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["domain", "url", "score", "subject", "body", "title", "snippet", "found_at"])
        for r in rows:
            if not r.get("outreach_subject"):
                continue
            w.writerow([
                r["domain"], r["url"], r["relevance_score"],
                r["outreach_subject"], r["outreach_body"],
                r["title"], r["snippet"], r["found_at"],
            ])
    return out


def main():
    ap = argparse.ArgumentParser(description="Find backlink prospects via tool-use.")
    ap.add_argument("--count", type=int, default=CONFIG["schedule"]["backlink_targets_per_day"])
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    if args.export:
        out = _export_csv()
        print(f"[backlinks] Exported queue to {out}")
        return

    if args.status:
        init_backlinks()
        all_rows = list_backlinks(limit=10_000)
        c = Counter(r["status"] for r in all_rows)
        print("[backlinks] Pipeline status:")
        for k, v in c.most_common():
            print(f"  {k:12s} {v}")
        return

    print(f"[backlinks] Finding {args.count} prospects...")
    prospects = find_prospects(args.count)
    new_count = 0
    for p in prospects:
        added = upsert_backlink(
            domain=p["domain"], url=p["url"],
            title=p.get("title", ""), snippet=p.get("snippet", ""),
            relevance_score=int(p.get("score", 0)),
            outreach_subject=p.get("outreach_subject", ""),
            outreach_body=p.get("outreach_body", ""),
        )
        if added:
            new_count += 1
            print(f"  + {p['domain']:40s} score={p.get('score',0)}")
        else:
            print(f"  · {p['domain']:40s} (already in pipeline)")
    print(f"[backlinks] Added {new_count} new prospects.")


if __name__ == "__main__":
    main()
