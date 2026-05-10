"""In-process job runner with live log streaming.

Each job:
  - has a uuid
  - runs a subprocess in the repo root (or a custom cwd)
  - streams stdout+stderr line-by-line into an in-memory ring buffer + on-disk log
  - exposes a thread-safe queue per subscriber for SSE streaming

No external deps. Stdlib only.
"""

from __future__ import annotations

import os
import queue
import shlex
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Job:
    id: str
    activity_id: str
    title: str
    cmd: list[str]
    cwd: str
    started_at: float
    status: str = "running"  # running | success | failed | killed
    finished_at: float | None = None
    exit_code: int | None = None
    log_path: Path | None = None
    process: subprocess.Popen | None = field(default=None, repr=False)
    buffer: list[str] = field(default_factory=list, repr=False)
    subscribers: list[queue.Queue] = field(default_factory=list, repr=False)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    MAX_BUFFER_LINES = 5000

    def append_line(self, line: str) -> None:
        with self.lock:
            self.buffer.append(line)
            if len(self.buffer) > self.MAX_BUFFER_LINES:
                self.buffer = self.buffer[-self.MAX_BUFFER_LINES :]
            for q in list(self.subscribers):
                try:
                    q.put_nowait(line)
                except queue.Full:
                    pass

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "activity_id": self.activity_id,
            "title": self.title,
            "cmd": self.cmd,
            "cwd": self.cwd,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "exit_code": self.exit_code,
            "log_path": str(self.log_path) if self.log_path else None,
            "duration": (self.finished_at or time.time()) - self.started_at,
            "lines": len(self.buffer),
        }


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.order: list[str] = []
        self._lock = threading.Lock()

    def list_jobs(self, limit: int = 50) -> list[dict]:
        with self._lock:
            ids = list(reversed(self.order))[:limit]
            return [self.jobs[i].snapshot() for i in ids if i in self.jobs]

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def start(self, *, activity_id: str, title: str, cmd: list[str], cwd: str = "") -> Job:
        job_id = uuid.uuid4().hex[:12]
        log_path = LOGS_DIR / f"{int(time.time())}-{activity_id}-{job_id}.log"
        run_cwd = REPO_ROOT / cwd if cwd else REPO_ROOT
        job = Job(
            id=job_id,
            activity_id=activity_id,
            title=title,
            cmd=cmd,
            cwd=str(run_cwd),
            started_at=time.time(),
            log_path=log_path,
        )
        with self._lock:
            self.jobs[job_id] = job
            self.order.append(job_id)
        thread = threading.Thread(target=self._run, args=(job, run_cwd), daemon=True)
        thread.start()
        return job

    def stop(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job or job.status != "running" or not job.process:
            return False
        try:
            if os.name == "nt":
                job.process.terminate()
            else:
                os.killpg(os.getpgid(job.process.pid), signal.SIGTERM)
        except Exception:
            try:
                job.process.terminate()
            except Exception:
                return False
        job.status = "killed"
        return True

    def subscribe(self, job_id: str) -> tuple[Job, queue.Queue] | None:
        job = self.jobs.get(job_id)
        if not job:
            return None
        q: queue.Queue = queue.Queue(maxsize=10000)
        with job.lock:
            for line in job.buffer:
                q.put_nowait(line)
            job.subscribers.append(q)
        return job, q

    def unsubscribe(self, job: Job, q: queue.Queue) -> None:
        with job.lock:
            try:
                job.subscribers.remove(q)
            except ValueError:
                pass

    def _run(self, job: Job, run_cwd: Path) -> None:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        # Auto-activate venv if present and not already activated
        venv_bin = REPO_ROOT / "venv" / "bin"
        if venv_bin.exists():
            env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
            env["VIRTUAL_ENV"] = str(REPO_ROOT / "venv")

        header = f"$ {' '.join(shlex.quote(c) for c in job.cmd)}\n"
        header += f"  cwd: {run_cwd}\n  job: {job.id}\n  started: {time.ctime(job.started_at)}\n\n"
        job.append_line(header)

        log_fp = open(job.log_path, "w", buffering=1, encoding="utf-8", errors="replace")
        log_fp.write(header)

        try:
            popen_kwargs: dict = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(run_cwd),
                env=env,
                bufsize=1,
                text=True,
                errors="replace",
            )
            if os.name != "nt":
                popen_kwargs["preexec_fn"] = os.setsid
            proc = subprocess.Popen(job.cmd, **popen_kwargs)
            job.process = proc

            assert proc.stdout is not None
            for raw_line in iter(proc.stdout.readline, ""):
                if not raw_line:
                    break
                job.append_line(raw_line)
                log_fp.write(raw_line)
            proc.stdout.close()
            exit_code = proc.wait()
            job.exit_code = exit_code
            if job.status != "killed":
                job.status = "success" if exit_code == 0 else "failed"
        except FileNotFoundError as e:
            job.append_line(f"\n[ERROR] command not found: {e}\n")
            log_fp.write(f"\n[ERROR] command not found: {e}\n")
            job.status = "failed"
            job.exit_code = 127
        except Exception as e:  # noqa: BLE001
            job.append_line(f"\n[ERROR] {type(e).__name__}: {e}\n")
            log_fp.write(f"\n[ERROR] {type(e).__name__}: {e}\n")
            job.status = "failed"
            job.exit_code = 1
        finally:
            job.finished_at = time.time()
            footer = f"\n--- exit={job.exit_code} status={job.status} duration={job.finished_at - job.started_at:.1f}s ---\n"
            job.append_line(footer)
            log_fp.write(footer)
            log_fp.close()
            for q in list(job.subscribers):
                try:
                    q.put_nowait(None)  # sentinel
                except queue.Full:
                    pass
