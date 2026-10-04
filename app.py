"""Web UI for JARVIS — Flask server that wraps think() and the tools."""

from flask import Flask, render_template, request, jsonify

from jarvis import think, QUIET_PREFIX
from voice import listen_voice

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/command", methods=["POST"])
def command():
    """Handle a typed command."""
    data = request.get_json() or {}
    user_text = (data.get("text") or "").strip()
    if not user_text:
        return jsonify({"error": "empty command"}), 400

    # Exit signal — the frontend will shut down the session
    if any(w in user_text.lower() for w in
           ["exit", "goodbye", "shut down", "quit", "stop"]):
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

    reply = think(user_text)
    quiet = reply.startswith(QUIET_PREFIX)
    if quiet:
        reply = reply[len(QUIET_PREFIX):]

    return jsonify({
        "user": user_text,
        "reply": reply,
        "speak": not quiet,
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)