#!/usr/bin/env python3
"""Audit portfolio harness coverage across all projects."""
from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR))

from detect import detect_project, list_portfolio_projects, load_portfolio  # noqa: E402


def timeout_handler(signum, frame):
    print("ERROR: Script timed out after 120 seconds", file=sys.stderr)
    sys.exit(1)


# Set a 300-second timeout for the entire script
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(300)

CHECKS = [
    ("agents_md", "AGENTS.md", 2),
    ("cursor_rules", ".cursor/rules", 2),
    ("git", ".git", 1),
]


def score_project(project_root: Path, portfolio: dict) -> dict:
    info = detect_project(project_root, portfolio)
    if info.get("skip_harness"):
        return {
            "name": info["name"],
            "slug": info["slug"],
            "archetype": info["archetype"],
            "skipped": True,
            "score": None,
            "max_score": None,
            "checks": [],
        }

    checks = []
    earned = 0
    max_score = 0
    markers = info["markers"]

    for key, label, points in CHECKS:
        max_score += points
        passed = bool(markers.get(key))
        if passed:
            earned += points
        checks.append({"id": key, "label": label, "points": points, "pass": passed})

    # Harness marker inside AGENTS.md
    agents = project_root / "AGENTS.md"
    harness_marker = False
    if agents.exists():
        try:
            harness_marker = "Portfolio Agent Harness" in agents.read_text(encoding="utf-8")
        except OSError:
            pass
    max_score += 2
    if harness_marker:
        earned += 2
    checks.append({"id": "harness_marker", "label": "Portfolio harness block in AGENTS.md", "points": 2, "pass": harness_marker})

    return {
        "name": info["name"],
        "slug": info["slug"],
        "path": info["path"],
        "archetype": info["archetype"],
        "skipped": False,
        "score": earned,
        "max_score": max_score,
        "pct": round(100 * earned / max_score) if max_score else 0,
        "checks": checks,
    }


def format_text(report: dict) -> str:
    lines = [
        f"Portfolio Harness Audit — {report['portfolio_root']}",
        f"Projects: {report['totals']['projects']} | Scored: {report['totals']['scored']} | Skipped: {report['totals']['skipped']}",
        f"Average coverage: {report['totals']['avg_pct']}%",
        "",
    ]
    for item in sorted(report["projects"], key=lambda x: (-1 if x.get("skipped") else x.get("pct", 0), x["name"])):
        if item.get("skipped"):
            lines.append(f"  SKIP  {item['name']:<32} ({item['archetype']})")
            continue
        filled = item["pct"] // 10
        bar = "#" * filled + "-" * (10 - filled)
        lines.append(f"  {item['pct']:3d}% {bar} {item['name']:<28} {item['archetype']}")
        missing = [c["label"] for c in item["checks"] if not c["pass"]]
        if missing:
            lines.append(f"        missing: {', '.join(missing)}")
    lines.append("")
    low = [p for p in report["projects"] if not p.get("skipped") and p.get("pct", 100) < 80]
    if low:
        lines.append("Install harness on low-coverage projects:")
        lines.append("  python3 agentic-os/harness/install.py --all")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit portfolio harness coverage")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--project", type=str, help="Audit single project only")
    args = parser.parse_args()

    portfolio = load_portfolio()
    if args.project:
        roots = [Path(args.project).resolve()]
        portfolio_root = str(roots[0].parent)
    else:
        roots = list_portfolio_projects(portfolio)
        portfolio_root = portfolio["paths"]["portfolio_root_windows"]

    projects = [score_project(r, portfolio) for r in roots]
    scored = [p for p in projects if not p.get("skipped")]
    avg = round(sum(p["pct"] for p in scored) / len(scored)) if scored else 0

    report = {
        "portfolio_root": portfolio_root,
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "totals": {
            "projects": len(projects),
            "scored": len(scored),
            "skipped": len(projects) - len(scored),
            "avg_pct": avg,
        },
        "projects": projects,
    }

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(format_text(report))


if __name__ == "__main__":
    main()
