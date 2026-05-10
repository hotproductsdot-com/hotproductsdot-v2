"""Git operations for committing generated articles + optional rsync deploy."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional

from .config import CONFIG, REPO_ROOT, is_dry_run


def _run(cmd: List[str], cwd: Optional[Path] = None) -> str:
    if is_dry_run():
        return f"[DRY RUN] {' '.join(cmd)}"
    res = subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    return (res.stdout or "") + (res.stderr or "")


def stage(paths: List[Path]) -> str:
    rel = [str(Path(p).resolve().relative_to(REPO_ROOT)) for p in paths]
    return _run(["git", "add", *rel])


def commit(message: str) -> str:
    # Skip if nothing staged
    if not is_dry_run():
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=str(REPO_ROOT)
        )
        if diff.returncode == 0:
            return "(nothing to commit)"
    return _run(["git", "commit", "-m", message])


def push(branch: str = "main") -> str:
    return _run(["git", "push", "origin", branch])


def deploy_rsync() -> str:
    """Run npm run deploy:rsync from site/. Requires SSH key setup."""
    return _run(
        ["npm", "run", "deploy:rsync"],
        cwd=REPO_ROOT / "site",
    )


def current_branch() -> str:
    if is_dry_run():
        return "main"
    res = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return res.stdout.strip() or "main"
