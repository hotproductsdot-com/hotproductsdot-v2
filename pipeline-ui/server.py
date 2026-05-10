#!/usr/bin/env python3
"""HotProducts visual CI/CD pipeline web UI.

Run:    python pipeline-ui/server.py            # http://localhost:7878
        python pipeline-ui/server.py --port 9000

No external deps. Pure stdlib HTTP server with Server-Sent Events (SSE) for live logs.
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import re
import shlex
import socket
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from jobs import JobManager  # noqa: E402
from pipeline_config import to_dict as stages_to_dict, find_activity  # noqa: E402


STATIC_DIR = HERE / "static"
CSV_PATH = HERE.parent / "products" / "top-1000.csv"
_CSV_LOCK = threading.Lock()

_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")

CSV_FIELDNAMES = [
    "Product Name", "Category", "Price Range", "Review Count",
    "Rating", "BSR", "Affiliate Potential", "Amazon URL",
    "Refreshed Date", "Action Needed",
]


def _catalog_read() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _catalog_write(rows: list[dict]) -> None:
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDNAMES})


def _extract_asin(url: str) -> str:
    m = _ASIN_RE.search(url or "")
    return m.group(1) if m else ""
JOB_MGR = JobManager()


def _build_cmd(activity, params: dict) -> list[str]:
    """Append CLI flags from params onto the activity's base cmd."""
    cmd = list(activity.cmd)
    for p in activity.params:
        val = params.get(p.name, "")
        if p.kind == "bool":
            if val in (True, "true", "True", "1", "on"):
                if p.flag:
                    cmd.append(p.flag)
            continue
        if val == "" or val is None:
            continue
        if p.flag:
            cmd.extend([p.flag, str(val)])
        else:
            cmd.append(str(val))
    return cmd


class Handler(BaseHTTPRequestHandler):
    server_version = "PipelineUI/1.0"

    def log_message(self, format, *args):  # quieter logs
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))

    # ---- helpers ----
    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _serve_static(self, rel: str) -> None:
        rel = rel.lstrip("/")
        if rel == "":
            rel = "index.html"
        path = (STATIC_DIR / rel).resolve()
        if STATIC_DIR.resolve() not in path.parents and path != STATIC_DIR.resolve() / rel:
            self.send_error(403)
            return
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        ctype, _ = mimetypes.guess_type(str(path))
        ctype = ctype or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # ---- routes ----
    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == "/api/stages":
                return self._json(200, {"stages": stages_to_dict()})

            if path == "/api/jobs":
                return self._json(200, {"jobs": JOB_MGR.list_jobs()})

            if path.startswith("/api/jobs/") and path.endswith("/stream"):
                job_id = path.split("/")[3]
                return self._stream_job(job_id)

            if path.startswith("/api/jobs/"):
                job_id = path.split("/")[3]
                job = JOB_MGR.get(job_id)
                if not job:
                    return self._json(404, {"error": "not found"})
                return self._json(200, {"job": job.snapshot()})

            if path == "/api/health":
                return self._json(200, {"ok": True, "ts": time.time()})

            if path == "/api/catalog":
                with _CSV_LOCK:
                    rows = _catalog_read()
                products = []
                for i, r in enumerate(rows):
                    url = r.get("Amazon URL", "")
                    products.append({
                        "idx": i,
                        "name": r.get("Product Name", ""),
                        "category": r.get("Category", ""),
                        "price": r.get("Price Range", ""),
                        "reviews": r.get("Review Count", ""),
                        "rating": r.get("Rating", ""),
                        "bsr": r.get("BSR", ""),
                        "score": r.get("Affiliate Potential", ""),
                        "url": url,
                        "date": r.get("Refreshed Date", ""),
                        "action": r.get("Action Needed", ""),
                        "asin": _extract_asin(url),
                    })
                return self._json(200, {"products": products, "total": len(products)})

            return self._serve_static(path)
        except BrokenPipeError:
            pass
        except Exception:
            traceback.print_exc()
            try:
                self._json(500, {"error": "internal"})
            except Exception:
                pass

    def do_POST(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == "/api/run":
                payload = self._read_json()
                activity_id = payload.get("activity_id")
                params = payload.get("params") or {}
                if not activity_id:
                    return self._json(400, {"error": "activity_id required"})
                activity = find_activity(activity_id)
                if not activity:
                    return self._json(404, {"error": f"unknown activity: {activity_id}"})
                cmd = _build_cmd(activity, params)
                job = JOB_MGR.start(
                    activity_id=activity.id,
                    title=activity.title,
                    cmd=cmd,
                    cwd=activity.cwd,
                )
                return self._json(200, {"job": job.snapshot()})

            if path.startswith("/api/jobs/") and path.endswith("/stop"):
                job_id = path.split("/")[3]
                ok = JOB_MGR.stop(job_id)
                return self._json(200 if ok else 404, {"ok": ok})

            if path == "/api/catalog/delete":
                payload = self._read_json()
                asins = set(payload.get("asins") or [])
                if not asins:
                    return self._json(400, {"error": "asins[] required"})
                with _CSV_LOCK:
                    rows = _catalog_read()
                    kept = [r for r in rows if _extract_asin(r.get("Amazon URL", "")) not in asins]
                    removed = len(rows) - len(kept)
                    _catalog_write(kept)
                return self._json(200, {"removed": removed, "remaining": len(kept)})

            return self._json(404, {"error": "not found"})
        except Exception:
            traceback.print_exc()
            try:
                self._json(500, {"error": "internal"})
            except Exception:
                pass

    # ---- SSE ----
    def _stream_job(self, job_id: str) -> None:
        sub = JOB_MGR.subscribe(job_id)
        if not sub:
            self._json(404, {"error": "not found"})
            return
        job, q = sub
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            last_keepalive = time.time()
            while True:
                try:
                    line = q.get(timeout=1.0)
                except Exception:
                    line = ...  # type: ignore[assignment]
                if line is None:
                    snap = json.dumps(job.snapshot())
                    self.wfile.write(f"event: done\ndata: {snap}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    break
                if line is ...:  # keepalive
                    if time.time() - last_keepalive > 15:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_keepalive = time.time()
                    continue
                last_keepalive = time.time()
                payload = json.dumps({"line": line})
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            JOB_MGR.unsubscribe(job, q)


def find_open_port(start: int) -> int:
    for p in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return start


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7878)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    port = find_open_port(args.port)
    if port != args.port:
        print(f"[pipeline-ui] port {args.port} busy; using {port}")
    httpd = ThreadingHTTPServer((args.host, port), Handler)
    url = f"http://{args.host}:{port}/"
    print("=" * 60)
    print(" HotProducts Pipeline UI")
    print(f" -> {url}")
    print(" Ctrl+C to stop")
    print("=" * 60)
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[pipeline-ui] shutting down")
        httpd.shutdown()


if __name__ == "__main__":
    main()
