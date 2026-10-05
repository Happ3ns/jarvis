"""JARVIS — voice assistant entry point.

Run with: python jarvis.py
"""

import input_handler
from voice import listen_voice, speak
from tools import (
    get_weather, get_time, get_date, get_system_info, get_ip,
    open_app, open_website,
    search_wikipedia, random_wikipedia,
    play_on_spotify, get_spotify_client,
    calculate, set_timer, take_note, read_notes,
    flip_coin, roll_dice,
)
from search import search_web, search_news
from productivity import (
    send_email, take_screenshot, find_file, open_file,
    get_clipboard, set_clipboard, morning_briefing,
)
from advanced import (
    remember, clear_memory, recall_last_question, recall_last_reply,
    recall_recent, set_reminder, parse_reminder_time,
    convert_units, convert_currency, translate_text, read_pdf,
)
from youtube_player import play_on_youtube, stop_youtube
from brain import ask as llm_ask


QUIET_PREFIX = "__QUIET__"

STOP_MUSIC_PHRASES = {
    "stop",
    "stop music",
    "stop the music",
    "stop playing",
    "stop youtube",
    "stop the song",
    "stop the song please",
    "kill the music",
    "pause the music",
    "pause music",
    "shut the music",
    "stop the audio",
}


def _stop_all_music() -> str:
    """Stop YouTube (mpv) and pause Spotify, whichever is playing."""
    stopped_anything = False

    # Stop YouTube
    try:
        result = stop_youtube()
        if "Nothing is playing" not in result:
            stopped_anything = True
    except Exception:
        pass

    # Pause Spotify
    try:
        sp = get_spotify_client()
        if sp is not None:
            sp.pause_playback()
            stopped_anything = True
    except Exception:
        pass

    if stopped_anything:
        return "Music stopped."
    return "Nothing is playing."


def execute_tool(name: str, args: dict) -> str:
    """Route LLM tool calls to the actual Python functions."""
    args = args or {}
    try:
        # Music
        if name == "play_on_youtube":
            return play_on_youtube(args["query"])
        if name == "stop_youtube":
            return _stop_all_music()
        if name == "play_on_spotify":
            return play_on_spotify(args["query"])

        # Info tools
        if name == "get_weather":
            return get_weather(args["city"])
        if name == "search_web":
            return search_web(args["query"])
        if name == "search_wikipedia":
            return search_wikipedia(args["query"])
        if name == "calculate":
            return calculate(args["expression"])
        if name == "get_time":
            return get_time()
        if name == "get_date":
            return get_date()
        if name == "get_system_info":
            return get_system_info()
        if name == "get_ip":
            return get_ip()
        if name == "search_news":
            return search_news(args["query"])

        # Launchers
        if name == "open_app":
            return open_app(args["app_name"])
        if name == "open_website":
            return open_website(args["site"])

        # Productivity
        if name == "take_screenshot":
            return take_screenshot()
        if name == "send_email":
            return send_email(args["to"], args["subject"], args["body"])
        if name == "translate_text":
            return translate_text(args["text"], args["target_lang"])
        if name == "convert_currency":
            return convert_currency(args["query"])
        if name == "convert_units":
            return convert_units(args["query"])
        if name == "set_reminder":
            return set_reminder(args["seconds"], args["message"], speak_fn=speak)

        # Utilities
        if name == "flip_coin":
            return flip_coin()
        if name == "roll_dice":
            return roll_dice()
        if name == "morning_briefing":
            return morning_briefing()
        if name == "read_notes":
            return read_notes()
        if name == "take_note":
            return take_note(args["text"])

        return f"Unknown tool: {name}"
    except KeyError as e:
        return f"Missing argument: {e}"
    except Exception as e:
        return f"Tool error: {e}"


def think(user_text: str) -> str:
    text = user_text.lower().strip()

    # ---- Fast path: stop music (no LLM needed) ----
    if text in STOP_MUSIC_PHRASES:
        return _stop_all_music()

    # ---- Fast path: memory commands ----
    if any(p in text for p in ["what did i just ask", "repeat my question"]):
        return recall_last_question()
    if any(p in text for p in ["what did you just say", "repeat that", "say that again"]):
        return recall_last_reply()
    if any(p in text for p in ["clear history", "clear memory", "forget everything"]):
        return clear_memory()

    # Everything else goes through the LLM
    return llm_ask(user_text, execute_tool)


def handle_reply(reply: str) -> None:
    if reply.startswith(QUIET_PREFIX):
        speak(reply[len(QUIET_PREFIX):], quiet=True)
    else:
        speak(reply)


def main():
    speak("JARVIS online. Type a message, or type 'voice' to speak.")
    input_handler.start()
    try:
        while True:
            item = input_handler.get()
            if item is None:
                continue
            source, text = item
            if source == "voice":
                speak("Listening...")
                user_text = listen_voice()
            else:
                print(f"You (typed): {text}")
                user_text = text
            if not user_text:
                continue
            if any(w in user_text.lower() for w in
                   ["exit", "goodbye", "shut down", "quit"]):
                speak("Shutting down.")
                break
            reply = think(user_text)
            remember(user_text, reply)
            handle_reply(reply)
    except KeyboardInterrupt:
        speak("Interrupted. Goodbye.")
    finally:
        input_handler.stop()


if __name__ == "__main__":
    main()