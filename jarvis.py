"""JARVIS — voice assistant entry point.

Run with: python jarvis.py

Type a message and press Enter, or type 'voice' to speak.
"""

import re

import input_handler
from voice import listen_voice, speak
from tools import (
    get_weather, get_time, get_date, get_system_info, get_ip,
    open_app, open_website,
    search_wikipedia, random_wikipedia,
    play_on_spotify,
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
    recall_recent, set_reminder, list_reminders, parse_reminder_time,
    convert_units, convert_currency, translate_text, read_pdf,
)


QUIET_PREFIX = "__QUIET__"


def _handle_email(user_text: str) -> str:
    """Parse 'send email to X about Y saying Z' or 'email X'."""
    text = user_text.lower().strip()

    # Extract recipient
    to = None
    for prefix in ["send email to ", "send an email to ", "email "]:
        if text.startswith(prefix):
            rest = user_text[len(prefix):]
            for delim in [" about ", " saying ", " with "]:
                if delim in rest.lower():
                    idx = rest.lower().index(delim)
                    to = rest[:idx].strip()
                    break
            if to is None:
                to = rest.strip()
            break

    if not to:
        return "Who should I email?"

    # Extract body
    body = "This is a test message from JARVIS."
    for delim in [" saying ", " with message ", " body "]:
        if delim in user_text.lower():
            idx = user_text.lower().index(delim)
            body = user_text[idx + len(delim):].strip()
            break

    # Extract subject
    subject = "Message from JARVIS"
    if " about " in user_text.lower():
        idx = user_text.lower().index(" about ")
        rest = user_text[idx + len(" about "):]
        for delim in [" saying ", " with message "]:
            if delim in rest.lower():
                subject = rest[:rest.lower().index(delim)].strip()
                break
        else:
            subject = rest.strip()

    return send_email(to, subject, body)


def think(user_text: str) -> str:
    text = user_text.lower().strip()

    # ============================================================
    # CONVERSATION MEMORY
    # ============================================================
    if any(p in text for p in ["what did i just ask", "what did i ask",
                                "repeat my question"]):
        return recall_last_question()

    if any(p in text for p in ["what did you just say", "repeat that",
                                "say that again", "what did you say"]):
        return recall_last_reply()

    if any(p in text for p in ["what have we talked about", "conversation history",
                                "recent conversation", "what did we discuss"]):
        return recall_recent(3)

    if any(p in text for p in ["clear history", "clear memory", "forget everything",
                                "forget our conversation"]):
        return clear_memory()

    # ============================================================
    # REMINDERS
    # ============================================================
    if any(p in text for p in ["remind me", "set a reminder", "put a reminder",
                                "make a reminder", "create a reminder",
                                "reminder to", "add a reminder"]):
        seconds, _ = parse_reminder_time(user_text)
        if seconds is None:
            return "When should I remind you? Try 'remind me in 10 minutes to...'"

        message = None
        for marker in [" to ", " that ", " about "]:
            if marker in user_text:
                idx = user_text.lower().index(marker)
                message = user_text[idx + len(marker):].strip()
                break
        if not message:
            message = "something"

        return set_reminder(seconds, message, speak_fn=speak)

    if any(p in text for p in ["what reminders", "list reminders", "my reminders"]):
        return list_reminders()

    # ============================================================
    # PDF READER
    # ============================================================
    if "read the pdf" in text or "read pdf" in text or \
       ("read" in text and "pdf" in text):
        m = re.search(r"(?:pdf|file)\s+(?:at\s+)?(.+)$", user_text, re.IGNORECASE)
        if m:
            path = m.group(1).strip().strip('"').strip("'")
            return read_pdf(path)
        return "Give me the full path to the PDF."

    # ============================================================
    # TRANSLATION
    # ============================================================
    if text.startswith("translate ") or any(
        f" in {lang}" in text for lang in [
            "spanish", "french", "german", "hindi", "japanese",
            "chinese", "korean", "russian", "arabic", "italian",
            "portuguese", "dutch", "turkish", "bengali", "tamil",
        ]
    ):
        # "translate X to Y" or "translate X into Y"
        m = re.search(r"translate\s+(.+?)\s+(?:to|into)\s+([a-zA-Z]+)",
                      user_text, re.IGNORECASE)
        if m:
            phrase = m.group(1).strip()
            lang = m.group(2).strip()
            result = translate_text(phrase, lang)
            return f"In {lang}: {result}"

        # "how do you say X in Y" or "say X in Y"
        m = re.search(r"(?:how do you say|say)\s+(.+?)\s+in\s+([a-zA-Z]+)",
                      user_text, re.IGNORECASE)
        if m:
            phrase = m.group(1).strip()
            lang = m.group(2).strip()
            result = translate_text(phrase, lang)
            return f"In {lang}: {result}"

    # ============================================================
    # CURRENCY CONVERSION
    # ============================================================
    currency_codes = [" usd ", " inr ", " eur ", " gbp ", " jpy ",
                      " aud ", " cad ", " chf ", " cny ", " sgd ",
                      " aed ", " rub ", " krw "]
    if any(cur in f" {text} " for cur in currency_codes):
        result = convert_currency(user_text)
        if result:
            return result

    # ============================================================
    # UNIT CONVERSION
    # ============================================================
    if (text.startswith("convert ") or "how many " in text or
        " km to " in text or " miles " in text or
        " celsius " in text or " fahrenheit " in text or
        " kg to " in text or " lbs " in text):
        result = convert_units(user_text)
        if result:
            return result

    # ============================================================
    # MORNING BRIEFING
    # ============================================================
    if any(p in text for p in ["morning briefing", "brief me", "daily briefing"]):
        return morning_briefing()

    # ============================================================
    # EMAIL
    # ============================================================
    if (text.startswith("send email to ") or
        text.startswith("send an email to ") or
        text.startswith("email ") or
        "send an email" in text):
        return _handle_email(user_text)

    # ============================================================
    # SCREENSHOT
    # ============================================================
    if any(p in text for p in ["take a screenshot", "capture screen", "screenshot"]):
        return take_screenshot()

    # ============================================================
    # CLIPBOARD
    # ============================================================
    if any(p in text for p in ["read my clipboard", "what's on my clipboard",
                                "clipboard contents"]):
        return get_clipboard()

    if text.startswith("copy ") or "copy this to clipboard" in text:
        content = user_text
        for prefix in ["copy this to clipboard", "copy "]:
            if content.lower().startswith(prefix):
                content = content[len(prefix):]
                break
        content = content.strip("?:.!,").strip()
        if content:
            return set_clipboard(content)
        return "What should I copy?"

    # ============================================================
    # FILE SEARCH
    # ============================================================
    if text.startswith("find file ") or (text.startswith("find ") and "file" in text):
        query = text
        for prefix in ["find file", "find"]:
            if query.startswith(prefix):
                query = query[len(prefix):]
                break
        query = query.replace("file", "", 1).strip()
        if query:
            return find_file(query)
        return "What file should I look for?"

    if text.startswith("open file "):
        path = user_text[len("open file "):].strip()
        return open_file(path)

    # ============================================================
    # NOTES
    # ============================================================
    if text.startswith("take a note") or text.startswith("note this"):
        note = user_text
        for prefix in ["take a note:", "take a note", "note this:", "note this"]:
            if note.lower().startswith(prefix):
                note = note[len(prefix):].strip()
                break
        if note:
            return take_note(note)
        return "What should I note?"

    if "read my notes" in text or "my notes" in text:
        return read_notes()

    # ============================================================
    # TIMER
    # ============================================================
    if "set a timer" in text or "set timer" in text:
        m = re.search(r"(\d+)\s*(second|minute|hour)s?", text)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            seconds = n * {"second": 1, "minute": 60, "hour": 3600}[unit]
            return set_timer(seconds, f"{n} {unit} timer")
        return "How long should the timer be?"

    # ============================================================
    # SYSTEM INFO
    # ============================================================
    if any(w in text for w in ["battery", "system info", "cpu",
                                "ram usage", "memory usage"]):
        return get_system_info()
    if "ip address" in text or "my ip" in text or "public ip" in text:
        return get_ip()

    # ============================================================
    # COIN / DICE
    # ============================================================
    if any(p in text for p in ["flip a coin", "toss a coin", "heads or tails"]):
        return flip_coin()
    if any(p in text for p in ["roll a dice", "roll a die", "roll dice"]):
        return roll_dice()

    # ============================================================
    # RANDOM WIKIPEDIA
    # ============================================================
    if any(p in text for p in ["random fact", "something random", "random article"]):
        return random_wikipedia()

    # ============================================================
    # WEB SEARCH
    # ============================================================
    if text.startswith("search for ") or text.startswith("search "):
        query = text
        for prefix in ["search for ", "search "]:
            if query.startswith(prefix):
                query = query[len(prefix):]
                break
        query = query.strip()
        if query:
            return search_web(query)

    if "search the web for " in text or "look up " in text:
        query = user_text
        for prefix in ["search the web for", "look up"]:
            if prefix in query.lower():
                idx = query.lower().index(prefix)
                query = query[idx + len(prefix):].strip()
                break
        if query:
            return search_web(query)

    if any(p in text for p in ["latest news", "recent news", "news about"]):
        query = text
        for prefix in ["latest news about", "recent news about", "news about",
                       "latest news", "recent news"]:
            query = query.replace(prefix, "", 1)
        query = query.strip("?.!,")
        return search_news(query if query else "India")

    # ============================================================
    # CALCULATOR
    # ============================================================
    calc_triggers = ["what's", "whats", "what is", "calculate",
                     "how much is", "compute"]
    has_trigger = any(text.startswith(t) for t in calc_triggers)
    has_digit = any(c.isdigit() for c in text)
    has_op = any(op in text for op in ["+", "-", "*", "/", "plus", "minus",
                                       "times", "multiplied", "divided",
                                       "over", "power"])
    if has_trigger and has_digit and has_op:
        expr = text
        for prefix in calc_triggers:
            if expr.startswith(prefix):
                expr = expr[len(prefix):].strip()
                break
        return calculate(expr)

    # ============================================================
    # SPOTIFY
    # ============================================================
    if text.startswith("play ") and len(text) > 5:
        query = text.replace("play", "", 1).replace("on spotify", "").strip()
        if query and query not in ("music", "a song", "something", "spotify"):
            result = play_on_spotify(query)
            if result.startswith("Playing "):
                return QUIET_PREFIX + result
            return result

    # ============================================================
    # OPEN APP / WEBSITE
    # ============================================================
    if text.startswith("open ") or "open up" in text:
        target = text.replace("open up", "", 1).replace("open", "", 1).strip()
        apps_known = ["spotify", "chrome", "edge", "notepad", "calculator",
                      "explorer", "cmd", "vscode"]
        if any(a in target for a in apps_known):
            return open_app(target)
        return open_website(target)

    # ============================================================
    # WIKIPEDIA
    # ============================================================
    if "wikipedia" in text or text.startswith("who is ") or \
       text.startswith("what is "):
        query = user_text
        for prefix in ["wikipedia", "who is", "what is", "tell me about"]:
            query = query.lower().replace(prefix, "", 1)
        query = query.strip("?.!,")
        if query:
            return search_wikipedia(query)

    # ============================================================
    # WEATHER
    # ============================================================
    if "weather" in text:
        words = user_text.split()
        for i, w in enumerate(words):
            if w.lower() in ("in", "for") and i + 1 < len(words):
                return get_weather(words[i + 1].strip("?.!,"))
        return get_weather("Kanpur")

    # ============================================================
    # TIME / DATE
    # ============================================================
    if re.search(r"\btime\b", text) and "timer" not in text:
        return get_time()
    if re.search(r"\bdate\b", text) or re.search(r"\bday\b", text):
        return get_date()

    return f"I heard you say: {user_text}. I don't have a tool for that yet."


def handle_reply(reply: str) -> None:
    """Speak or print based on whether the reply is marked quiet."""
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