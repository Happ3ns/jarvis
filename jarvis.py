"""JARVIS — voice assistant entry point with streaming responses.

Run with: python jarvis.py
"""
import memory
import slash_commands
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
from screen_vision import (
    analyze_screen, read_screen_text, explain_screen_error, translate_screen,
)
from document_rag import index_folder, ask_documents, clear_index
from brain import ask_stream


QUIET_PREFIX = "__QUIET__"

STOP_MUSIC_PHRASES = {
    "stop", "stop music", "stop the music", "stop playing",
    "stop youtube", "stop the song", "stop the song please",
    "kill the music", "pause the music", "pause music",
    "shut the music", "stop the audio",
}


def _stop_all_music() -> str:
    stopped_anything = False
    try:
        result = stop_youtube()
        if "Nothing is playing" not in result:
            stopped_anything = True
    except Exception:
        pass
    try:
        sp = get_spotify_client()
        if sp is not None:
            sp.pause_playback()
            stopped_anything = True
    except Exception:
        pass
    return "Music stopped." if stopped_anything else "Nothing is playing."


def execute_tool(name: str, args: dict) -> str:
    args = args or {}
    try:
        # Vision
        if name == "analyze_screen":
            return analyze_screen(args.get("question", "What's on this screen? Be brief."))
        if name == "read_screen_text":
            return read_screen_text()
        if name == "explain_screen_error":
            return explain_screen_error()
        if name == "translate_screen":
            return translate_screen(args.get("target_lang", "English"))

        # RAG
        if name == "index_folder":
            return index_folder(args["folder_path"])
        if name == "ask_documents":
            return ask_documents(args["question"])
        if name == "clear_index":
            return clear_index()
        # Long-term memory
        if name == "remember_fact":
            return memory.remember_fact(args["text"])
        if name == "recall_facts":
            return memory.get_all_facts()
        if name == "forget_fact":
            return memory.forget_fact(args["text"])
        if name == "search_past_conversations":
            return memory.search_conversations(args["query"])
        if name == "get_conversations_on":
            return memory.get_conversations_on(args["date"])
        if name == "get_recent_conversations":
            return memory.get_recent_conversations(5)
        if name == "memory_stats":
            return memory.get_stats()
        if name == "clear_all_facts":
            return memory.clear_all_facts()
        # Music
        if name == "play_on_youtube":
            return play_on_youtube(args["query"])
        if name == "stop_youtube":
            return _stop_all_music()
        if name == "play_on_spotify":
            return play_on_spotify(args["query"])

        # Info
        if name == "get_weather":
            return get_weather(args.get("city", "Kanpur"))
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


def think_stream(user_text: str):
    """Yield (kind, text) tuples for a user command."""
    # ---- Slash command handling ----
    if slash_commands.is_clear(user_text):
        yield ("content", "__CLEAR__")
        return

    if slash_commands.is_help(user_text):
        yield ("content", slash_commands.get_help())
        return

    if slash_commands.is_stop(user_text):
        yield ("content", _stop_all_music())
        return

    # Expand /shortcut → full command before anything else
    user_text = slash_commands.expand(user_text)

    text = user_text.lower().strip()

    # Fast-path: stop music (plain text form)
    if text in STOP_MUSIC_PHRASES:
        yield ("content", _stop_all_music())
        return

    # Fast-path: memory commands
    if any(p in text for p in ["what did i just ask", "repeat my question"]):
        yield ("content", recall_last_question())
        return
    if any(p in text for p in ["what did you just say", "repeat that", "say that again"]):
        yield ("content", recall_last_reply())
        return
    if any(p in text for p in ["clear history", "clear memory", "forget everything"]):
        yield ("content", clear_memory())
        return

    # LLM streaming
    yield from ask_stream(user_text, execute_tool)


def think(user_text: str) -> str:
    """Non-streaming compatibility wrapper for app.py."""
    full = ""
    for kind, chunk in think_stream(user_text):
        if kind == "content":
            full += chunk
    return full


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
                print(f"\nYou (typed): {text}")
                user_text = text

            if not user_text:
                continue

            if any(w in user_text.lower() for w in
                   ["exit", "goodbye", "shut down", "quit"]):
                speak("Shutting down.")
                break

            # Stream the reply to the terminal
            full_reply = ""
            print("JARVIS: ", end="", flush=True)
            for kind, chunk in think_stream(user_text):
                if kind == "content":
                    print(chunk, end="", flush=True)
                    full_reply += chunk
                elif kind == "status":
                    print(f"\n  {chunk}", end="", flush=True)
            print()

            remember(user_text, full_reply)
            
            memory.log_conversation(user_text, full_reply)   # <-- new line
            if not full_reply.startswith(QUIET_PREFIX):
                speak(full_reply)

    except KeyboardInterrupt:
        speak("Interrupted. Goodbye.")
    finally:
        input_handler.stop()


if __name__ == "__main__":
    main()