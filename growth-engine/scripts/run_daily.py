"""Daily orchestrator. Runs the full growth pipeline once.

Pipeline:
  1. If content_plan.json is missing or older than refresh_plan_after_days,
     regenerate it (script 1).
  2. Generate `articles_per_day` new articles (script 2).
  3. Run AI visibility check on `visibility_queries_per_day` queries (script 4).
  4. Find `backlink_targets_per_day` new backlink prospects (script 3).
  5. Commit + (optionally) deploy (script 5).
  6. Refresh visibility HTML report.

Usage:
    python scripts/run_daily.py
    python scripts/run_daily.py --skip-publish    # generate only, no commit
    python scripts/run_daily.py --dry-run         # mock all external calls
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.config import CONFIG  # noqa: E402

ENGINE_DIR = Path(__file__).resolve().parents[1]
PY = sys.executable


def _run(script: str, *extra: str) -> int:
    cmd = [PY, str(ENGINE_DIR / "scripts" / script), *extra]
    print(f"\n┌──────── {' '.join(cmd[1:])}")
    res = subprocess.run(cmd, cwd=str(ENGINE_DIR))
    print(f"└──────── exit={res.returncode}")
    return res.returncode


def _plan_is_stale() -> bool:
    plan_path = Path(CONFIG["paths"]["content_plan"])
    if not plan_path.exists():
        return True
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        gen_at = datetime.fromisoformat(plan["generatedAt"].replace("Z", "+00:00"))
    except Exception:
        return True
    age_days = (datetime.now(timezone.utc) - gen_at).days
    return age_days >= CONFIG["schedule"]["refresh_plan_after_days"]


def _pending_count() -> int:
    plan_path = Path(CONFIG["paths"]["content_plan"])
    if not plan_path.exists():
        return 0
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    return sum(1 for b in plan.get("briefs", []) if b.get("status", "pending") == "pending")


def main():
    ap = argparse.ArgumentParser(description="Daily growth-engine orchestrator.")
    ap.add_argument("--skip-publish", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        os.environ["GROWTH_ENGINE_DRY_RUN"] = "1"

    started = datetime.now(timezone.utc)
    print(f"╔══════════════════════════════════════════════════")
    print(f"║ growth-engine daily run · {started.isoformat()}")
    print(f"║ site: {CONFIG['site']['domain']}")
    print(f"╚══════════════════════════════════════════════════")

    # 1. Plan refresh
    if _plan_is_stale() or _pending_count() < CONFIG["schedule"]["articles_per_day"]:
        print("[orchestrator] Plan stale or empty — refreshing.")
        _run("1_keyword_research.py")
    else:
        print(f"[orchestrator] Plan healthy ({_pending_count()} pending briefs).")

    # 2. Articles
    n = CONFIG["schedule"]["articles_per_day"]
    _run("2_generate_article.py", "--count", str(n))

    # 3. AI visibility
    _run("4_ai_visibility.py")
    _run("4_ai_visibility.py", "--report")

    # 4. Backlinks
    _run("3_backlink_finder.py", "--count", str(CONFIG["schedule"]["backlink_targets_per_day"]))

    # 5. Publish
    if args.skip_publish:
        print("[orchestrator] --skip-publish: not committing.")
    else:
        deploy_arg = ["--deploy"] if CONFIG["schedule"].get("auto_deploy") else []
        _run("5_publish.py", *deploy_arg)

    # 6. Facebook
    _run("6_facebook_post.py")

    # 7. Deals
    _run("7_deal_finder.py")

    finished = datetime.now(timezone.utc)
    print(f"\n[orchestrator] Done. Total runtime: {(finished - started).total_seconds():.1f}s")


if __name__ == "__main__":
    main()
