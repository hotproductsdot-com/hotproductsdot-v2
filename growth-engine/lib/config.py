"""Loads growth-engine config.yaml + .env. Single source of truth."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

# Repo root contains the canonical .env (already used by other pipelines)
ENGINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ENGINE_DIR.parent

load_dotenv(REPO_ROOT / ".env")
load_dotenv(ENGINE_DIR / ".env", override=False)


def load_config() -> Dict[str, Any]:
    cfg_path = ENGINE_DIR / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Missing {cfg_path}. Copy config.yaml.example.")
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Resolve paths relative to engine dir
    paths = cfg.get("paths", {})
    for key, val in list(paths.items()):
        paths[key] = str((ENGINE_DIR / val).resolve())
    cfg["paths"] = paths
    cfg["_engine_dir"] = str(ENGINE_DIR)
    cfg["_repo_root"] = str(REPO_ROOT)
    return cfg


def is_dry_run() -> bool:
    return os.getenv("GROWTH_ENGINE_DRY_RUN", "").strip() == "1"


def require_env(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise RuntimeError(
            f"Required env var {key} is not set. Add it to {REPO_ROOT / '.env'}."
        )
    return val


CONFIG = load_config()
