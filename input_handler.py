"""Input handler — reads typed lines from the terminal.

Special triggers:
    'voice' or 'v'  → switch to voice mode (mic recording)
    anything else   → treated as a typed command
"""

import sys
import threading
import queue

_events = queue.Queue()
_stop = threading.Event()
VOICE_TRIGGERS = {"voice", "v", "speak", "listen"}


def _reader():
    while not _stop.is_set():
        try:
            line = sys.stdin.readline()
        except Exception:
            break
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        if line.lower() in VOICE_TRIGGERS:
            _events.put(("voice", None))
        else:
            _events.put(("typed", line))


def start(access_key: str = "", keyword: str = "") -> None:
    """Compatibility stub — no wake word needed."""
    threading.Thread(target=_reader, daemon=True).start()


def get(timeout: float = 0.3):
    try:
        return _events.get(timeout=timeout)
    except queue.Empty:
        return None


def stop() -> None:
    _stop.set()