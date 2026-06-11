#!/usr/bin/env python3
"""Merge agentic-os Pantheon personalities into ~/.hermes/config.yaml."""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

REPO = Path(__file__).resolve().parents[1]
PERSONALITIES_SRC = REPO / "config" / "personalities.yaml"
HERMES_HOME = Path.home() / ".hermes"
CONFIG = HERMES_HOME / "config.yaml"
SOUL_SRC = REPO / "SOUL.md"
SOUL_DST = HERMES_HOME / "SOUL.md"
SKILLS_SRC = REPO / "skills"
SKILLS_DST = HERMES_HOME / "skills"


def merge_personalities(cfg: dict, personas: dict) -> dict:
    existing = cfg.get("personalities") or {}
    if not isinstance(existing, dict):
        existing = {}
    merged = {**existing, **personas}
    cfg["personalities"] = merged
    return cfg


def copy_skills() -> None:
    if not SKILLS_SRC.exists():
        return
    for skill_dir in SKILLS_SRC.iterdir():
        if not skill_dir.is_dir():
            continue
        dest = SKILLS_DST / skill_dir.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(skill_dir, dest)
        print(f"  skill: {skill_dir.name} → {dest}")


def update_soul(force: bool = False) -> None:
    if not SOUL_SRC.exists():
        return
    if SOUL_DST.exists() and not force:
        current = SOUL_DST.read_text(encoding="utf-8")
        if len(current.strip()) > 200 and "hotproductsdot Agentic OS" not in current:
            print("  SOUL.md: kept existing (use --force-soul to overwrite)")
            return
    shutil.copy2(SOUL_SRC, SOUL_DST)
    print(f"  SOUL.md → {SOUL_DST}")


def main() -> None:
    force_soul = "--force-soul" in sys.argv
    if not PERSONALITIES_SRC.exists():
        print(f"Missing {PERSONALITIES_SRC}", file=sys.stderr)
        sys.exit(1)
    if not CONFIG.exists():
        print(f"Hermes config not found at {CONFIG}. Run: hermes setup", file=sys.stderr)
        sys.exit(1)

    personas = yaml.safe_load(PERSONALITIES_SRC.read_text(encoding="utf-8")) or {}
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}

    backup = CONFIG.with_suffix(f".yaml.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(CONFIG, backup)
    print(f"Backup: {backup}")

    cfg = merge_personalities(cfg, personas)
    CONFIG.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False), encoding="utf-8")
    print(f"Merged {len(personas)} Pantheon personas into {CONFIG}")

    print("Copying skills...")
    copy_skills()
    update_soul(force=force_soul)
    print("Done. Restart Hermes gateway if running: hermes gateway restart")


if __name__ == "__main__":
    main()
