"""Notification queue for background tasks.

Pushed to by the autonomous daemon, polled by the browser HUD.
"""

import threading
from datetime import datetime

_queue = []
_lock = threading.Lock()
MAX_QUEUE = 100


def push(title: str, body: str, kind: str = "info") -> None:
    with _lock:
        _queue.append({
            "title": title,
            "body": body,
            "kind": kind,
            "time": datetime.now().strftime("%H:%M"),
        })
        if len(_queue) > MAX_QUEUE:
            _queue.pop(0)


def drain() -> list:
    """Return all pending and clear the queue."""
    with _lock:
        items = list(_queue)
        _queue.clear()
    return items


def peek() -> list:
    with _lock:
        return list(_queue)