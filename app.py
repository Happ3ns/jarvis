"""Web UI for JARVIS — Flask server with streaming support."""

import json
import memory
import ambient
from flask import Flask, render_template, request, jsonify, Response

from jarvis import think_stream, QUIET_PREFIX
from voice import listen_voice, speak
from advanced import remember

app = Flask(__name__)

EXIT_WORDS = ["exit", "goodbye", "shut down", "quit"]


def _is_exit(text: str) -> bool:
    return text.lower().strip() in EXIT_WORDS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/command", methods=["POST"])
def command():
    """Non-streaming endpoint (kept for compatibility)."""
    data = request.get_json() or {}
    user_text = (data.get("text") or "").strip()
    if not user_text:
        return jsonify({"error": "empty command"}), 400

    if _is_exit(user_text):
        speak("Goodbye.")
        return jsonify({
            "user": user_text, "reply": "Goodbye.",
            "speak": True, "exit": True,
        })

    full_reply = ""
    for kind, chunk in think_stream(user_text):
        if kind == "content":
            full_reply += chunk

    quiet = full_reply.startswith(QUIET_PREFIX)
    reply = full_reply[len(QUIET_PREFIX):] if quiet else full_reply
    if not quiet:
        speak(reply)
    remember(user_text, reply)
    
    memory.log_conversation(user_text, reply)   # <-- new line
    return jsonify({
        "user": user_text, "reply": reply,
        "speak": not quiet, "exit": False,
    })

@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    """Return and clear queued notifications."""
    import notifications
    return jsonify({"notifications": notifications.drain()})

@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    import tasks
    import sqlite3
    with sqlite3.connect(tasks.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, name, type, schedule, enabled, "
            "next_run_at, run_count FROM tasks "
            "WHERE enabled = 1 ORDER BY next_run_at ASC"
        ).fetchall()
    return jsonify({"tasks": [dict(r) for r in rows]})

@app.route("/api/system", methods=["GET"])
def get_system():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage("C:\\").percent if __import__("os").name == "nt" else psutil.disk_usage("/").percent
        net = psutil.net_io_counters()
        return jsonify({
            "cpu": round(cpu),
            "mem": round(mem),
            "disk": round(disk),
            "net_sent_mb": round(net.bytes_sent / 1024 / 1024, 1),
            "net_recv_mb": round(net.bytes_recv / 1024 / 1024, 1),
        })
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/memory-stats", methods=["GET"])
def memory_stats_endpoint():
    import sqlite3
    from pathlib import Path
    result = {"facts": 0, "conversations": 0}
    db = Path("memory.db")
    if db.exists():
        try:
            with sqlite3.connect(db) as conn:
                result["facts"] = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
                result["conversations"] = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        except Exception:
            pass
    return jsonify(result)


@app.route("/api/tool-stats", methods=["GET"])
def tool_stats_endpoint():
    import json
    from pathlib import Path
    stats_file = Path("tool_stats.json")
    if not stats_file.exists():
        return jsonify({"tools": []})
    try:
        stats = json.loads(stats_file.read_text(encoding="utf-8"))
        tools = []
        for name, s in stats.items():
            if s.get("calls", 0) < 1:
                continue
            rate = s["successes"] / s["calls"] * 100 if s["calls"] else 0
            tools.append({
                "name": name,
                "calls": s["calls"],
                "rate": round(rate),
                "avg": round(s.get("total_time", 0) / s["calls"], 2) if s["calls"] else 0,
            })
        tools.sort(key=lambda x: -x["calls"])
        return jsonify({"tools": tools[:5]})
    except Exception:
        return jsonify({"tools": []})


@app.route("/api/recent-files", methods=["GET"])
def recent_files_endpoint():
    import json
    from pathlib import Path
    state_file = Path("ambient_state.json")
    if not state_file.exists():
        return jsonify({"files": []})
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return jsonify({"files": data.get("recent_files", [])[:6]})
    except Exception:
        return jsonify({"files": []})

@app.route("/api/ambient", methods=["GET"])
def get_ambient():
    import json
    from pathlib import Path
    state_file = Path("ambient_state.json")
    if not state_file.exists():
        return jsonify({"active_app": None, "active_window": None, "idle": 0})
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return jsonify({
            "active_app": data.get("active_app"),
            "active_window": data.get("active_window"),
            "idle": data.get("idle_seconds", 0),
        })
    except Exception:
        return jsonify({"active_app": None, "active_window": None, "idle": 0})

@app.route("/api/command/stream", methods=["POST"])
def command_stream():
    """Streaming endpoint — sends tokens as they're generated."""
    data = request.get_json() or {}
    user_text = (data.get("text") or "").strip()
    if not user_text:
        return jsonify({"error": "empty command"}), 400

    def generate():
        if _is_exit(user_text):
            speak("Goodbye.")
            yield f"data: {json.dumps({'kind': 'exit', 'reply': 'Goodbye.'})}\n\n"
            return

        full_reply = ""
        try:
            for kind, chunk in think_stream(user_text):
                if kind == "content":
                    full_reply += chunk
                    yield f"data: {json.dumps({'kind': 'content', 'text': chunk})}\n\n"
                elif kind == "plan":
                    full_reply += chunk
                    yield f"data: {json.dumps({'kind': 'plan', 'text': chunk})}\n\n"
                elif kind == "status":
                    yield f"data: {json.dumps({'kind': 'status', 'text': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'kind': 'error', 'text': str(e)})}\n\n"
            return

        quiet = full_reply.startswith(QUIET_PREFIX)
        reply = full_reply[len(QUIET_PREFIX):] if quiet else full_reply

        # Speak AFTER all text has streamed to the browser
        if not quiet:
            speak(reply)
        remember(user_text, reply)
        memory.log_conversation(user_text, reply)
        yield f"data: {json.dumps({'kind': 'done', 'reply': reply, 'speak': not quiet})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/voice", methods=["POST"])
def voice():
    user_text = listen_voice()
    if not user_text:
        return jsonify({"error": "no speech detected"}), 200

    if _is_exit(user_text):
        speak("Goodbye.")
        return jsonify({
            "user": user_text, "reply": "Goodbye.",
            "speak": True, "exit": True,
        })

    full_reply = ""
    for kind, chunk in think_stream(user_text):
        if kind == "content":
            full_reply += chunk

    quiet = full_reply.startswith(QUIET_PREFIX)
    reply = full_reply[len(QUIET_PREFIX):] if quiet else full_reply
    if not quiet:
        speak(reply)
    remember(user_text, reply)
    
    memory.log_conversation(user_text, reply)   # <-- new line
    return jsonify({
        "user": user_text, "reply": reply,
        "speak": not quiet, "exit": False,
    })


if __name__ == "__main__":
    speak("JARVIS online. Type in the browser.")
    ambient.start()
    import daemon
    daemon.start()
    try:
        app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
    finally:
        daemon.stop()