"""Agent-side persistence: run traces, pending confirmations, notes, document registry.

Lives in the same SQLite file as tasks (db.DB_PATH) so one file holds all state.
"""
import json

from . import db


def init_store() -> None:
    with db._conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                skill TEXT,
                reply TEXT,
                status TEXT NOT NULL,          -- ok | error | needs_confirmation
                steps TEXT NOT NULL,           -- JSON list of trace steps
                sources TEXT NOT NULL DEFAULT '[]',
                latency_ms INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pending_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                tool TEXT NOT NULL,
                args TEXT NOT NULL,
                summary TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',   -- pending | confirmed | cancelled
                result TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                pages INTEGER,
                chunks INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def _rows(sql: str, args=()) -> list[dict]:
    with db._conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


# ---- runs ----------------------------------------------------------------------

def save_run(message, skill, reply, status, steps, sources, latency_ms) -> int:
    with db._conn() as c:
        return c.execute(
            "INSERT INTO runs (message, skill, reply, status, steps, sources, latency_ms, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (message, skill, reply, status, json.dumps(steps), json.dumps(sources), latency_ms, db._now()),
        ).lastrowid


def _run(r: dict) -> dict:
    r["steps"] = json.loads(r["steps"])
    r["sources"] = json.loads(r["sources"])
    return r


def list_runs(limit: int = 30) -> list[dict]:
    return [_run(r) for r in _rows("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,))]


def get_run(run_id: int) -> dict | None:
    rows = _rows("SELECT * FROM runs WHERE id = ?", (run_id,))
    return _run(rows[0]) if rows else None


# ---- pending confirmations ---------------------------------------------------------

def add_pending(tool: str, args: dict, summary: str) -> dict:
    with db._conn() as c:
        pid = c.execute(
            "INSERT INTO pending_actions (tool, args, summary, created_at) VALUES (?,?,?,?)",
            (tool, json.dumps(args), summary, db._now()),
        ).lastrowid
    return get_pending(pid)


def attach_pending_to_run(pending_ids: list[int], run_id: int) -> None:
    with db._conn() as c:
        c.executemany("UPDATE pending_actions SET run_id = ? WHERE id = ?", [(run_id, p) for p in pending_ids])


def get_pending(pid: int) -> dict | None:
    rows = _rows("SELECT * FROM pending_actions WHERE id = ?", (pid,))
    if not rows:
        return None
    r = rows[0]
    r["args"] = json.loads(r["args"])
    r["result"] = json.loads(r["result"]) if r["result"] else None
    return r


def list_pending() -> list[dict]:
    return [get_pending(r["id"]) for r in _rows("SELECT id FROM pending_actions WHERE status = 'pending' ORDER BY id")]


def resolve_pending(pid: int, status: str, result: dict | None = None) -> dict:
    with db._conn() as c:
        c.execute("UPDATE pending_actions SET status = ?, result = ? WHERE id = ?",
                  (status, json.dumps(result) if result is not None else None, pid))
    return get_pending(pid)


# ---- notes -------------------------------------------------------------------------

def add_note(title: str, body: str) -> dict:
    with db._conn() as c:
        nid = c.execute("INSERT INTO notes (title, body, created_at) VALUES (?,?,?)",
                        (title.strip(), body.strip(), db._now())).lastrowid
    return _rows("SELECT * FROM notes WHERE id = ?", (nid,))[0]


def list_notes() -> list[dict]:
    return _rows("SELECT * FROM notes ORDER BY id DESC")


# ---- documents ---------------------------------------------------------------------

def find_document(sha256: str) -> dict | None:
    rows = _rows("SELECT * FROM documents WHERE sha256 = ?", (sha256,))
    return rows[0] if rows else None


def add_document(name: str, sha256: str, pages: int | None, chunks: int) -> dict:
    with db._conn() as c:
        did = c.execute("INSERT INTO documents (name, sha256, pages, chunks, created_at) VALUES (?,?,?,?,?)",
                        (name, sha256, pages, chunks, db._now())).lastrowid
    return _rows("SELECT * FROM documents WHERE id = ?", (did,))[0]


def list_documents() -> list[dict]:
    return _rows("SELECT * FROM documents ORDER BY id DESC")


def delete_document(doc_id: int) -> dict | None:
    rows = _rows("SELECT * FROM documents WHERE id = ?", (doc_id,))
    if rows:
        with db._conn() as c:
            c.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    return rows[0] if rows else None
