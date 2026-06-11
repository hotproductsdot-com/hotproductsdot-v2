"""Pantheon persona management for Mission Control."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTIC = ROOT / "agentic-os"
PERSONALITIES_FILE = AGENTIC / "config" / "personalities.yaml"
SYNC_SCRIPT = AGENTIC / "scripts" / "sync-pantheon.py"

HEADER = """# Pantheon — Jack Roberts-style delegated personas for Hermes Agent.
# Synced into ~/.hermes/config.yaml → personalities: by scripts/sync-pantheon.py
#
# Invoke: "use Labyrinth to research X" or /personality labyrinth

"""

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.strip().lower()).strip("_")


def load_personalities() -> dict:
    if not yaml or not PERSONALITIES_FILE.exists():
        return {}
    return yaml.safe_load(PERSONALITIES_FILE.read_text(encoding="utf-8")) or {}


def save_personalities(data: dict) -> None:
    if not yaml:
        raise RuntimeError("PyYAML required")
    PERSONALITIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    PERSONALITIES_FILE.write_text(HEADER + body, encoding="utf-8")


def sync_to_hermes() -> dict:
    if not SYNC_SCRIPT.exists():
        return {"ok": False, "error": "sync-pantheon.py not found"}
    try:
        r = subprocess.run(
            ["python3", str(SYNC_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(ROOT),
        )
        out = (r.stdout or r.stderr or "").strip()
        if r.returncode != 0:
            return {"ok": False, "error": out or f"sync exited {r.returncode}"}
        return {"ok": True, "output": out}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "sync timed out"}
    except OSError as e:
        return {"ok": False, "error": str(e)}


def create_persona(
    name: str,
    system_prompt: str,
    tone: str = "",
    style: str = "",
) -> dict:
    if not yaml:
        return {"ok": False, "error": "PyYAML required — pip install pyyaml"}

    slug = _normalize_name(name)
    if not slug or not NAME_RE.match(slug):
        return {
            "ok": False,
            "error": "Name must start with a letter and use only lowercase letters, numbers, underscores (max 32 chars)",
        }

    prompt = (system_prompt or "").strip()
    if len(prompt) < 20:
        return {"ok": False, "error": "System prompt must be at least 20 characters"}

    personas = load_personalities()
    if slug in personas:
        return {"ok": False, "error": f"Persona '{slug}' already exists"}

    entry: dict = {"system_prompt": prompt}
    tone = (tone or "").strip()
    style = (style or "").strip()
    if tone:
        entry["tone"] = tone
    if style:
        entry["style"] = style

    personas[slug] = entry
    save_personalities(personas)
    sync = sync_to_hermes()

    return {
        "ok": True,
        "persona": {"name": slug, **entry},
        "sync": sync,
        "warning": None if sync.get("ok") else sync.get("error"),
    }
