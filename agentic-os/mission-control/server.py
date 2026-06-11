#!/usr/bin/env python3
"""Mission Control — Jack Roberts-style Agentic OS dashboard with sub-pages."""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
AGENTIC = ROOT / "agentic-os"
BRIDGE = AGENTIC / "bridge" / "context" / "latest.json"
PERSONALITIES = AGENTIC / "config" / "personalities.yaml"
HERMES_HOME = Path.home() / ".hermes"
HERMES_CONFIG = HERMES_HOME / "config.yaml"
HERMES_SOUL = HERMES_HOME / "SOUL.md"
HERMES_USER = HERMES_HOME / "memories" / "USER.md"
HERMES_SKILLS = HERMES_HOME / "skills"
STATIC = Path(__file__).resolve().parent / "static"
CHAT_FILE = Path(__file__).resolve().parent / "data" / "chat.json"
DEFAULT_SKILLS = ["pantheon", "claude-os-bridge", "hotproducts-growth"]
CHAT_LOCK = threading.Lock()

from projects import (  # noqa: E402
    import_repository,
    list_projects,
    pull_project,
    register_local,
    remove_project,
)
from pantheon import create_persona  # noqa: E402

SPA_ROUTES = {
    "/",
    "/command",
    "/hermes",
    "/pantheon",
    "/bridge",
    "/memory",
    "/growth",
    "/cron",
    "/skills",
    "/projects",
}

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def _hermes_env() -> dict:
    env = os.environ.copy()
    home_bin = str(Path.home() / ".local" / "bin")
    env["PATH"] = os.pathsep.join(filter(None, [
        env.get("PATH", ""),
        home_bin,
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
    ]))
    env["HERMES_ACCEPT_HOOKS"] = "1"
    return env


def _run(cmd: list[str], timeout: int = 15, cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env=_hermes_env(), cwd=str(cwd or ROOT),
        )
        return (r.stdout or r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return "Error: command timed out"
    except FileNotFoundError as e:
        return str(e)


def _which(cmd: str) -> bool:
    from shutil import which
    home_bin = Path.home() / ".local" / "bin" / cmd
    if home_bin.exists():
        return True
    extra = os.pathsep.join([str(Path.home() / ".local" / "bin"), "/usr/local/bin", "/usr/bin"])
    return which(cmd, path=extra) is not None


def _read_text(path: Path, limit: int = 12000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:limit] if len(text) > limit else text
    except OSError:
        return ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_chat() -> dict:
    CHAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CHAT_FILE.exists():
        try:
            return json.loads(CHAT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"session_id": None, "messages": [], "updated_at": None}


def save_chat(data: dict) -> None:
    CHAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    CHAT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run_hermes_chat(
    message: str,
    session_id: str | None = None,
    personality: str | None = None,
    skills: list[str] | None = None,
    timeout: int = 600,
) -> dict:
    if not _which("hermes"):
        return {"ok": False, "error": "Hermes not installed or not on PATH", "response": "", "session_id": session_id}

    prompt = message.strip()
    if personality:
        prompt = f"Use Pantheon persona '{personality}': {prompt}"

    cmd = ["hermes", "chat", "-q", prompt, "-Q", "--accept-hooks"]
    if session_id:
        cmd.extend(["--resume", session_id])
    for skill in (skills or DEFAULT_SKILLS):
        cmd.extend(["--skills", skill])

    try:
        started = datetime.now(timezone.utc)
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env=_hermes_env(), cwd=str(ROOT),
        )
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        combined = (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
        new_session = session_id
        response_lines: list[str] = []
        for line in combined.splitlines():
            m = re.match(r"session_id:\s*(\S+)", line.strip())
            if m:
                new_session = m.group(1)
                continue
            if line.startswith("Warning:"):
                continue
            if re.match(r"^[↻🔄].*[Rr]esumed session", line.strip()):
                continue
            response_lines.append(line)
        response = "\n".join(response_lines).strip()
        if not response and r.returncode != 0:
            response = combined.strip() or f"Hermes exited with code {r.returncode}"
        return {
            "ok": r.returncode == 0 and bool(response),
            "response": response,
            "session_id": new_session,
            "duration_s": round(elapsed, 1),
            "error": None if r.returncode == 0 else f"exit code {r.returncode}",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timed out after {timeout}s", "response": "", "session_id": session_id}
    except Exception as e:
        return {"ok": False, "error": str(e), "response": "", "session_id": session_id}


def handle_chat_post(body: dict) -> dict:
    message = (body.get("message") or "").strip()
    if not message:
        return {"ok": False, "error": "Message is required"}

    with CHAT_LOCK:
        chat = load_chat()
        session_id = body.get("session_id") or chat.get("session_id")
        if body.get("new_session"):
            session_id = None

        result = run_hermes_chat(
            message=message,
            session_id=session_id,
            personality=body.get("personality") or None,
            skills=body.get("skills") or DEFAULT_SKILLS,
            timeout=int(body.get("timeout") or 600),
        )

        chat.setdefault("messages", []).append({
            "role": "user",
            "content": message,
            "personality": body.get("personality"),
            "ts": _now(),
        })
        chat["messages"].append({
            "role": "assistant",
            "content": result.get("response") or result.get("error") or "(no response)",
            "ts": _now(),
            "duration_s": result.get("duration_s"),
            "ok": result.get("ok", False),
        })
        if len(chat["messages"]) > 100:
            chat["messages"] = chat["messages"][-100:]
        if result.get("session_id"):
            chat["session_id"] = result["session_id"]
        save_chat(chat)

        return {**result, "history": chat["messages"][-20:]}


def hermes_status() -> dict:
    version = _run(["hermes", "--version"]).split("\n")[0] if _which("hermes") else "not installed"
    gateway = _run(["hermes", "gateway", "status"]) if _which("hermes") else ""
    cron = _run(["hermes", "cron", "list"]) if _which("hermes") else ""
    profiles = _run(["hermes", "profile", "list"]) if _which("hermes") else ""
    mcp = _run(["hermes", "mcp", "list"]) if _which("hermes") else ""
    gateway_up = bool(gateway) and "not running" not in gateway.lower() and "✗" not in gateway
    return {
        "version": version,
        "gateway_running": gateway_up,
        "gateway_raw": gateway,
        "cron_jobs": cron,
        "profiles": profiles,
        "mcp_servers": mcp,
        "home": str(HERMES_HOME),
    }


def load_bridge() -> dict:
    if BRIDGE.exists():
        try:
            return json.loads(BRIDGE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"suggestions": ["Run collect_context.py"], "cursor_sessions": []}


def load_pantheon(full: bool = False) -> dict:
    if not yaml or not PERSONALITIES.exists():
        return {}
    raw = yaml.safe_load(PERSONALITIES.read_text(encoding="utf-8")) or {}
    if full:
        return raw
    return {
        k: {
            "role": (v.get("system_prompt", "")[:120] + "...") if isinstance(v, dict) else str(v)[:120],
            "tone": v.get("tone", "") if isinstance(v, dict) else "",
        }
        for k, v in raw.items()
    }


def load_hermes_model() -> str:
    if not yaml or not HERMES_CONFIG.exists():
        return "unknown"
    try:
        cfg = yaml.safe_load(HERMES_CONFIG.read_text(encoding="utf-8")) or {}
        model = cfg.get("model") or {}
        if isinstance(model, dict):
            return model.get("default") or model.get("model") or str(model)
        return str(model)
    except Exception:
        return "unknown"


def load_skills() -> list[dict]:
    skills = []
    if not HERMES_SKILLS.exists():
        return skills
    for d in sorted(HERMES_SKILLS.iterdir()):
        if not d.is_dir():
            continue
        skill_md = d / "SKILL.md"
        entry = {"name": d.name, "path": str(d), "installed": skill_md.exists()}
        if skill_md.exists():
            text = _read_text(skill_md, 500)
            for line in text.splitlines():
                if line.startswith("description:"):
                    entry["description"] = line.split(":", 1)[1].strip().strip('"')
                    break
        skills.append(entry)
    agentic_skills = AGENTIC / "skills"
    for d in sorted(agentic_skills.iterdir()) if agentic_skills.exists() else []:
        if d.is_dir() and not any(s["name"] == d.name for s in skills):
            skills.append({"name": d.name, "path": str(d), "installed": False, "source": "repo"})
    return skills


def load_memory() -> dict:
    memories_dir = HERMES_HOME / "memories"
    files = []
    if memories_dir.exists():
        for f in sorted(memories_dir.glob("*.md")):
            files.append({"name": f.name, "content": _read_text(f, 8000)})
    return {
        "soul": _read_text(HERMES_SOUL, 8000),
        "user_profile": _read_text(HERMES_USER, 8000),
        "memory_files": files,
        "obsidian_vault": os.environ.get("OBSIDIAN_VAULT_PATH") or "/mnt/e/GITHUB/Claude-Code-OBVault",
    }


def load_growth() -> dict:
    data_dir = ROOT / "growth-engine" / "data"
    out: dict = {"paths": {}}
    for name in ("published.json", "content_plan.json", "deals.json"):
        path = data_dir / name
        key = name.replace(".json", "")
        out["paths"][key] = str(path)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                out[key] = {
                    "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
                    "data": data if isinstance(data, (dict, list)) and len(str(data)) < 5000 else _summarize_growth(key, data),
                }
            except (json.JSONDecodeError, OSError):
                out[key] = {"error": "unreadable"}
        else:
            out[key] = {"missing": True}
    return out


def _summarize_growth(name: str, data) -> dict | list | str:
    if name == "published" and isinstance(data, list):
        return {"count": len(data), "latest": data[-3:] if data else []}
    if name == "content_plan" and isinstance(data, dict):
        queue = data.get("queue") or data.get("articles") or []
        return {"queue_count": len(queue), "preview": queue[:3]}
    if name == "deals":
        items = data if isinstance(data, list) else (data.get("deals") or data.get("items") or [])
        return {"count": len(items), "preview": items[:5]}
    return f"({type(data).__name__})"


def _service_health(url: str, timeout: float = 2.0) -> dict:
    import urllib.request
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"up": resp.status in (200, 301, 302, 304), "status": resp.status}
    except Exception:
        return {"up": False, "status": 0}


def _desktop_health() -> dict:
    try:
        r = subprocess.run(
            ["pgrep", "-f", r"linux-unpacked/Hermes|apps/desktop/release"],
            capture_output=True, text=True, timeout=3,
        )
        up = r.returncode == 0 and bool(r.stdout.strip())
        return {"up": up, "status": "running" if up else "stopped"}
    except Exception:
        return {"up": False, "status": "unknown"}


def launch_hermes_desktop() -> dict:
    if _desktop_health()["up"]:
        return {"ok": True, "message": "Hermes Desktop is already running"}
    log_dir = HERMES_HOME / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "desktop.log"
    release = HERMES_HOME / "hermes-agent/apps/desktop/release/linux-unpacked/Hermes"
    cmd = ["hermes", "desktop", "--skip-build"] if release.exists() else ["hermes", "desktop"]
    env = _hermes_env()
    if not env.get("DISPLAY") and Path("/mnt/wslg/runtime-dir/wayland-0").exists():
        env["DISPLAY"] = ":0"
        env["WAYLAND_DISPLAY"] = "wayland-0"
    try:
        with open(log_path, "a", encoding="utf-8") as log:
            subprocess.Popen(
                cmd,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
                cwd=str(ROOT),
            )
        return {"ok": True, "message": "Launching Hermes Desktop…"}
    except FileNotFoundError:
        return {"ok": False, "error": "hermes CLI not found — install Hermes in WSL first"}
    except OSError as e:
        return {"ok": False, "error": str(e)}


def build_state() -> dict:
    chat = load_chat()
    bridge = load_bridge()
    return {
        "generated_at": _now(),
        "hermes": hermes_status(),
        "model": load_hermes_model(),
        "pantheon": load_pantheon(),
        "pantheon_full": load_pantheon(full=True),
        "pantheon_names": list(load_pantheon(full=True).keys()),
        "bridge": bridge,
        "memory": load_memory(),
        "growth": load_growth(),
        "skills": load_skills(),
        "chat": {
            "session_id": chat.get("session_id"),
            "message_count": len(chat.get("messages") or []),
            "updated_at": chat.get("updated_at"),
        },
        "projects": list_projects(),
        "projects_dir": str(AGENTIC / "projects"),
        "obsidian_vault": os.environ.get("OBSIDIAN_VAULT_PATH") or "/mnt/e/GITHUB/Claude-Code-OBVault",
        "repo": str(ROOT),
        "external_services": {
            "hermes_dashboard": {"type": "web", "url": "http://127.0.0.1:9119", "label": "Hermes Dashboard", **_service_health("http://127.0.0.1:9119")},
            "hermes_desktop": {"type": "desktop", "label": "Hermes Desktop", **_desktop_health()},
            "pipeline_ui": {"type": "web", "url": "http://127.0.0.1:7878", "label": "Pipeline UI", **_service_health("http://127.0.0.1:7878")},
            "deal_poster": {"type": "web", "url": "http://127.0.0.1:5050", "label": "Deal Poster", **_service_health("http://127.0.0.1:5050")},
        },
    }


def _shell_html() -> bytes:
    return (STATIC / "index.html").read_bytes()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str = "text/html") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/api/state":
            self._send(200, json.dumps(build_state(), indent=2).encode(), "application/json")
            return

        if path == "/api/chat":
            chat = load_chat()
            self._send(200, json.dumps(chat, indent=2).encode(), "application/json")
            return

        if path == "/api/projects":
            self._send(200, json.dumps({"projects": list_projects()}, indent=2).encode(), "application/json")
            return

        if path.startswith("/static/"):
            rel = path.removeprefix("/static/")
            fp = STATIC / rel
            if fp.exists() and fp.is_file() and fp.resolve().is_relative_to(STATIC.resolve()):
                self._send(200, fp.read_bytes(), mimetypes_for(fp.suffix))
                return
            self._send(404, b"Not found")
            return

        if path in SPA_ROUTES:
            self._send(200, _shell_html())
            return

        self._send(404, b"Not found")

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            body = self._read_json_body()
        except json.JSONDecodeError:
            self._send(400, json.dumps({"ok": False, "error": "Invalid JSON"}).encode(), "application/json")
            return

        if path == "/api/chat":
            try:
                result = handle_chat_post(body)
                code = 200 if result.get("ok") else 502
                self._send(code, json.dumps(result, indent=2).encode(), "application/json")
            except Exception as e:
                self._send(500, json.dumps({"ok": False, "error": str(e)}).encode(), "application/json")
            return

        if path == "/api/projects/import":
            if body.get("local_path"):
                result = register_local(body["local_path"], body.get("name"))
            else:
                result = import_repository(
                    body.get("url", ""),
                    branch=body.get("branch") or None,
                    name=body.get("name") or None,
                )
            code = 200 if result.get("ok") else 400
            self._send(code, json.dumps(result, indent=2).encode(), "application/json")
            return

        if path.startswith("/api/projects/") and path.endswith("/pull"):
            project_id = path.removeprefix("/api/projects/").removesuffix("/pull")
            result = pull_project(project_id)
            code = 200 if result.get("ok") else 400
            self._send(code, json.dumps(result, indent=2).encode(), "application/json")
            return

        if path == "/api/external/hermes-desktop/launch":
            result = launch_hermes_desktop()
            code = 200 if result.get("ok") else 500
            self._send(code, json.dumps(result, indent=2).encode(), "application/json")
            return

        if path == "/api/pantheon":
            result = create_persona(
                body.get("name", ""),
                body.get("system_prompt", ""),
                tone=body.get("tone") or "",
                style=body.get("style") or "",
            )
            code = 200 if result.get("ok") else 400
            self._send(code, json.dumps(result, indent=2).encode(), "application/json")
            return

        self._send(404, b"Not found")

    def do_DELETE(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/api/chat":
            with CHAT_LOCK:
                save_chat({"session_id": None, "messages": []})
            self._send(200, json.dumps({"ok": True}).encode(), "application/json")
            return

        if path.startswith("/api/projects/"):
            project_id = path.removeprefix("/api/projects/")
            if not project_id or "/" in project_id:
                self._send(400, json.dumps({"ok": False, "error": "Invalid project id"}).encode(), "application/json")
                return
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                body = {}
            result = remove_project(project_id, delete_files=bool(body.get("delete_files")))
            code = 200 if result.get("ok") else 400
            self._send(code, json.dumps(result, indent=2).encode(), "application/json")
            return

        self._send(404, b"Not found")


def mimetypes_for(suffix: str) -> str:
    return {
        ".css": "text/css",
        ".js": "application/javascript",
        ".html": "text/html",
        ".svg": "image/svg+xml",
    }.get(suffix, "application/octet-stream")


def main():
    port = int(os.environ.get("MISSION_CONTROL_PORT", "9120"))
    host = os.environ.get("MISSION_CONTROL_HOST", "127.0.0.1")
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Mission Control → http://{host}:{port}")
    print(f"  Pages: /  /command  /projects  /hermes  /pantheon  /bridge  /memory  /growth  /cron  /skills")
    server.serve_forever()


if __name__ == "__main__":
    main()
