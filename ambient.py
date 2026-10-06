"""Ambient context tracker for JARVIS.

Tracks what you're currently doing so JARVIS can answer with awareness.
Uses only Windows APIs via ctypes — no extra libraries needed.

All data stays local in ambient_state.json. Nothing is uploaded.
Toggle with /ambient on|off.
"""

import ctypes
import ctypes.wintypes
import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).parent / "ambient_state.json"

_running = False
_thread = None
_enabled = True
_interval = 5  # seconds

# App-time tracking
_current_app = None
_current_app_start = None
_app_times = {}
_app_times_lock = threading.Lock()


# ---------- Windows API helpers ----------

def _get_active_window_title() -> str:
    """Get the title of the currently active window."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or ""
    except Exception:
        return ""


def _get_idle_seconds() -> int:
    """Seconds since last keyboard/mouse input."""
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.wintypes.UINT),
                ("dwTime", ctypes.wintypes.DWORD),
            ]
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return int(millis / 1000)
    except Exception:
        pass
    return 0


def _get_battery_info() -> dict:
    try:
        import psutil
        bat = psutil.sensors_battery()
        if bat:
            return {
                "percent": int(bat.percent),
                "plugged": bool(bat.power_plugged),
            }
    except Exception:
        pass
    return {"percent": None, "plugged": None}


def _get_git_uncommitted(repo_paths: list) -> list:
    results = []
    for repo in repo_paths:
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo, capture_output=True, text=True, timeout=3,
            )
            if r.returncode == 0:
                count = len([l for l in r.stdout.strip().split("\n") if l])
                if count > 0:
                    results.append({
                        "repo": Path(repo).name,
                        "uncommitted": count,
                    })
        except Exception:
            pass
    return results


def _get_recent_files(minutes: int = 60) -> list:
    jarvis_dir = Path(__file__).parent
    cutoff = time.time() - (minutes * 60)
    recent = []
    try:
        for f in jarvis_dir.glob("*.py"):
            if f.stat().st_mtime > cutoff:
                recent.append(f.name)
    except Exception:
        pass
    return sorted(recent)[:5]


def _extract_app_name(title: str) -> str:
    if not title:
        return "Unknown"
    # Common patterns: "file.py - VS Code", "Page - Chrome"
    if " - " in title:
        return title.split(" - ")[-1].strip()
    return title[:40]


# ---------- App time tracking ----------

def _update_app_time(app: str) -> None:
    global _current_app, _current_app_start
    now = time.time()
    with _app_times_lock:
        if app != _current_app:
            if _current_app is not None and _current_app_start is not None:
                elapsed = now - _current_app_start
                _app_times[_current_app] = _app_times.get(_current_app, 0) + elapsed
            _current_app = app
            _current_app_start = now


def _get_current_app_time() -> float:
    with _app_times_lock:
        if _current_app is None or _current_app_start is None:
            return 0
        return time.time() - _current_app_start


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m}m"


# ---------- Main loop ----------

def _tick() -> dict:
    """Collect one snapshot of ambient state."""
    title = _get_active_window_title()
    app = _extract_app_name(title)
    _update_app_time(app)

    battery = _get_battery_info()
    idle = _get_idle_seconds()
    now = datetime.now()

    state = {
        "active_app": app,
        "active_window": title[:100],
        "active_duration_seconds": _get_current_app_time(),
        "idle_seconds": idle,
        "battery_percent": battery["percent"],
        "battery_plugged": battery["plugged"],
        "time": now.strftime("%I:%M %p"),
        "date": now.strftime("%A, %B %d"),
        "recent_files": _get_recent_files(),
        "git_uncommitted": _get_git_uncommitted(
            [str(Path(__file__).parent)]
        ),
        "updated": now.isoformat(timespec="seconds"),
    }
    return state


def _loop() -> None:
    while _running:
        try:
            if _enabled:
                state = _tick()
                STATE_FILE.write_text(
                    json.dumps(state, indent=2), encoding="utf-8"
                )
        except Exception as e:
            print(f"[ambient] tick error: {e}")
        time.sleep(_interval)


# ---------- Public API ----------

def start() -> None:
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()
    print("[ambient] Level 3 tracker started")


def stop() -> None:
    global _running
    _running = False
    print("[ambient] Stopped")


def enable() -> str:
    global _enabled
    _enabled = True
    return "Ambient tracking: ON"


def disable() -> str:
    global _enabled
    _enabled = False
    return "Ambient tracking: OFF"


def is_enabled() -> bool:
    return _enabled


def context_summary() -> str:
    """Return a short text summary for injection into the system prompt."""
    if not _enabled or not STATE_FILE.exists():
        return ""
    try:
        s = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return ""

    lines = ["Current context:"]

    if s.get("active_app"):
        duration = _format_duration(s.get("active_duration_seconds", 0))
        lines.append(f"- Active: {s['active_window']} ({duration})")

    idle = s.get("idle_seconds", 0)
    if idle > 300:
        lines.append(f"- Idle for {_format_duration(idle)}")

    bp = s.get("battery_percent")
    if bp is not None:
        plug = "plugged in" if s.get("battery_plugged") else "on battery"
        lines.append(f"- Battery: {bp}% ({plug})")

    git = s.get("git_uncommitted", [])
    if git:
        for g in git:
            lines.append(f"- Git: {g['uncommitted']} uncommitted changes in {g['repo']}/")

    rf = s.get("recent_files", [])
    if rf:
        lines.append(f"- Recent files: {', '.join(rf[:4])}")

    if s.get("time"):
        lines.append(f"- Time: {s['time']} ({s.get('date', '')})")

    return "\n".join(lines)


def show_state() -> str:
    """Full state for the /ambient command."""
    if not STATE_FILE.exists():
        return "No state recorded yet."
    try:
        s = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return json.dumps(s, indent=2)
    except Exception as e:
        return f"Error reading state: {e}"