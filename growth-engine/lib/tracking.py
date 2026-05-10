"""SQLite stores for AI visibility logs and backlink outreach pipeline.
Pure stdlib so it runs anywhere.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .config import CONFIG


@contextmanager
def _conn(db_path: str) -> Iterator[sqlite3.Connection]:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --- AI visibility ---------------------------------------------------------

VISIBILITY_DDL = """
CREATE TABLE IF NOT EXISTS visibility_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    brand_mentioned INTEGER NOT NULL,
    citation_count INTEGER NOT NULL,
    domains_cited TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_visibility_query ON visibility_checks (query, checked_at);
"""


def init_visibility() -> None:
    with _conn(CONFIG["paths"]["visibility_db"]) as c:
        c.executescript(VISIBILITY_DDL)


def log_visibility(
    *,
    provider: str,
    query: str,
    response: str,
    brand_mentioned: bool,
    domains_cited: List[str],
) -> None:
    init_visibility()
    with _conn(CONFIG["paths"]["visibility_db"]) as c:
        c.execute(
            """INSERT INTO visibility_checks
               (checked_at, provider, query, response, brand_mentioned, citation_count, domains_cited)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                provider,
                query,
                response,
                1 if brand_mentioned else 0,
                len(domains_cited),
                json.dumps(domains_cited),
            ),
        )


def visibility_history(query: Optional[str] = None) -> List[Dict[str, Any]]:
    init_visibility()
    sql = "SELECT * FROM visibility_checks"
    args: tuple = ()
    if query:
        sql += " WHERE query = ?"
        args = (query,)
    sql += " ORDER BY checked_at DESC LIMIT 1000"
    with _conn(CONFIG["paths"]["visibility_db"]) as c:
        rows = c.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


# --- Backlinks -------------------------------------------------------------

BACKLINKS_DDL = """
CREATE TABLE IF NOT EXISTS backlink_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    found_at TEXT NOT NULL,
    domain TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    title TEXT,
    snippet TEXT,
    relevance_score INTEGER DEFAULT 0,
    contact_email TEXT,
    status TEXT NOT NULL DEFAULT 'prospect',
    last_action_at TEXT,
    notes TEXT,
    outreach_subject TEXT,
    outreach_body TEXT
);
CREATE INDEX IF NOT EXISTS idx_backlink_status ON backlink_targets (status);
"""


def init_backlinks() -> None:
    with _conn(CONFIG["paths"]["backlinks_db"]) as c:
        c.executescript(BACKLINKS_DDL)


def upsert_backlink(
    *,
    domain: str,
    url: str,
    title: str,
    snippet: str,
    relevance_score: int,
    outreach_subject: str = "",
    outreach_body: str = "",
) -> bool:
    """Returns True if newly inserted, False if domain already known."""
    init_backlinks()
    now = datetime.now(timezone.utc).isoformat()
    with _conn(CONFIG["paths"]["backlinks_db"]) as c:
        existing = c.execute(
            "SELECT id FROM backlink_targets WHERE domain = ?", (domain,)
        ).fetchone()
        if existing:
            return False
        c.execute(
            """INSERT INTO backlink_targets
               (found_at, domain, url, title, snippet, relevance_score,
                outreach_subject, outreach_body)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                now,
                domain,
                url,
                title,
                snippet,
                relevance_score,
                outreach_subject,
                outreach_body,
            ),
        )
    return True


def list_backlinks(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    init_backlinks()
    sql = "SELECT * FROM backlink_targets"
    args: tuple = ()
    if status:
        sql += " WHERE status = ?"
        args = (status,)
    sql += " ORDER BY relevance_score DESC, found_at DESC LIMIT ?"
    args = args + (limit,)
    with _conn(CONFIG["paths"]["backlinks_db"]) as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def update_backlink_status(domain: str, status: str, notes: str = "") -> None:
    init_backlinks()
    with _conn(CONFIG["paths"]["backlinks_db"]) as c:
        c.execute(
            """UPDATE backlink_targets
               SET status = ?, notes = COALESCE(notes,'') || ? || char(10),
                   last_action_at = ?
               WHERE domain = ?""",
            (
                status,
                f" [{datetime.now(timezone.utc).isoformat()}] {notes}" if notes else "",
                datetime.now(timezone.utc).isoformat(),
                domain,
            ),
        )


# --- Published log ---------------------------------------------------------

def append_published(record: Dict[str, Any]) -> None:
    path = Path(CONFIG["paths"]["published_log"])
    path.parent.mkdir(parents=True, exist_ok=True)
    log: List[Dict[str, Any]] = []
    if path.exists():
        try:
            log = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            log = []
    record = {**record, "loggedAt": datetime.now(timezone.utc).isoformat()}
    log.append(record)
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
