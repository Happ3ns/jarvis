"""Anticipation engine for JARVIS.

Learns your query patterns. Precomputes answers during idle time.
Serves them from cache when you ask. Zero cloud tokens for precompute.

Storage: SQLite (anticipate.db).
Precompute: runs tool calls directly, no LLM.
"""

import ctypes
import ctypes.wintypes
import json
import re
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "anticipate.db"

# ─── Tunables ───
MIN_OBSERVATIONS = 3          # times a pattern must repeat before we trust it
CACHE_TTL_SECONDS = 3600      # how long a precomputed answer stays fresh
CONSOLIDATION_INTERVAL = 900  # min seconds between consolidation passes
IDLE_THRESHOLD = 900          # seconds of idle before we consider user away

_running = False
_thread = None
_lock = threading.Lock()


# ─── DB helpers ───
def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            hour INTEGER NOT NULL,
            weekday INTEGER NOT NULL,
            text TEXT NOT NULL,
            tools_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_text_hour ON queries(text, hour);

        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created REAL NOT NULL,
            expires REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires);

        CREATE TABLE IF NOT EXISTS meta (
            k TEXT PRIMARY KEY,
            v TEXT
        );
        """)


def _normalize(text):
    """Normalize a query for pattern matching."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _cache_key(text, hour):
    return f"{_normalize(text)}|{hour}"


# ─── Public: log every query ───
def log_query(text, tools=None):
    """Call this after every response. tools = list of {'name', 'args'}."""
    if not text or not text.strip():
        return
    now = datetime.now()
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO queries (ts, hour, weekday, text, tools_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (time.time(), now.hour, now.weekday(),
                 _normalize(text), json.dumps(tools or [])),
            )
    except Exception as e:
        print(f"[anticipate] log_query error: {e}")


# ─── Public: check cache before calling the LLM ───
def get_cached(text):
    """Return (hit: bool, value: str or None)."""
    hour = datetime.now().hour
    key = _cache_key(text, hour)
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT value, expires FROM cache WHERE key = ?", (key,)
            ).fetchone()
            if row and row["expires"] > time.time():
                return True, row["value"]
            if row:
                c.execute("DELETE FROM cache WHERE key = ?", (key,))
    except Exception:
        pass
    return False, None


def _set_cache(text, hour, value):
    key = _cache_key(text, hour)
    now = time.time()
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO cache (key, value, created, expires) "
            "VALUES (?, ?, ?, ?)",
            (key, value, now, now + CACHE_TTL_SECONDS),
        )


def _cleanup_cache():
    try:
        with _conn() as c:
            c.execute("DELETE FROM cache WHERE expires < ?", (time.time(),))
    except Exception:
        pass


# ─── Pattern learning ───
def learn_patterns():
    """Scan recent queries, return patterns seen MIN_OBSERVATIONS+ times."""
    cutoff = time.time() - (14 * 24 * 3600)
    with _conn() as c:
        rows = c.execute(
            "SELECT hour, text, tools_json FROM queries WHERE ts > ?",
            (cutoff,),
        ).fetchall()

    groups = {}
    for r in rows:
        key = (r["text"], r["hour"])
        if key not in groups:
            groups[key] = {"count": 0, "tools": []}
        groups[key]["count"] += 1
        try:
            for t in json.loads(r["tools_json"] or "[]"):
                groups[key]["tools"].append(t)
        except Exception:
            pass

    patterns = []
    for (text, hour), info in groups.items():
        if info["count"] < MIN_OBSERVATIONS:
            continue
        if not info["tools"]:
            continue
        # Most recent tool call for this pattern
        tool = info["tools"][-1]
        if not isinstance(tool, dict) or not tool.get("name"):
            continue
        patterns.append({
            "text": text,
            "hour": hour,
            "count": info["count"],
            "tool": tool,
        })
    return patterns


def precompute(patterns, execute_tool_fn):
    """Run tool calls for patterns due now or next hour. No LLM."""
    now_hour = datetime.now().hour
    done = 0
    for p in patterns:
        if p["hour"] not in (now_hour, (now_hour + 1) % 24):
            continue
        tool = p["tool"]
        name = tool.get("name")
        args = tool.get("args", {})
        if not name:
            continue
        try:
            result = execute_tool_fn(name, args)
            if result and not str(result).startswith("Tool error"):
                _set_cache(p["text"], p["hour"], str(result))
                done += 1
                print(f"[anticipate] precomputed: '{p['text']}' via {name}")
        except Exception as e:
            print(f"[anticipate] precompute error '{p['text']}': {e}")
    return done


# ─── Consolidation ───
def _get_last_consolidation():
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT v FROM meta WHERE k = 'last_consolidation'"
            ).fetchone()
            return float(row["v"]) if row else 0
    except Exception:
        return 0


def _set_last_consolidation(ts):
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO meta (k, v) VALUES ('last_consolidation', ?)",
            (str(ts),),
        )


def consolidate(execute_tool_fn, force=False):
    """Learn patterns → precompute → cleanup. Rate-limited unless forced."""
    with _lock:
        now = time.time()
        if not force and (now - _get_last_consolidation()) < CONSOLIDATION_INTERVAL:
            return 0
        try:
            patterns = learn_patterns()
            n = precompute(patterns, execute_tool_fn)
            _cleanup_cache()
            _set_last_consolidation(now)
            if n > 0:
                print(f"[anticipate] consolidation: {n} precomputes from "
                      f"{len(patterns)} patterns")
            return n
        except Exception as e:
            print(f"[anticipate] consolidation error: {e}")
            return 0


def startup_catchup(execute_tool_fn):
    """On boot, catch up if we've been off for a while."""
    last = _get_last_consolidation()

    # First run — no baseline. Set it and skip catch-up.
    if last == 0:
        print("[anticipate] first run — marking baseline, no catch-up needed")
        _set_last_consolidation(time.time())
        return

    hours = (time.time() - last) / 3600
    if hours >= 24:
        print(f"[anticipate] catch-up needed ({hours:.1f}h since last)")
        consolidate(execute_tool_fn, force=True)
    else:
        print(f"[anticipate] last consolidation {hours:.1f}h ago")

# ─── Idle detection ───
def _idle_seconds():
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.wintypes.UINT),
                        ("dwTime", ctypes.wintypes.DWORD)]
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return int(millis / 1000)
    except Exception:
        pass
    return 0


def _idle_loop(execute_tool_fn):
    while _running:
        try:
            time.sleep(60)
            idle = _idle_seconds()
            if idle >= IDLE_THRESHOLD:
                consolidate(execute_tool_fn, force=True)
        except Exception as e:
            print(f"[anticipate] idle loop error: {e}")


# ─── Public: start / stop / stats ───
def start(execute_tool_fn):
    global _running, _thread
    _init_db()
    startup_catchup(execute_tool_fn)
    if _running:
        return
    _running = True
    _thread = threading.Thread(
        target=_idle_loop, args=(execute_tool_fn,), daemon=True
    )
    _thread.start()
    print("[anticipate] Engine running")


def stop():
    global _running
    _running = False


def stats():
    """For a /api endpoint or UI badge."""
    try:
        with _conn() as c:
            q = c.execute("SELECT COUNT(*) FROM queries").fetchone()[0]
            cached = c.execute(
                "SELECT COUNT(*) FROM cache WHERE expires > ?", (time.time(),)
            ).fetchone()[0]
            last = c.execute(
                "SELECT v FROM meta WHERE k = 'last_consolidation'"
            ).fetchone()
            last_ts = float(last["v"]) if last else 0
            return {
                "queries_logged": q,
                "cached_answers": cached,
                "last_consolidation": (
                    datetime.fromtimestamp(last_ts).strftime("%H:%M")
                    if last_ts else "never"
                ),
            }
    except Exception:
        return {"queries_logged": 0, "cached_answers": 0,
                "last_consolidation": "never"}