"""Web UI for JARVIS — Flask server that wraps think() and the tools."""

from flask import Flask, render_template, request, jsonify

from jarvis import think, QUIET_PREFIX
from voice import listen_voice, speak
from advanced import remember

app = Flask(__name__)

# NOTE: "stop" is intentionally NOT in this list.
# "stop" means "stop the music" — it should route to think(), not exit.
EXIT_WORDS = ["exit", "goodbye", "shut down", "quit"]


def _is_exit(text: str) -> bool:
    lowered = text.lower().strip()
    # Only match if the ENTIRE command is an exit word,
    # so "stop the music" doesn't accidentally trigger exit
    return lowered in EXIT_WORDS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/command", methods=["POST"])
def command():
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


if __name__ == "__main__":
    speak("JARVIS online. Type in the browser.")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)