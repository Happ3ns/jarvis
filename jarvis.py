"""JARVIS — voice assistant entry point with streaming responses.

Run with: python jarvis.py
"""
from code_runner import run_code, compute, analyze_file
import browser_control
import memory
import time
import tool_stats
import lessons
import self_extension
import agents
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
    """Route LLM tool calls to the actual Python functions."""
    args = args or {}
    start = time.time()
    success = False
    try:
        result = _execute_tool_inner(name, args)
        success = True
        return result
    except Exception as e:
        result = f"Tool error: {e}"
        return result
    finally:
        duration = time.time() - start
        tool_stats.record(name, success, duration)
        # If failed, save a lesson automatically
        if not success:
            try:
                context = f"{name}({list(args.keys())})"
                lesson = f"Tool failed: {str(args)[:100]}"
                lessons.record_lesson(context, lesson)
            except Exception:
                pass


def _execute_tool_inner(name: str, args: dict) -> str:
    """Actual dispatcher — wrapped by execute_tool for stats."""
    try:
        if name == "run_experiment":
            import experiment
            return experiment.experiment_run(args["question"])
        if name == "list_experiments":
            import experiment
            return experiment.experiment_list()
        if name == "show_experiment":
            import experiment
            return experiment.experiment_show(args["experiment_id"])
                # Scheduled tasks
        if name == "schedule_task":
            import tasks
            return tasks.add_scheduled(
                args["name"], args["schedule"], args["action"]
            )
        if name == "watch_for":
            import tasks
            return tasks.add_watcher(
                args["name"], args["check_code"], args["action"]
            )
        if name == "list_scheduled_tasks":
            import tasks
            return tasks.list_tasks()
        if name == "delete_scheduled_task":
            import tasks
            return tasks.delete(int(args["id"]))
        
                # Self-extension
        if name == "create_tool":
            return self_extension.create_tool(
                name=args["name"],
                description=args["description"],
                code=args["code"],
                parameters=args["parameters"],
                test_code=args["test_code"],
            )
        if name == "run_experiment":
            import experiment
            return experiment.experiment_run(args["question"])
        if name == "list_experiments":
            import experiment
            return experiment.experiment_list()
        if name == "show_experiment":
           import experiment
           return experiment.experiment_show(args["experiment_id"])

        # Dispatch to learned tools
        learned = self_extension.load_learned_tools()
        if name in learned:
            try:
                return str(learned[name](**args))
            except Exception as e:
                return f"Tool '{name}' error: {e}"
        if name == "spawn_agents":
            return agents.spawn_agents(args["tasks"], execute_tool)
        if name == "list_agent_roles":
            return agents.list_roles()
                # Browser automation
        if name == "open_url":
            return browser_control.open_url(args["url"])
        if name == "search_youtube":
            return browser_control.search_youtube(args["query"])
        if name == "search_google":
            return browser_control.search_google(args["query"])
        if name == "get_page_text":
            return browser_control.get_page_text()
        if name == "click_element":
            return browser_control.click_element(args["text"])
        if name == "type_into":
            return browser_control.type_into(args["selector"], args["text"], args.get("submit", False))
        if name == "run_browser_code":
            return browser_control.run_browser_code(args["code"])
        if name == "close_browser":
            return browser_control.close_browser()
        
        # Vision
        if name == "analyze_screen":
            return analyze_screen(args.get("question", "What's on this screen? Be brief."))
        if name == "read_screen_text":
            return read_screen_text()
        if name == "explain_screen_error":
            return explain_screen_error()
        if name == "translate_screen":
            return translate_screen(args.get("target_lang", "English"))
        
        if name == "run_code":
            return run_code(args["code"])
        if name == "compute":
            return compute(args["expression"])
        if name == "analyze_file":
            return analyze_file(args["path"], args.get("question", "describe this file"))
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
            city = args.get("city") or "Kanpur"
            return get_weather(city)
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
        if name == "open_file_in_editor":
            return open_file_in_editor(args["path"], args.get("line"))

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
    # ---- Learned-tool management (/tools, /learned X, /forget-tool X) ----
        # ---- Learned-tool management (/tools, /learned X, /forget-tool X) ----
    special = slash_commands.handle_special_commands(user_text)
    if special is not None:
        yield ("content", QUIET_PREFIX + special)
        return

    # ---- Slash command handling ----
    if slash_commands.is_clear(user_text):
        yield ("content", QUIET_PREFIX + "__CLEAR__")
        return

    if slash_commands.is_help(user_text):
        yield ("content", QUIET_PREFIX + slash_commands.get_help())
        return

    if slash_commands.is_stop(user_text):
        yield ("content", QUIET_PREFIX + _stop_all_music())
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
        try:
            browser_control.close_browser()
        except Exception:
            pass


if __name__ == "__main__":
    main()