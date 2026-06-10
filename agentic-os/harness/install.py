#!/usr/bin/env python3
"""Install portfolio harness into one or all projects."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
REPO_ROOT = HARNESS_DIR.parents[1]
sys.path.insert(0, str(HARNESS_DIR))

from detect import detect_project, list_portfolio_projects, load_portfolio  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _windows_to_wsl(path: str) -> str:
    m = re.match(r"^([A-Za-z]):\\(.*)$", path.replace("/", "\\"))
    if not m:
        return path.replace("\\", "/")
    drive = m.group(1).lower()
    rest = m.group(2).replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def _wsl_to_windows(path: str) -> str:
    m = re.match(r"^/mnt/([a-z])/(.*)$", path)
    if not m:
        return path
    drive = m.group(1).upper()
    rest = m.group(2).replace("/", "\\")
    return f"{drive}:\\{rest}"


def _render_agents(project: dict, portfolio: dict) -> str:
    base = (HARNESS_DIR / "templates" / "AGENTS.base.md").read_text(encoding="utf-8")
    archetype = project["archetype"]
    overlay_path = HARNESS_DIR / "templates" / "archetypes" / f"{archetype}.md"
    overlay = overlay_path.read_text(encoding="utf-8") if overlay_path.exists() else ""

    rules = portfolio.get("global_rules") or []
    rules_md = "\n".join(f"- {r}" for r in rules)

    cmds = project.get("commands") or {}
    cmd_lines = []
    for key in ("dev", "build", "test"):
        val = cmds.get(key)
        if val:
            cmd_lines.append(f"```bash\n{val}\n```")
    if project.get("python_entrypoints"):
        cmd_lines.append("**Python entrypoints:** " + ", ".join(f"`{p}`" for p in project["python_entrypoints"][:4]))
    commands_section = "\n\n".join(cmd_lines) if cmd_lines else "_No standard commands detected — check README._"

    if archetype == "node-monorepo":
        verify = "```bash\npnpm -r typecheck\npnpm test:run\npnpm build\n```"
    elif archetype in ("nextjs-vercel", "fullstack-mixed", "node-app"):
        verify = "```bash\nnpm run build\n# npm test — if defined\n```"
    elif archetype == "python-app":
        verify = "_Run the project's test/lint commands if present; otherwise smoke-test the main script._"
    else:
        verify = "_Run whatever build/test commands exist in the repo before claiming done._"

    notes = project.get("notes", "").strip()
    notes_line = f"- **Notes:** {notes}" if notes else ""

    path = project["path"]
    replacements = {
        "{{PROJECT_NAME}}": project["name"],
        "{{ARCHETYPE}}": archetype,
        "{{PATH_WSL}}": _windows_to_wsl(path) if ":" in path else path,
        "{{PATH_WINDOWS}}": _wsl_to_windows(path) if path.startswith("/mnt/") else path,
        "{{NOTES_LINE}}": notes_line,
        "{{OBSIDIAN_VAULT}}": portfolio["paths"]["obsidian_vault"],
        "{{GLOBAL_RULES}}": rules_md,
        "{{COMMANDS_SECTION}}": commands_section,
        "{{VERIFY_SECTION}}": verify,
    }
    for token, value in replacements.items():
        base = base.replace(token, value)
    return base.rstrip() + "\n\n" + overlay.strip() + "\n"


def _write_agents(path: Path, content: str, merge: bool, dry_run: bool) -> str:
    if path.exists() and merge:
        existing = path.read_text(encoding="utf-8")
        marker = "<!-- PORTFOLIO-HARNESS:START -->"
        end = "<!-- PORTFOLIO-HARNESS:END -->"
        block = f"{marker}\n{content}\n{end}"
        if marker in existing:
            new = re.sub(
                rf"{re.escape(marker)}.*?{re.escape(end)}",
                block,
                existing,
                flags=re.DOTALL,
            )
        else:
            new = existing.rstrip() + "\n\n" + block + "\n"
        action = "merged"
    else:
        new = content
        action = "replaced" if path.exists() else "created"
    if not dry_run:
        path.write_text(new, encoding="utf-8")
    return action


def _install_cursor_rule(project_root: Path, dry_run: bool) -> str:
    src = HARNESS_DIR / "templates" / "cursor" / "portfolio-core.mdc"
    dest_dir = project_root / ".cursor" / "rules"
    dest = dest_dir / "portfolio-core.mdc"
    if dry_run:
        return "would install" if not dest.exists() else "would refresh"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return "installed"


def _register_mission_control(project: dict, dry_run: bool) -> str:
    registry_path = REPO_ROOT / "agentic-os" / "mission-control" / "data" / "projects.json"
    if not registry_path.parent.exists():
        return "skipped (no mission-control)"

    data = {"projects": [], "updated_at": _now()}
    if registry_path.exists():
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    projects = data.get("projects") or []
    slug = project["slug"]
    entry = {
        "id": slug,
        "name": project["name"],
        "url": "",
        "path": project["path"],
        "branch": "",
        "imported_at": _now(),
        "primary": project.get("primary", False),
        "source": "harness",
        "archetype": project["archetype"],
    }
    replaced = False
    for i, p in enumerate(projects):
        if p.get("id") == slug:
            if p.get("primary"):
                entry["primary"] = True
            projects[i] = {**p, **entry}
            replaced = True
            break
    if not replaced:
        projects.append(entry)
    data["projects"] = projects
    data["updated_at"] = _now()
    if not dry_run:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return "registered" if not replaced else "updated"


def install_project(
    project_root: Path,
    *,
    merge: bool = False,
    dry_run: bool = False,
    skip_cursor: bool = False,
    skip_registry: bool = False,
) -> dict:
    portfolio = load_portfolio()
    info = detect_project(project_root, portfolio)
    if info.get("skip_harness"):
        return {"ok": True, "skipped": True, "reason": "skip_harness", "project": info}

    agents_path = project_root / "AGENTS.md"
    agents_content = _render_agents(info, portfolio)
    agents_action = _write_agents(agents_path, agents_content, merge=merge, dry_run=dry_run)

    cursor_action = "skipped"
    if not skip_cursor:
        cursor_action = _install_cursor_rule(project_root, dry_run=dry_run)

    registry_action = "skipped"
    if not skip_registry and info.get("primary"):
        registry_action = _register_mission_control(info, dry_run=dry_run)
    elif not skip_registry:
        registry_action = _register_mission_control(info, dry_run=dry_run)

    return {
        "ok": True,
        "dry_run": dry_run,
        "project": info,
        "agents": agents_action,
        "cursor_rule": cursor_action,
        "registry": registry_action,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Install portfolio harness into project(s)")
    parser.add_argument("--project", type=str, help="Project path (default: cwd)")
    parser.add_argument("--all", action="store_true", help="Install across entire portfolio")
    parser.add_argument("--merge", action="store_true", help="Merge into existing AGENTS.md")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--skip-cursor", action="store_true")
    parser.add_argument("--skip-registry", action="store_true")
    args = parser.parse_args()

    targets: list[Path] = []
    if args.all:
        targets = list_portfolio_projects()
    elif args.project:
        targets = [Path(args.project).resolve()]
    else:
        targets = [Path.cwd().resolve()]

    results = []
    for target in targets:
        if not target.is_dir():
            print(f"SKIP {target} — not a directory", file=sys.stderr)
            continue
        result = install_project(
            target,
            merge=args.merge,
            dry_run=args.dry_run,
            skip_cursor=args.skip_cursor,
            skip_registry=args.skip_registry,
        )
        results.append(result)
        info = result["project"]
        if result.get("skipped"):
            print(f"SKIP {info['name']} — marked skip_harness")
            continue
        prefix = "[dry-run] " if args.dry_run else ""
        print(
            f"{prefix}OK {info['name']} ({info['archetype']}) "
            f"agents={result['agents']} cursor={result['cursor_rule']} registry={result['registry']}"
        )

    if args.all:
        ok = sum(1 for r in results if r.get("ok") and not r.get("skipped"))
        skip = sum(1 for r in results if r.get("skipped"))
        print(f"\nDone: {ok} installed, {skip} skipped, {len(results)} total")


if __name__ == "__main__":
    main()
