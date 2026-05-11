"""Post the most recently published article(s) to the Facebook Page.

Reads data/published.json for entries logged within the last LOOKBACK_MINUTES,
loads each article's JSON from its stored path, then calls facebook.post_link().

Usage:
    python scripts/6_facebook_post.py
    python scripts/6_facebook_post.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.config import CONFIG  # noqa: E402
from lib.facebook import post_link  # noqa: E402

SITE_URL = f"https://{CONFIG['site']['domain']}"
LOOKBACK_MINUTES = 30


def _recent_log_entries() -> List[Dict[str, Any]]:
    path = Path(CONFIG["paths"]["published_log"])
    if not path.exists():
        return []
    try:
        entries: List[Dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)
    recent = []
    for entry in entries:
        try:
            ts = datetime.fromisoformat(entry.get("loggedAt", "").replace("Z", "+00:00"))
            if ts >= cutoff:
                recent.append(entry)
        except Exception:
            pass
    return recent


def _load_article(path_str: str) -> Dict[str, Any]:
    try:
        return json.loads(Path(path_str).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _format_date(date_str: str) -> str:
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime(f"%B {dt.day}, %Y")
    except Exception:
        return date_str


def _build_post(article: Dict[str, Any], slug: str) -> tuple[str, str]:
    title = article.get("title") or slug
    description = article.get("description", "")
    published_at = article.get("publishedAt", "")

    parts: List[str] = [f"📝 {title}"]
    if published_at:
        parts.append(_format_date(published_at))
    if description:
        parts += ["", description]
    parts += ["", "👉 Read the full guide:"]

    return "\n".join(parts), f"{SITE_URL}/guides/{slug}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Post recent articles to Facebook.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        os.environ["GROWTH_ENGINE_DRY_RUN"] = "1"

    entries = _recent_log_entries()
    if not entries:
        print(f"[facebook] No articles published in the last {LOOKBACK_MINUTES} min — skipping.")
        return

    for entry in entries:
        slug = entry.get("slug") or ""
        article = _load_article(entry.get("path") or "")
        title = article.get("title") or entry.get("title") or slug

        print(f"[facebook] Posting: {title}")
        message, link = _build_post(article, slug)
        try:
            result = post_link(message=message, link=link)
            print(f"[facebook] Posted → id={result.get('id')}")
        except Exception as exc:
            print(f"[facebook] ERROR: {exc}")


if __name__ == "__main__":
    main()
