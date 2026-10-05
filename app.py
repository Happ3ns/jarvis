"""Web UI for JARVIS — Flask server with streaming support."""

import json
import memory
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
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)