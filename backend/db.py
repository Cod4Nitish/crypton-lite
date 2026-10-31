"""SQLite storage for tasks. Uses the stdlib sqlite3 module, no ORM."""
import os
import re
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("CRYPTON_DB", os.path.join(os.path.dirname(__file__), "..", "crypton.db"))

PRIORITIES = ("low", "medium", "high")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medium',
                due TEXT,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )"""
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["done"] = bool(d["done"])
    return d


def create_task(title: str, priority: str = "medium", due: str | None = None) -> dict:
    title = (title or "").strip()
    if not title:
        raise ValueError("title is required")
    priority = (priority or "medium").lower()
    if priority not in PRIORITIES:
        priority = "medium"
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO tasks (title, priority, due, created_at) VALUES (?, ?, ?, ?)",
            (title, priority, due or None, _now()),
        )
        return _row(c.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone())


def find_duplicate_open(title: str, due: str | None = None) -> dict | None:
    """An open task with the same due date and a near-identical title (case/space/punctuation-insensitive)."""
    from difflib import SequenceMatcher
    norm = _norm_title(title)
    for t in list_tasks("open"):
        if (t["due"] or None) != (due or None):
            continue
        other = _norm_title(t["title"])
        if other == norm or SequenceMatcher(None, other, norm).ratio() >= 0.85:
            return t
    return None


def _norm_title(title: str) -> str:
    return " ".join("".join(ch if ch.isalnum() else " " for ch in (title or "").lower()).split())


def list_tasks(status: str = "all") -> list[dict]:
    q = "SELECT * FROM tasks"
    if status == "open":
        q += " WHERE done = 0"
    elif status == "done":
        q += " WHERE done = 1"
    q += " ORDER BY done ASC, CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id ASC"
    with _conn() as c:
        return [_row(r) for r in c.execute(q).fetchall()]


def complete_task(task_id: int | None = None, title: str | None = None) -> dict:
    """Mark a task done by id, or by a case-insensitive title match on open tasks."""
    with _conn() as c:
        row = None
        if task_id is not None:
            row = c.execute("SELECT * FROM tasks WHERE id = ?", (int(task_id),)).fetchone()
        elif title:
            row = c.execute(
                "SELECT * FROM tasks WHERE done = 0 AND lower(title) LIKE ? ORDER BY id LIMIT 1",
                (f"%{title.strip().lower()}%",),
            ).fetchone()
        if row is None:
            raise LookupError("task not found")
        c.execute("UPDATE tasks SET done = 1, completed_at = ? WHERE id = ?", (_now(), row["id"]))
        return _row(c.execute("SELECT * FROM tasks WHERE id = ?", (row["id"],)).fetchone())


def update_task(task_id: int, title: str | None = None, priority: str | None = None,
                due: str | None = None, done: bool | None = None) -> dict:
    """Patch any subset of fields. Pass due="" to clear the due date."""
    fields, values = [], []
    if title is not None and title.strip():
        fields.append("title = ?"); values.append(title.strip())
    if priority is not None and priority.lower() in PRIORITIES:
        fields.append("priority = ?"); values.append(priority.lower())
    if due is not None:
        fields.append("due = ?"); values.append(due or None)
    if done is not None:
        fields.append("done = ?"); values.append(int(done))
        fields.append("completed_at = ?"); values.append(_now() if done else None)
    with _conn() as c:
        if c.execute("SELECT 1 FROM tasks WHERE id = ?", (int(task_id),)).fetchone() is None:
            raise LookupError("task not found")
        if fields:
            c.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", (*values, int(task_id)))
        return _row(c.execute("SELECT * FROM tasks WHERE id = ?", (int(task_id),)).fetchone())


def delete_task(task_id: int) -> dict:
    with _conn() as c:
        row = c.execute("SELECT * FROM tasks WHERE id = ?", (int(task_id),)).fetchone()
        if row is None:
            raise LookupError("task not found")
        c.execute("DELETE FROM tasks WHERE id = ?", (int(task_id),))
        return _row(row)


def restore_task(task: dict) -> dict:
    """Re-insert a deleted task with its original id (used by undo)."""
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO tasks (id, title, priority, due, done, created_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task["id"], task["title"], task["priority"], task.get("due"), int(task.get("done", False)),
             task.get("created_at") or _now(), task.get("completed_at")),
        )
        return _row(c.execute("SELECT * FROM tasks WHERE id = ?", (task["id"],)).fetchone())


STOPWORDS = {"the", "a", "an", "to", "for", "my", "task", "of", "and", "on", "in", "at", "with", "it"}


def _stems(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w[:5] for w in words if w not in STOPWORDS}


def find_open_by_title(title: str) -> dict | None:
    """Best match for a spoken title: substring first, then shared word stems
    (so "practicing the pitch" finds "Practice the pitch"). Open tasks win ties."""
    needle = title.strip().lower()
    if not needle:
        return None
    tasks = list_tasks()
    for t in sorted(tasks, key=lambda t: t["done"]):
        if needle in t["title"].lower():
            return t
    want = _stems(needle)
    best, best_score = None, 0.0
    for t in tasks:
        have = _stems(t["title"])
        if not want or not have:
            continue
        score = len(want & have) / len(want | have) - (0.01 if t["done"] else 0)
        if score > best_score:
            best, best_score = t, score
    return best if best_score >= 0.3 else None
