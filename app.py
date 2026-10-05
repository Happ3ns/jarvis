"""Web UI for JARVIS — Flask server that wraps think() and the tools."""

import threading
import time

from flask import Flask, render_template, request, jsonify

from jarvis import think, QUIET_PREFIX
from voice import listen_voice, speak
from advanced import remember
from wake_listener import WakeWordListener

app = Flask(__name__)

EXIT_WORDS = ["exit", "goodbye", "shut down", "quit", "stop"]

# ---- Shared buffer for wake-word conversations ----
wake_events = []
wake_events_lock = threading.Lock()


def _is_exit(text: str) -> bool:
    lowered = text.lower()
    return any(w in lowered for w in EXIT_WORDS)


def push_wake_event(user_text: str, reply: str) -> None:
    """Store a wake-word conversation so the browser can pick it up."""
    with wake_events_lock:
        wake_events.append({"user": user_text, "reply": reply})
        if len(wake_events) > 50:
            wake_events.pop(0)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/command", methods=["POST"])
def command():
    """Handle a typed command from the browser."""
    data = request.get_json() or {}
    user_text = (data.get("text") or "").strip()
    if not user_text:
        return jsonify({"error": "empty command"}), 400

    if _is_exit(user_text):
        speak("Goodbye.")
        return jsonify({
            "user": user_text,
            "reply": "Goodbye.",
            "speak": True,
            "exit": True,
        })

    reply = think(user_text)
    quiet = reply.startswith(QUIET_PREFIX)
    if quiet:
        reply = reply[len(QUIET_PREFIX):]
    else:
        speak(reply)

    remember(user_text, reply)

    return jsonify({
        "user": user_text,
        "reply": reply,
        "speak": not quiet,
        "exit": False,
    })


@app.route("/api/voice", methods=["POST"])
def voice():
    """Record from mic and process."""
    user_text = listen_voice()
    if not user_text:
        return jsonify({"error": "no speech detected"}), 200

    if _is_exit(user_text):
        speak("Goodbye.")
        return jsonify({
            "user": user_text,
            "reply": "Goodbye.",
            "speak": True,
            "exit": True,
        })

    reply = think(user_text)
    quiet = reply.startswith(QUIET_PREFIX)
    if quiet:
        reply = reply[len(QUIET_PREFIX):]
    else:
        speak(reply)

    remember(user_text, reply)

    return jsonify({
        "user": user_text,
        "reply": reply,
        "speak": not quiet,
        "exit": False,
    })


@app.route("/api/events", methods=["GET"])
def events():
    """Return and clear recent wake-word conversations for the browser."""
    with wake_events_lock:
        result = list(wake_events)
        wake_events.clear()
    return jsonify({"events": result})


# ---------- Wake word listener ----------

def _start_wake_listener():
    """Start Vosk wake word listener in a background thread."""
    wake_event = threading.Event()

    wake_listener = WakeWordListener(
        on_wake=lambda: wake_event.set(),
        device=11,
    )
    wake_listener.start()

    def _listen_loop():
        while True:
            if wake_event.is_set():
                wake_event.clear()
                speak("Yes?")
                user_text = listen_voice()

                if user_text and not _is_exit(user_text):
                    reply = think(user_text)
                    quiet = reply.startswith(QUIET_PREFIX)
                    if quiet:
                        reply = reply[len(QUIET_PREFIX):]
                    else:
                        speak(reply)
                    remember(user_text, reply)
                    push_wake_event(user_text, reply)   # notify the browser
                elif user_text and _is_exit(user_text):
                    speak("Goodbye.")

            time.sleep(0.2)

    threading.Thread(target=_listen_loop, daemon=True).start()
    return wake_listener


if __name__ == "__main__":
    speak("JARVIS online. Say 'Jarvis' to wake me, or type in the browser.")

    wake_listener = _start_wake_listener()

    try:
        app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
    finally:
        wake_listener.stop()