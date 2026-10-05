"""Long-term memory backed by SQLite.

Persists user-stated facts and conversation history across sessions.
"""

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "memory.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_text TEXT NOT NULL,
                reply TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_date
            ON conversations (created_at)
        """)
        conn.commit()


_init_db()


# ---------- Facts ----------

def remember_fact(text: str) -> str:
    text = text.strip()
    if not text:
        return "What should I remember?"

    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM facts WHERE LOWER(text) = LOWER(?)",
            (text,)
        ).fetchone()

        if existing:
            return "I already remember that."

        conn.execute("INSERT INTO facts (text) VALUES (?)", (text,))
        conn.commit()

    return f"Remembered: {text}"


def get_all_facts() -> str:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT text, created_at FROM facts ORDER BY created_at ASC"
        ).fetchall()

    if not rows:
        return "I don't know anything about you yet."

    lines = []
    for r in rows:
        date = r["created_at"][:10]
        lines.append(f"• {r['text']} (since {date})")

    return f"I know {len(rows)} thing{'s' if len(rows) != 1 else ''}:\n" + "\n".join(lines)


def forget_fact(text: str) -> str:
    text = text.strip()
    with _connect() as conn:
        result = conn.execute(
            "DELETE FROM facts WHERE LOWER(text) = LOWER(?)",
            (text,)
        )
        if result.rowcount == 0:
            result = conn.execute(
                "DELETE FROM facts WHERE LOWER(text) LIKE LOWER(?)",
                (f"%{text}%",)
            )
        conn.commit()

        if result.rowcount == 0:
            return f"I don't remember anything about '{text}'."

        return f"Forgot {result.rowcount} fact(s)."


def clear_all_facts() -> str:
    with _connect() as conn:
        result = conn.execute("DELETE FROM facts")
        conn.commit()
    return f"Cleared {result.rowcount} facts."


# ---------- Conversations ----------

def log_conversation(user_text: str, reply: str) -> None:
    if not user_text.strip():
        return
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO conversations (user_text, reply) VALUES (?, ?)",
                (user_text.strip(), reply.strip())
            )
            conn.commit()
    except Exception:
        pass  # never crash the main loop over logging


def get_recent_conversations(n: int = 5) -> str:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT user_text, reply, created_at FROM conversations "
            "ORDER BY created_at DESC LIMIT ?",
            (n,)
        ).fetchall()

    if not rows:
        return "No conversation history yet."

    lines = []
    for r in reversed(rows):
        t = r["created_at"][11:16]
        date = r["created_at"][:10]
        lines.append(f"[{date} {t}]")
        lines.append(f"  You: {r['user_text']}")
        lines.append(f"  Me: {r['reply'][:100]}")

    return "\n".join(lines)


def search_conversations(query: str, n: int = 5) -> str:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT user_text, reply, created_at FROM conversations "
            "WHERE LOWER(user_text) LIKE LOWER(?) OR LOWER(reply) LIKE LOWER(?) "
            "ORDER BY created_at DESC LIMIT ?",
            (f"%{query}%", f"%{query}%", n)
        ).fetchall()

    if not rows:
        return f"No conversations found mentioning '{query}'."

    lines = [f"Found {len(rows)} matching conversation(s):"]
    for r in rows:
        date = r["created_at"][:10]
        t = r["created_at"][11:16]
        lines.append(f"[{date} {t}] You: {r['user_text']}")

    return "\n".join(lines)


def get_conversations_on(date_str: str) -> str:
    target = _parse_date(date_str)
    if target is None:
        return f"I couldn't understand the date '{date_str}'."

    date_iso = target.strftime("%Y-%m-%d")
    with _connect() as conn:
        rows = conn.execute(
            "SELECT user_text, reply, created_at FROM conversations "
            "WHERE DATE(created_at) = ? ORDER BY created_at ASC",
            (date_iso,)
        ).fetchall()

    if not rows:
        return f"No conversations on {date_iso}."

    lines = [f"On {date_iso} ({len(rows)} exchange{'s' if len(rows) != 1 else ''}):"]
    for r in rows:
        t = r["created_at"][11:16]
        lines.append(f"  [{t}] You: {r['user_text']}")

    return "\n".join(lines)


def _parse_date(text: str):
    text = text.lower().strip()
    now = datetime.now()

    if text == "today":
        return now
    if text == "yesterday":
        return now - timedelta(days=1)

    m = re.match(r"last\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", text)
    if m:
        day_name = m.group(1)
        days = ["monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday"]
        target_dow = days.index(day_name)
        current_dow = now.weekday()
        diff = (current_dow - target_dow) % 7
        if diff == 0:
            diff = 7
        return now - timedelta(days=diff)

    m = re.match(r"(\d+)\s+days?\s+ago", text)
    if m:
        return now - timedelta(days=int(m.group(1)))

    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        pass

    return None


def get_stats() -> str:
    with _connect() as conn:
        facts = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        convs = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        oldest = conn.execute("SELECT MIN(created_at) FROM conversations").fetchone()[0]

    parts = [
        f"{facts} fact{'s' if facts != 1 else ''}",
        f"{convs} conversation{'s' if convs != 1 else ''}",
    ]
    if oldest:
        parts.append(f"oldest from {oldest[:10]}")
    return "Memory: " + ", ".join(parts) + "."


def clear_all_conversations() -> str:
    with _connect() as conn:
        result = conn.execute("DELETE FROM conversations")
        conn.commit()
    return f"Cleared {result.rowcount} conversations."