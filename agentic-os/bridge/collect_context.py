#!/usr/bin/env python3
"""Collect cross-tool AI context into a shared bridge digest (Claude OS Bridge).

Reads Cursor agent transcripts, Claude Code project metadata, and repo state.
Output: agentic-os/bridge/context/latest.json
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "context"
OUT_FILE = OUT_DIR / "latest.json"

# WSL paths (primary) with Windows fallbacks
CURSOR_TRANSCRIPTS = Path("/mnt/c/Users/cyber/.cursor/projects")
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
OBSIDIAN_VAULT = Path("/mnt/e/GITHUB/Claude-Code-OBVault")
GROWTH_DATA = ROOT / "growth-engine" / "data"


def _mtime_iso(p: Path) -> str | None:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def _read_jsonl_tail(path: Path, max_lines: int = 30) -> list[dict]:
    lines: list[str] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                lines.append(line.rstrip())
                if len(lines) > max_lines * 2:
                    lines = lines[-max_lines:]
    except OSError:
        return []
    out = []
    for line in lines[-max_lines:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _extract_user_queries(records: list[dict]) -> list[str]:
    queries = []
    for rec in records:
        role = rec.get("role") or rec.get("type") or ""
        content = rec.get("content") or rec.get("message") or ""
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") if isinstance(c, dict) else str(c) for c in content
            )
        if role in ("user", "human") and content:
            text = str(content).strip()[:300]
            if text and text not in queries:
                queries.append(text)
    return queries[-5:]


def collect_cursor_sessions(limit: int = 8) -> list[dict]:
    if not CURSOR_TRANSCRIPTS.exists():
        return []
    sessions = []
    for transcript in sorted(
        CURSOR_TRANSCRIPTS.glob("**/agent-transcripts/**/*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]:
        project = transcript.parts[-4] if len(transcript.parts) >= 4 else "unknown"
        records = _read_jsonl_tail(transcript)
        sessions.append({
            "source": "cursor",
            "project": project,
            "file": str(transcript),
            "modified": _mtime_iso(transcript),
            "recent_queries": _extract_user_queries(records),
            "message_count": len(records),
        })
    return sessions


def collect_claude_projects(limit: int = 5) -> list[dict]:
    if not CLAUDE_PROJECTS.exists():
        return []
    projects = []
    for entry in sorted(CLAUDE_PROJECTS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not entry.is_dir():
            continue
        meta = {
            "source": "claude-code",
            "path": str(entry),
            "modified": _mtime_iso(entry),
        }
        for name in (".claude.json", "project.json"):
            cfg = entry / name
            if cfg.exists():
                try:
                    meta["config"] = json.loads(cfg.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass
                break
        projects.append(meta)
        if len(projects) >= limit:
            break
    return projects


def collect_growth_engine_status() -> dict:
    status: dict = {"source": "growth-engine"}
    for name, path in [
        ("published", GROWTH_DATA / "published.json"),
        ("content_plan", GROWTH_DATA / "content_plan.json"),
        ("deals", GROWTH_DATA / "deals.json"),
    ]:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                status[name] = {
                    "modified": _mtime_iso(path),
                    "summary": _summarize_growth(name, data),
                }
            except (json.JSONDecodeError, OSError):
                status[name] = {"error": "unreadable"}
        else:
            status[name] = {"missing": True}
    return status


def _summarize_growth(name: str, data) -> str:
    if name == "published" and isinstance(data, list):
        return f"{len(data)} published articles"
    if name == "content_plan" and isinstance(data, dict):
        queue = data.get("queue") or data.get("articles") or []
        return f"{len(queue)} items in content plan"
    if name == "deals" and isinstance(data, list):
        return f"{len(data)} deals tracked"
    if name == "deals" and isinstance(data, dict):
        deals = data.get("deals") or data.get("items") or []
        return f"{len(deals)} deals tracked"
    return type(data).__name__


def collect_obsidian_recent(limit: int = 5) -> list[dict]:
    if not OBSIDIAN_VAULT.exists():
        return []
    notes = []
    for md in sorted(OBSIDIAN_VAULT.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        notes.append({
            "path": str(md.relative_to(OBSIDIAN_VAULT)),
            "modified": _mtime_iso(md),
            "title": md.stem,
        })
    return notes


def generate_suggestions(sessions: list[dict], growth: dict) -> list[str]:
    suggestions = []
    projects = {s.get("project", "") for s in sessions if s.get("source") == "cursor"}
    if "e-GITHUB-hotproductsdot-v2" in str(projects) or any("hotproduct" in str(s) for s in sessions):
        suggestions.append("Active work on hotproductsdot-v2 — consider running growth-engine dry-run to validate pipeline.")
    deals = growth.get("deals", {})
    if deals.get("missing"):
        suggestions.append("No deals.json yet — run growth-engine/scripts/7_deal_finder.py")
    if len(sessions) > 3:
        suggestions.append(f"{len(sessions)} recent Cursor sessions — review bridge for duplicate effort across tools.")
    if not suggestions:
        suggestions.append("Bridge healthy. No urgent actions detected.")
    return suggestions[:3]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cursor = collect_cursor_sessions()
    claude = collect_claude_projects()
    growth = collect_growth_engine_status()
    obsidian = collect_obsidian_recent()

    digest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bridge_version": "1.0.0",
        "cursor_sessions": cursor,
        "claude_projects": claude,
        "growth_engine": growth,
        "obsidian_recent": obsidian,
        "suggestions": generate_suggestions(cursor, growth),
        "paths": {
            "repo": str(ROOT),
            "obsidian_vault": str(OBSIDIAN_VAULT),
            "hermes_home": str(Path.home() / ".hermes"),
        },
    }
    OUT_FILE.write_text(json.dumps(digest, indent=2), encoding="utf-8")
    print(f"Bridge context written to {OUT_FILE}")
    print(f"  Cursor sessions: {len(cursor)}")
    print(f"  Claude projects: {len(claude)}")
    print(f"  Suggestions: {len(digest['suggestions'])}")


if __name__ == "__main__":
    main()
