"""Unified task store for JARVIS — scheduled tasks and watchers.

Backed by SQLite (tasks.db). Supports:
  - Recurring tasks: "every 30m", "every 2h", "daily 08:00"
  - One-shot tasks: "at 2026-10-10 14:00"
  - Watchers: run check_code periodically; if truthy, run action

All tasks execute JARVIS prompts via brain.ask() when triggered.
"""

import json
import re
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "tasks.db"
_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                schedule TEXT,
                check_code TEXT,
                action TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_run_at TIMESTAMP,
                next_run_at TIMESTAMP,
                run_count INTEGER DEFAULT 0,
                last_result TEXT
            )
        """)
        conn.commit()


_init_db()


# ---------- Schedule parsing ----------

def _parse_schedule(spec: str):
    """Return (kind, seconds_or_time) from a schedule spec."""
    s = spec.strip().lower()

    m = re.match(r"every\s+(\d+)\s*(s|sec|m|min|h|hr|hour|d|day)s?", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        mult = {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "hr": 3600,
                "hour": 3600, "d": 86400, "day": 86400}[unit]
        return ("interval", n * mult)

    m = re.match(r"daily\s+(\d{1,2}):(\d{2})", s)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        return ("daily", (hour, minute))

    m = re.match(r"at\s+(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        h = int(m.group(4)) if m.group(4) else 0
        mi = int(m.group(5)) if m.group(5) else 0
        return ("once", datetime(y, mo, d, h, mi))

    return (None, None)


def _compute_next_run(schedule: str, from_time: datetime = None):
    """Compute the next run time from a schedule spec."""
    if from_time is None:
        from_time = datetime.now()

    kind, value = _parse_schedule(schedule)
    if kind is None:
        return None

    if kind == "interval":
        return from_time + timedelta(seconds=value)

    if kind == "daily":
        h, mi = value
        today = from_time.replace(hour=h, minute=mi, second=0, microsecond=0)
        if today <= from_time:
            return today + timedelta(days=1)
        return today

    if kind == "once":
        return value

    return None


# ---------- CRUD ----------

def add_scheduled(name: str, schedule: str, action: str) -> str:
    """Add a scheduled task. Returns confirmation message."""
    kind, _ = _parse_schedule(schedule)
    if kind is None:
        return (f"Could not parse schedule '{schedule}'. "
                "Try: 'every 30m', 'daily 08:00', 'at 2026-10-10 14:00'")

    next_run = _compute_next_run(schedule)

    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO tasks (name, type, schedule, action, next_run_at) "
            "VALUES (?, 'scheduled', ?, ?, ?)",
            (name, schedule, action, next_run.isoformat() if next_run else None),
        )
        conn.commit()

    return f"Scheduled '{name}' — {schedule}. Next run: {next_run}"


def add_watcher(name: str, check_code: str, action: str) -> str:
    """Add a watcher task."""
    if not check_code.strip():
        return "check_code is required for watchers."

    next_check = datetime.now() + timedelta(seconds=60)

    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO tasks (name, type, check_code, action, next_run_at) "
            "VALUES (?, 'watcher', ?, ?, ?)",
            (name, check_code, action, next_check.isoformat()),
        )
        conn.commit()

    return f"Watcher '{name}' active. Checking every 60s."


def list_tasks() -> str:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()

    if not rows:
        return "No scheduled tasks yet."

    lines = [f"Scheduled tasks ({len(rows)}):"]
    for r in rows:
        status = "on" if r["enabled"] else "off"
        kind = r["type"]
        next_run = r["next_run_at"][:16] if r["next_run_at"] else "?"
        runs = r["run_count"] or 0
        lines.append(
            f"  [{r['id']}] {r['name']} ({kind}, {status}) "
            f"— runs: {runs}, next: {next_run}"
        )
    return "\n".join(lines)


def get(id: int) -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
    return dict(row) if row else None


def delete(id: int) -> str:
    with _lock, _connect() as conn:
        result = conn.execute("DELETE FROM tasks WHERE id = ?", (id,))
        conn.commit()
    if result.rowcount == 0:
        return f"No task with id {id}."
    return f"Deleted task {id}."


def toggle(id: int) -> str:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT enabled FROM tasks WHERE id = ?", (id,)).fetchone()
        if not row:
            return f"No task with id {id}."
        new = 0 if row["enabled"] else 1
        conn.execute("UPDATE tasks SET enabled = ? WHERE id = ?", (new, id))
        conn.commit()
    return f"Task {id}: {'enabled' if new else 'disabled'}."


def get_due(now: datetime = None) -> list:
    """Return tasks whose next_run_at has passed."""
    if now is None:
        now = datetime.now()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE enabled = 1 "
            "AND next_run_at IS NOT NULL AND next_run_at <= ?",
            (now.isoformat(),),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_ran(id: int, result: str):
    """Update a task after it runs."""
    task = get(id)
    if not task:
        return

    now = datetime.now()
    next_run = None

    if task["type"] == "scheduled":
        if task["schedule"]:
            next_run = _compute_next_run(task["schedule"], from_time=now)
    elif task["type"] == "watcher":
        next_run = now + timedelta(seconds=60)

    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE tasks SET last_run_at = ?, next_run_at = ?, "
            "run_count = COALESCE(run_count, 0) + 1, last_result = ? "
            "WHERE id = ?",
            (now.isoformat(),
             next_run.isoformat() if next_run else None,
             result[:500],
             id),
        )
        conn.commit()