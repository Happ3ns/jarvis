"""Background daemon for JARVIS — runs scheduled tasks and watchers.

Started by app.py on boot. Runs in a background thread.
Checks for due tasks every 10 seconds and executes them.
"""

import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import notifications
import tasks

_running = False
_paused = False
_thread = None

# Safety
CHECK_INTERVAL = 10
MAX_CONCURRENT_RUNS = 1  # only one task at a time
_executing = threading.Event()
_last_run_summary = ""


def _run_check_code(code: str, timeout: int = 10):
    """Run watcher check_code in a subprocess. Returns (truthy, output)."""
    BLOCKED = ["os.system", "os.popen", "subprocess", "socket",
               "shutil.rmtree", "__import__", "eval(", "exec("]
    lowered = code.lower()
    for b in BLOCKED:
        if b.lower() in lowered:
            return False, f"Blocked pattern: {b}"

    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "check.py"
        script.write_text(code, encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, timeout=timeout,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            return False, "check_code timed out"
        except Exception as e:
            return False, f"check_code error: {e}"

    stdout = (result.stdout or "").strip()
    if result.returncode != 0:
        return False, f"exit {result.returncode}: {(result.stderr or '')[:200]}"
    # Truthy: "true", "1", "yes", or any non-empty output
    truthy = stdout.lower() in ("true", "1", "yes") or bool(stdout)
    return truthy, stdout[:200]


def _execute_action(action: str, task_name: str) -> str:
    """Run a task's action through brain.ask(). Lazy import to avoid cycles."""
    try:
        from brain import ask
        from jarvis import execute_tool
    except Exception as e:
        return f"import error: {e}"

    try:
        result = ask(action, execute_tool, max_steps=8)
        return result[:300] if result else "(no output)"
    except Exception as e:
        return f"action error: {e}"


def _process_task(task: dict) -> None:
    """Run one task and update its state."""
    task_id = task["id"]
    name = task["name"]
    kind = task["type"]

    print(f"[daemon] Running task {task_id}: {name} ({kind})")

    if kind == "scheduled":
        result = _execute_action(task["action"], name)
        print(f"[daemon]   → {result[:120]}")
        tasks.mark_ran(task_id, result)
        notifications.push(
            f"Scheduled: {name}",
            result[:200],
            kind="info",
        )
        return

    if kind == "watcher":
        # Check condition, only fire if truthy
        truthy, output = _run_check_code(task["check_code"])
        print(f"[daemon]   check → truthy={truthy} output={output[:80]}")
        if truthy:
            result = _execute_action(task["action"], name)
            print(f"[daemon]   → fired: {result[:120]}")
            tasks.mark_ran(task_id, f"FIRED: {result[:200]}")
            notifications.push(
                f"Watcher: {name}",
                result[:200],
                kind="alert",
            )
        else:
            # Not triggered — just reschedule, don't increment runs
            next_time = datetime.now().isoformat()
            import sqlite3
            with sqlite3.connect(tasks.DB_PATH) as conn:
                conn.execute(
                    "UPDATE tasks SET next_run_at = ? WHERE id = ?",
                    ((datetime.now().timestamp() + 60) and
                     datetime.fromtimestamp(time.time() + 60).isoformat(),
                     task_id),
                )
                conn.commit()
        return

    # Unknown type
    tasks.mark_ran(task_id, f"Unknown task type: {kind}")


def _loop() -> None:
    global _last_run_summary
    print("[daemon] started — checking every 10s")
    while _running:
        try:
            if not _paused:
                due = tasks.get_due()
                for task in due:
                    if not _executing.is_set():
                        _executing.set()
                        try:
                            _process_task(task)
                            _last_run_summary = (
                                f"{datetime.now().strftime('%H:%M')} — "
                                f"ran '{task['name']}'"
                            )
                        finally:
                            _executing.clear()
                    else:
                        break
        except Exception as e:
            print(f"[daemon] error: {e}")
        time.sleep(CHECK_INTERVAL)


# ---------- Public API ----------

def start() -> None:
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()


def stop() -> None:
    global _running
    _running = False
    print("[daemon] stopping")


def pause() -> str:
    global _paused
    _paused = True
    return "Daemon paused."


def resume() -> str:
    global _paused
    _paused = False
    return "Daemon resumed."


def status() -> str:
    state = "PAUSED" if _paused else ("RUNNING" if _running else "STOPPED")
    extra = f"\nLast run: {_last_run_summary}" if _last_run_summary else ""
    return f"Daemon: {state}{extra}"