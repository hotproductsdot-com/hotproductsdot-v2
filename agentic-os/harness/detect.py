#!/usr/bin/env python3
"""Detect project archetype and build commands for portfolio harness."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent
PORTFOLIO_FILE = HARNESS_DIR / "portfolio.yaml"


def load_portfolio() -> dict:
    return yaml.safe_load(PORTFOLIO_FILE.read_text(encoding="utf-8")) or {}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9._-]", "-", name.lower()).strip("-") or "project"


def _has_marker(root: Path, marker: str) -> bool:
    return (root / marker).exists()


def detect_archetype(root: Path, portfolio: dict | None = None) -> str:
    portfolio = portfolio or load_portfolio()
    slug = _slug(root.name)
    override = (portfolio.get("projects") or {}).get(slug, {})
    if override.get("archetype"):
        return override["archetype"]

    for name, spec in (portfolio.get("archetypes") or {}).items():
        if name == "generic":
            continue
        markers = spec.get("markers") or []
        if not markers:
            continue
        mode = (spec.get("match") or "any").lower()
        if mode == "all":
            matched = all(_has_marker(root, m) for m in markers)
        else:
            matched = any(_has_marker(root, m) for m in markers)
        if matched:
            return name
    return "generic"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _package_scripts(root: Path) -> dict:
    for rel in ("package.json", "site/package.json"):
        pkg = root / rel
        if pkg.exists():
            return _read_json(pkg).get("scripts") or {}
    return {}


_SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "site", "dist", "build"}


def _walk_limited(root: Path, filename: str, limit: int = 4) -> list[str]:
    import stat
    hits: list[str] = []
    # Stack stores tuples of (path, depth)
    stack = [(root, 0)]
    max_depth = 3  # Limit recursion depth to prevent hangs from symlink loops
    while stack and len(hits) < limit:
        current, depth = stack.pop()
        if depth > max_depth:
            continue
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.name in _SKIP_DIRS:
                continue
            try:
                # Use lstat to avoid following symlinks
                st = entry.lstat()
                if stat.S_ISREG(st.st_mode) and entry.name == filename:
                    hits.append(str(entry.relative_to(root)).replace("\\", "/"))
                    if len(hits) >= limit:
                        break
                elif stat.S_ISDIR(st.st_mode):
                    stack.append((entry, depth + 1))
            except (OSError, PermissionError):
                # Skip entries we can't stat
                continue
    return hits


def _python_entrypoints(root: Path) -> list[str]:
    hits: list[str] = []
    for rel in ("requirements.txt", "pyproject.toml"):
        if (root / rel).exists():
            hits.append(rel)
    for name in ("run_daily.py", "main.py", "app.py", "server.py"):
        hits.extend(_walk_limited(root, name, limit=4 - len(hits)))
        if len(hits) >= 4:
            return hits[:4]
    return hits


def detect_project(root: Path, portfolio: dict | None = None) -> dict:
    portfolio = portfolio or load_portfolio()
    root = root.resolve()
    slug = _slug(root.name)
    override = (portfolio.get("projects") or {}).get(slug, {})
    archetype = detect_archetype(root, portfolio)
    scripts = _package_scripts(root)

    build_cmd = None
    dev_cmd = None
    test_cmd = None
    if scripts:
        build_cmd = scripts.get("build")
        dev_cmd = scripts.get("dev") or scripts.get("start")
        test_cmd = scripts.get("test") or scripts.get("test:run")

    if archetype == "fullstack-mixed":
        build_cmd = build_cmd or "cd site && npm install && npm run build"
        dev_cmd = dev_cmd or "cd site && npm run dev"
    elif archetype == "nextjs-vercel":
        if (root / "site/package.json").exists():
            build_cmd = build_cmd or "cd site && npm run build"
            dev_cmd = dev_cmd or "cd site && npm run dev"
        else:
            build_cmd = build_cmd or "npm run build"
            dev_cmd = dev_cmd or "npm run dev"
    elif archetype == "node-monorepo":
        build_cmd = build_cmd or "pnpm build"
        dev_cmd = dev_cmd or "pnpm dev"
        test_cmd = test_cmd or "pnpm test:run"
    elif archetype == "python-app":
        py = _python_entrypoints(root)
        if py and not any(x.endswith(".py") for x in py[:1]):
            pass
        elif py:
            main_py = next((x for x in py if x.endswith(".py")), None)
            if main_py:
                dev_cmd = dev_cmd or f"python {main_py}"

    markers = {}
    for marker_name, marker_path in [
        ("package_json", "package.json"),
        ("site_package_json", "site/package.json"),
        ("requirements_txt", "requirements.txt"),
        ("pyproject_toml", "pyproject.toml"),
        ("pnpm_workspace", "pnpm-workspace.yaml"),
        ("agents_md", "AGENTS.md"),
        ("claude_md", "CLAUDE.md"),
        ("cursor_rules", ".cursor/rules"),
        ("git", ".git"),
    ]:
        try:
            markers[marker_name] = (root / marker_path).exists()
        except OSError:
            markers[marker_name] = False

    # Special case for next_config
    try:
        markers["next_config"] = any((root / f).exists() for f in ("next.config.ts", "next.config.js", "site/next.config.ts"))
    except OSError:
        markers["next_config"] = False

    # Skip expensive directory scanning for:
    # 1. Projects marked to skip harness
    # 2. Node.js projects (unlikely to have Python entrypoints)
    if override.get("skip_harness") or markers.get("package_json") or markers.get("site_package_json"):
        python_entrypoints = []
    else:
        python_entrypoints = _python_entrypoints(root)

    return {
        "slug": slug,
        "name": root.name,
        "path": str(root),
        "archetype": archetype,
        "primary": bool(override.get("primary")),
        "skip_harness": bool(override.get("skip_harness")),
        "notes": override.get("notes", ""),
        "markers": markers,
        "commands": {
            "build": build_cmd,
            "dev": dev_cmd,
            "test": test_cmd,
        },
        "python_entrypoints": python_entrypoints,
    }


def list_portfolio_projects(portfolio: dict | None = None) -> list[Path]:
    portfolio = portfolio or load_portfolio()
    root = Path(portfolio["paths"]["portfolio_root_windows"])
    if not root.exists():
        root = Path(portfolio["paths"]["portfolio_root_wsl"])
    if not root.exists():
        return []

    skip_names = {
        ".git", "node_modules", "__MACOSX", "ARCHIVED REPOS",
        "venv", ".venv", ".claude", ".omc", ".remember", ".ruff_cache",
    }
    projects = []
    try:
        entries = sorted(root.iterdir())
    except (OSError, PermissionError) as e:
        import sys
        print(f"Warning: Failed to list {root}: {e}", file=sys.stderr)
        return []

    for entry in entries:
        try:
            import stat
            # Use lstat to avoid following symlinks
            st = entry.lstat()
            if not stat.S_ISDIR(st.st_mode):
                continue
            if entry.name in skip_names or entry.name.startswith("."):
                continue
            projects.append(entry)
        except (OSError, PermissionError):
            # Skip entries we can't access
            continue
    return projects


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps(detect_project(target), indent=2))
