"""Project registry and git import for Mission Control."""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTIC = ROOT / "agentic-os"
PROJECTS_DIR = AGENTIC / "projects"
REGISTRY_FILE = Path(__file__).resolve().parent / "data" / "projects.json"

ALLOWED_URL = re.compile(
    r"^(https://(github\.com|gitlab\.com|bitbucket\.org)/[\w.\-/]+(\.git)?"
    r"|git@(github\.com|gitlab\.com|bitbucket\.org):[\w.\-/]+(\.git)?)$",
    re.I,
)
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_from_url(url: str) -> str:
    clean = url.rstrip("/").removesuffix(".git")
    if ":" in clean and "@" in clean and not clean.startswith("http"):
        name = clean.split(":")[-1]
    else:
        name = clean.split("/")[-1]
    slug = re.sub(r"[^a-z0-9._-]", "-", name.lower()).strip("-")
    return slug or "project"


def load_registry() -> dict:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if REGISTRY_FILE.exists():
        try:
            data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            if data.get("projects"):
                return data
        except json.JSONDecodeError:
            pass
    return _seed_registry()


def _seed_registry() -> dict:
    primary = {
        "id": "hotproductsdot-v2",
        "name": "hotproductsdot-v2",
        "url": "",
        "path": str(ROOT),
        "branch": _git_branch(ROOT),
        "imported_at": _now(),
        "primary": True,
        "source": "local",
    }
    data = {"projects": [primary], "updated_at": _now()}
    save_registry(data)
    return data


def save_registry(data: dict) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    REGISTRY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _run_git(args: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
        )
        out = (r.stdout or r.stderr or "").strip()
        return r.returncode, out
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return 1, str(e)


def _git_branch(path: Path) -> str:
    code, out = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], path, timeout=5)
    return out if code == 0 else "unknown"


def _git_info(path: Path) -> dict:
    info: dict = {"branch": _git_branch(path)}
    code, commit = _run_git(["log", "-1", "--format=%h %s (%cr)"], path, timeout=5)
    info["last_commit"] = commit if code == 0 else ""
    code, dirty = _run_git(["status", "--porcelain"], path, timeout=5)
    info["dirty"] = bool(dirty.strip()) if code == 0 else False
    code, remote = _run_git(["remote", "get-url", "origin"], path, timeout=5)
    info["remote"] = remote if code == 0 else ""
    return info


def enrich_project(p: dict) -> dict:
    path = Path(p.get("path", ""))
    out = dict(p)
    out["exists"] = path.is_dir()
    if path.is_dir() and (path / ".git").exists():
        out["git"] = _git_info(path)
    else:
        out["git"] = {"branch": p.get("branch", ""), "last_commit": "", "dirty": False, "remote": p.get("url", "")}
    return out


def list_projects() -> list[dict]:
    data = load_registry()
    return [enrich_project(p) for p in data.get("projects", [])]


def import_repository(url: str, branch: str | None = None, name: str | None = None) -> dict:
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "Repository URL is required"}
    if not ALLOWED_URL.match(url):
        return {"ok": False, "error": "URL must be a GitHub, GitLab, or Bitbucket HTTPS/SSH git URL"}

    slug = _slug_from_url(url)
    if name:
        slug = re.sub(r"[^a-z0-9._-]", "-", name.lower().strip()).strip("-") or slug
    if not SLUG_RE.match(slug):
        return {"ok": False, "error": "Invalid project name"}

    data = load_registry()
    projects = data.get("projects", [])
    if any(p["id"] == slug or p.get("path", "").endswith(f"/{slug}") for p in projects):
        return {"ok": False, "error": f"Project '{slug}' already exists"}

    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROJECTS_DIR / slug
    if dest.exists():
        return {"ok": False, "error": f"Directory already exists: {dest}"}

    cmd = ["git", "clone", "--depth", "1", url, str(dest)]
    if branch:
        cmd = ["git", "clone", "--depth", "1", "--branch", branch, url, str(dest)]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "git clone failed").strip()
            return {"ok": False, "error": err}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Clone timed out after 5 minutes"}
    except FileNotFoundError:
        return {"ok": False, "error": "git not found — install git in WSL"}

    entry = {
        "id": slug,
        "name": name or slug,
        "url": url,
        "path": str(dest.resolve()),
        "branch": branch or _git_branch(dest),
        "imported_at": _now(),
        "primary": False,
        "source": "import",
    }
    projects.append(entry)
    data["projects"] = projects
    save_registry(data)
    return {"ok": True, "project": enrich_project(entry)}


def register_local(path: str, name: str | None = None) -> dict:
    p = Path(path.strip()).expanduser().resolve()
    if not p.is_dir():
        return {"ok": False, "error": f"Path not found: {p}"}

    slug = re.sub(r"[^a-z0-9._-]", "-", (name or p.name).lower()).strip("-") or "project"
    if not SLUG_RE.match(slug):
        return {"ok": False, "error": "Invalid project name"}

    data = load_registry()
    projects = data.get("projects", [])
    if any(x["id"] == slug for x in projects):
        return {"ok": False, "error": f"Project '{slug}' already registered"}

    code, remote = _run_git(["remote", "get-url", "origin"], p, timeout=5)
    entry = {
        "id": slug,
        "name": name or p.name,
        "url": remote if code == 0 else "",
        "path": str(p),
        "branch": _git_branch(p) if (p / ".git").exists() else "",
        "imported_at": _now(),
        "primary": False,
        "source": "local",
    }
    projects.append(entry)
    data["projects"] = projects
    save_registry(data)
    return {"ok": True, "project": enrich_project(entry)}


def remove_project(project_id: str, delete_files: bool = False) -> dict:
    data = load_registry()
    projects = data.get("projects", [])
    match = next((p for p in projects if p["id"] == project_id), None)
    if not match:
        return {"ok": False, "error": "Project not found"}
    if match.get("primary"):
        return {"ok": False, "error": "Cannot remove the primary project"}

    if delete_files and match.get("source") == "import":
        path = Path(match["path"])
        if path.is_dir() and path.resolve().is_relative_to(PROJECTS_DIR.resolve()):
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    data["projects"] = [p for p in projects if p["id"] != project_id]
    save_registry(data)
    return {"ok": True}


def pull_project(project_id: str) -> dict:
    data = load_registry()
    match = next((p for p in data.get("projects", []) if p["id"] == project_id), None)
    if not match:
        return {"ok": False, "error": "Project not found"}
    path = Path(match["path"])
    if not (path / ".git").exists():
        return {"ok": False, "error": "Not a git repository"}

    code, out = _run_git(["pull", "--ff-only"], path, timeout=120)
    if code != 0:
        return {"ok": False, "error": out}
    return {"ok": True, "output": out, "project": enrich_project(match)}
