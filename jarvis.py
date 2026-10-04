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


def think(user_text: str) -> str:
    text = user_text.lower().strip()

    # Notes
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

    # Timer
    if "set a timer" in text or "set timer" in text:
        m = re.search(r"(\d+)\s*(second|minute|hour)s?", text)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            seconds = n * {"second": 1, "minute": 60, "hour": 3600}[unit]
            return set_timer(seconds, f"{n} {unit} timer")
        return "How long should the timer be?"

    # System info
    if any(w in text for w in ["battery", "system info", "cpu", "ram usage", "memory usage"]):
        return get_system_info()
    if "ip address" in text or "my ip" in text or "public ip" in text:
        return get_ip()

    # Coin / dice
    if "flip a coin" in text or "toss a coin" in text or "heads or tails" in text:
        return flip_coin()
    if "roll a dice" in text or "roll a die" in text or "roll dice" in text:
        return roll_dice()

    # Random Wikipedia
    if "random fact" in text or "something random" in text or "random article" in text:
        return random_wikipedia()

    # Calculator
    calc_triggers = ["what's", "whats", "what is", "calculate", "how much is", "compute"]
    has_trigger = any(text.startswith(t) for t in calc_triggers)
    has_digit = any(c.isdigit() for c in text)
    has_op = any(op in text for op in ["+", "-", "*", "/", "plus", "minus",
                                       "times", "multiplied", "divided", "over", "power"])
    if has_trigger and has_digit and has_op:
        expr = text
        for prefix in calc_triggers:
            if expr.startswith(prefix):
                expr = expr[len(prefix):].strip()
                break
        return calculate(expr)

    # Spotify
    if text.startswith("play ") and len(text) > 5:
        query = text.replace("play", "").replace("on spotify", "").strip()
        if query and query not in ("music", "a song", "something", "spotify"):
            return play_on_spotify(query)

    # Open app or website
    if text.startswith("open ") or "open up" in text:
        target = text.replace("open up", "").replace("open", "").strip()
        apps_known = ["spotify", "chrome", "edge", "notepad", "calculator",
                      "explorer", "cmd", "vscode"]
        if any(a in target for a in apps_known):
            return open_app(target)
        return open_website(target)

    # Wikipedia
    if "wikipedia" in text or text.startswith("who is ") or text.startswith("what is "):
        query = user_text
        for prefix in ["wikipedia", "who is", "what is", "tell me about"]:
            query = query.lower().replace(prefix, "")
        query = query.strip("?.!,")
        if query:
            return search_wikipedia(query)

    # Weather
    if "weather" in text:
        words = user_text.split()
        for i, w in enumerate(words):
            if w.lower() in ("in", "for") and i + 1 < len(words):
                return get_weather(words[i + 1].strip("?.!,",))
        return get_weather("Kanpur")

    # Time / date — word boundaries matter
    if re.search(r"\btime\b", text) and "timer" not in text:
        return get_time()
    if re.search(r"\bdate\b", text) or re.search(r"\bday\b", text):
        return get_date()

    return f"I heard you say: {user_text}. I don't have a tool for that yet."


def main():
    speak("JARVIS online. Type a message, or type 'voice' to speak.")
    input_handler.start()  # no wake word needed — uses keyboard trigger
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
            speak(reply)

    except KeyboardInterrupt:
        speak("Interrupted. Goodbye.")
    finally:
        input_handler.stop()


if __name__ == "__main__":
    main()