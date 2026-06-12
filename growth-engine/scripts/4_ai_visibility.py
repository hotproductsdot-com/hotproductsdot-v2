"""Track brand visibility in AI search engines (Claude, ChatGPT, Perplexity).

Pipeline:
  1. Read tracked_queries from config.yaml.
  2. For each enabled provider, ask the question and capture the response.
  3. Detect mentions of any brand_term ("hotproductsdot", etc.) and any
     domain citations.
  4. Log to SQLite (visibility_checks table).
  5. With --report, emit an HTML chart of mentions over time to data/visibility_report.html.

Usage:
    python scripts/4_ai_visibility.py
    python scripts/4_ai_visibility.py --report
    python scripts/4_ai_visibility.py --query "best kitchen gadgets 2026"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.claude_client import complete  # noqa: E402
from lib.config import CONFIG, is_dry_run  # noqa: E402
from lib.tracking import (  # noqa: E402
    init_visibility,
    log_visibility,
    visibility_history,
)


URL_RE = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)


def _detect(brand_terms: List[str], response_text: str) -> Tuple[bool, List[str]]:
    lower = response_text.lower()
    mentioned = any(t.lower() in lower for t in brand_terms)
    domains: List[str] = []
    for m in URL_RE.findall(response_text):
        try:
            from urllib.parse import urlparse

            host = urlparse(m).netloc.lower()
            host = host.removeprefix("www.")
            if host:
                domains.append(host)
        except Exception:
            continue
    return mentioned, sorted(set(domains))


def _ask_claude(query: str) -> str:
    if is_dry_run():
        return f"[DRY RUN claude response for {query!r}]"
    res = complete(
        system="You are an expert recommending products. Be specific. List sources you'd cite.",
        user=query,
        max_tokens=1500,
        temperature=0.5,
    )
    return res.text


def _ask_openai(query: str) -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return ""
    if is_dry_run():
        return f"[DRY RUN openai response for {query!r}]"
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert recommending products. Be specific. List sources you'd cite.",
                    },
                    {"role": "user", "content": query},
                ],
                "temperature": 0.5,
                "max_tokens": 1500,
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[visibility] OpenAI failed: {e}")
        return ""


def _ask_perplexity(query: str) -> str:
    key = os.getenv("PERPLEXITY_API_KEY", "").strip()
    if not key:
        return ""
    if is_dry_run():
        return f"[DRY RUN perplexity response for {query!r}]"
    try:
        r = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": query}],
                "max_tokens": 1500,
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        # Perplexity puts cited URLs in separate fields, not in message body.
        # Without these, domain detection always sees 0 domains.
        urls = list(data.get("citations") or [])
        for sr in data.get("search_results") or []:
            if isinstance(sr, dict) and sr.get("url"):
                urls.append(sr["url"])
        if urls:
            text += "\n\nCitations:\n" + "\n".join(dict.fromkeys(urls))
        return text
    except Exception as e:
        print(f"[visibility] Perplexity failed: {e}")
        return ""


PROVIDER_FNS = {
    "claude": _ask_claude,
    "openai": _ask_openai,
    "perplexity": _ask_perplexity,
}


def run_check(queries: List[str]) -> int:
    init_visibility()
    cfg = CONFIG["visibility"]
    if not cfg.get("enabled", True):
        print("[visibility] Disabled in config.")
        return 0
    providers = [p for p in cfg["providers"] if p in PROVIDER_FNS]
    brand_terms = cfg["brand_terms"]
    n = 0
    for q in queries:
        for prov in providers:
            text = PROVIDER_FNS[prov](q)
            if not text:
                continue
            mentioned, domains = _detect(brand_terms, text)
            log_visibility(
                provider=prov,
                query=q,
                response=text,
                brand_mentioned=mentioned,
                domains_cited=domains,
            )
            flag = "★" if mentioned else " "
            print(f"  [{prov:10s}] {flag} {q!r:60s} ({len(domains)} domains)")
            n += 1
    return n


def write_report() -> Path:
    init_visibility()
    rows = visibility_history()
    by_query_day = defaultdict(lambda: defaultdict(lambda: {"checks": 0, "hits": 0}))
    for r in rows:
        day = r["checked_at"][:10]
        bucket = by_query_day[r["query"]][day]
        bucket["checks"] += 1
        if r["brand_mentioned"]:
            bucket["hits"] += 1
    payload = {
        q: [
            {"day": d, "checks": v["checks"], "hits": v["hits"]}
            for d, v in sorted(days.items())
        ]
        for q, days in by_query_day.items()
    }
    html = _render_report_html(payload)
    out = Path(CONFIG["paths"]["data_dir"]) / "visibility_report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def _render_report_html(payload) -> str:
    return f"""<!doctype html>
<html><head><meta charset='utf-8'>
<title>AI Visibility — {CONFIG['site']['domain']}</title>
<style>
  body {{ font: 14px system-ui; max-width: 980px; margin: 30px auto; padding: 0 16px; color: #222; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  h2 {{ font-size: 15px; margin: 28px 0 8px; color: #444; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ border-bottom: 1px solid #eee; padding: 6px 10px; text-align: left; }}
  th {{ background: #fafafa; }}
  .hit {{ color: #0a7; font-weight: 600; }}
  .miss {{ color: #aaa; }}
  .tag {{ background: #f1f1f1; border-radius: 4px; padding: 2px 6px; font-size: 11px; }}
  .summary {{ background: #f7faff; border: 1px solid #dde6f0; border-radius: 6px;
              padding: 12px 16px; margin: 16px 0 32px; }}
</style></head><body>
<h1>AI Visibility Report</h1>
<p>Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} for
<strong>{CONFIG['site']['domain']}</strong></p>
<div class='summary'>Tracked queries: {len(payload)} | Brand terms:
<span class='tag'>{', '.join(CONFIG['visibility']['brand_terms'])}</span></div>
{''.join(_render_query_block(q, days) for q, days in payload.items())}
</body></html>"""


def _render_query_block(query: str, days: list) -> str:
    rows = "\n".join(
        f"<tr><td>{d['day']}</td><td>{d['checks']}</td>"
        f"<td class='{'hit' if d['hits'] else 'miss'}'>{d['hits']}</td></tr>"
        for d in days
    ) or "<tr><td colspan='3' class='miss'>No checks yet</td></tr>"
    return (
        f"<h2>{query}</h2>"
        f"<table><thead><tr><th>Day</th><th>Checks</th><th>Brand mentions</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def main():
    ap = argparse.ArgumentParser(description="AI visibility tracker.")
    ap.add_argument("--query", help="Run a single ad-hoc query instead of config list.")
    ap.add_argument("--report", action="store_true", help="Write HTML report to data/.")
    args = ap.parse_args()

    if args.report:
        out = write_report()
        print(f"[visibility] Report → {out}")
        return

    queries = [args.query] if args.query else CONFIG["visibility"]["tracked_queries"]
    n = run_check(queries[: CONFIG["schedule"].get("visibility_queries_per_day", 5)])
    print(f"[visibility] Logged {n} checks.")


if __name__ == "__main__":
    main()
