import sounddevice as sd
import numpy as np
import whisper
import pyttsx3
import requests
import subprocess
import os
import webbrowser
import threading
import random
from datetime import datetime, timedelta
from pathlib import Path

SAMPLE_RATE = 16000
DEVICE = 11
DURATION = 5

NOTES_FILE = Path("notes.txt")

print("Loading Whisper...")
whisper_model = whisper.load_model("base")
tts = pyttsx3.init()
tts.setProperty("rate", 175)

for v in tts.getProperty("voices"):
    if "David" in v.name or "Mark" in v.name:
        tts.setProperty("voice", v.id)
        break


# ---------- Existing Tools ----------

def get_weather(city: str) -> str:
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1}, timeout=5,
        ).json()
        if not geo.get("results"):
            return f"I couldn't find {city}."
        lat = geo["results"][0]["latitude"]
        lon = geo["results"][0]["longitude"]
        name = geo["results"][0]["name"]
        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            timeout=5,
        ).json()
        cw = weather["current_weather"]
        return f"{name} is {cw['temperature']}°C with wind at {cw['windspeed']} km/h."
    except Exception as e:
        return f"Sorry, I couldn't fetch the weather. Error: {e}"


def get_time() -> str:
    return datetime.now().strftime("It's %I:%M %p on %A, %B %d.")


def get_date() -> str:
    return datetime.now().strftime("Today is %A, %B %d, %Y.")


def open_app(app_name: str) -> str:
    apps = {
        "spotify":    os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        "chrome":     r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "edge":       r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "notepad":    "notepad.exe",
        "calculator": "calc.exe",
        "explorer":   "explorer.exe",
        "cmd":        "cmd.exe",
        "vscode":     os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
    }
    name = app_name.lower().strip()
    if name in apps:
        try:
            subprocess.Popen(apps[name])
            return f"Opening {app_name}."
        except FileNotFoundError:
            return f"Found '{app_name}', but the executable isn't at the expected path."
    for key in apps:
        if key in name:
            try:
                subprocess.Popen(apps[key])
                return f"Opening {key}."
            except FileNotFoundError:
                return f"Found '{key}', but the executable isn't at the expected path."
    return f"I don't know how to open {app_name} yet."


def search_wikipedia(query: str) -> str:
    from urllib.parse import quote
    headers = {
        "User-Agent": "JARVIS/0.1 (personal voice assistant; contact: akshatkharkwal39@gmail.com)"
    }
    try:
        search = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "opensearch", "search": query, "limit": 5, "format": "json"},
            headers=headers, timeout=5,
        ).json()
        candidates = search[1]
        if not candidates:
            return f"I couldn't find a Wikipedia article for {query}."
        for title in candidates:
            summary = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
                headers=headers, timeout=5,
            ).json()
            if summary.get("type") == "disambiguation":
                continue
            extract = summary.get("extract", "")
            if extract:
                sentences = extract.split(". ")
                short = ". ".join(sentences[:2]).strip()
                if not short.endswith("."):
                    short += "."
                return f"According to Wikipedia: {short}"
        return f"'{candidates[0]}' is ambiguous — try being more specific."
    except Exception as e:
        return f"Sorry, I couldn't search Wikipedia. Error: {e}"


def open_website(site: str) -> str:
    shortcuts = {
        "youtube": "https://www.youtube.com",
        "gmail":   "https://mail.google.com",
        "github":  "https://github.com",
        "reddit":  "https://www.reddit.com",
        "twitter": "https://twitter.com",
        "x":       "https://x.com",
        "stackoverflow": "https://stackoverflow.com",
        "wikipedia": "https://en.wikipedia.org",
        "google": "https://www.google.com",
    }
    name = site.lower().strip().replace(" ", "")
    if name in shortcuts:
        webbrowser.open(shortcuts[name])
        return f"Opening {site}."
    if "." in name:
        url = name if name.startswith("http") else f"https://{name}"
        webbrowser.open(url)
        return f"Opening {site}."
    webbrowser.open(f"https://www.google.com/search?q={site}")
    return f"I didn't recognize {site}, so I searched for it on Google."


# ---------- Spotify ----------

_spotify_client = None

def get_spotify_client():
    global _spotify_client
    if _spotify_client is not None:
        return _spotify_client
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            print("[Spotify: missing CLIENT_ID or CLIENT_SECRET env vars]")
            return None
        _spotify_client = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri="http://127.0.0.1:8888/callback",
            scope="user-modify-playback-state user-read-playback-state",
        ))
        return _spotify_client
    except Exception as e:
        print(f"[Spotify init failed: {e}]")
        return None


def play_on_spotify(query: str) -> str:
    sp = get_spotify_client()
    if sp is None:
        return "Spotify isn't set up yet."
    try:
        results = sp.search(q=query, limit=1, type="track")
        items = results["tracks"]["items"]
        if not items:
            return f"Couldn't find {query} on Spotify."
        track = items[0]
        uri = track["uri"]
        name = track["name"]
        artist = track["artists"][0]["name"]
        import time
        devices = sp.devices().get("devices", [])

        def usable(d):
            n = d.get("name", "").lower()
            if "echo" in n or "alexa" in n or "_amzn_" in d.get("id", ""):
                return False
            return True

        chosen = next((d for d in devices if d.get("is_active") and usable(d)), None)
        if chosen is None:
            chosen = next((d for d in devices if usable(d)), None)
        if chosen is None:
            print("[No usable device — launching Spotify desktop...]")
            subprocess.Popen(os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"))
            for attempt in range(10):
                time.sleep(2)
                devices = sp.devices().get("devices", [])
                chosen = next((d for d in devices if usable(d)), None)
                if chosen:
                    print(f"[Spotify ready after {(attempt + 1) * 2}s]")
                    break
            if chosen is None:
                return "No playable Spotify device found. Open Spotify manually."
        device_id = chosen["id"]
        print(f"[Using device: {chosen.get('name', 'unknown')}]")
        try:
            sp.transfer_playback(device_id, force_play=False)
            time.sleep(0.5)
        except Exception:
            pass
        sp.start_playback(device_id=device_id, uris=[uri])
        return f"Playing {name} by {artist}."
    except Exception as e:
        return f"Spotify error: {e}"


# ---------- NEW TOOLS ----------

def calculate(expression: str) -> str:
    """Safe math evaluation. Handles +, -, *, /, **, parentheses."""
    import re
    # Normalize spoken math to symbols
    expr = expression.lower()
    replacements = {
        " plus ": " + ",
        " minus ": " - ",
        " times ": " * ",
        " multiplied by ": " * ",
        " divided by ": " / ",
        " over ": " / ",
        " to the power of ": " ** ",
        " squared": " ** 2",
        " cubed": " ** 3",
        " x ": " * ",
    }
    for word, symbol in replacements.items():
        expr = expr.replace(word, symbol)

    # Strip trailing punctuation
    expr = expr.strip(" ?.!,")

    # Allow only safe characters
    if not re.fullmatch(r"[0-9+\-*/(). %]+", expr):
        return "That calculation has characters I can't handle."

    try:
        # Replace % with /100 only if it's a trailing modifier
        result = eval(expr, {"__builtins__": {}}, {})
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"That's {result}."
    except ZeroDivisionError:
        return "You can't divide by zero."
    except Exception:
        return "I couldn't parse that math."


def get_system_info() -> str:
    try:
        import psutil
        battery = psutil.sensors_battery()
        parts = []
        if battery:
            parts.append(f"battery at {int(battery.percent)}%")
            if battery.power_plugged:
                parts.append("plugged in")
            else:
                mins = battery.secsleft // 60 if battery.secsleft > 0 else None
                if mins:
                    parts.append(f"about {mins} minutes left")
        cpu = psutil.cpu_percent(interval=0.5)
        parts.append(f"CPU at {cpu}%")
        ram = psutil.virtual_memory().percent
        parts.append(f"RAM at {ram}%")
        return "Your system: " + ", ".join(parts) + "."
    except ImportError:
        return "Install psutil for system info: pip install psutil"
    except Exception as e:
        return f"System info error: {e}"


def get_ip() -> str:
    try:
        r = requests.get("https://api.ipify.org", timeout=5).text
        return f"Your public IP is {r}."
    except Exception:
        return "Couldn't fetch your IP."


_timers = []

def set_timer(seconds: int, label: str = "timer") -> str:
    def _ring():
        import time
        time.sleep(seconds)
        # Beep via the TTS engine
        speak(f"Your {label} is up.")
    t = threading.Thread(target=_ring, daemon=True)
    t.start()
    _timers.append(t)
    if seconds >= 60:
        mins = seconds // 60
        return f"Timer set for {mins} minute{'s' if mins != 1 else ''}."
    return f"Timer set for {seconds} seconds."


def take_note(text: str) -> str:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with NOTES_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {text}\n")
        return "Note saved."
    except Exception as e:
        return f"Couldn't save note: {e}"


def read_notes() -> str:
    if not NOTES_FILE.exists() or NOTES_FILE.stat().st_size == 0:
        return "You don't have any notes yet."
    lines = NOTES_FILE.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-3:]  # last 3 notes
    count = len(lines)
    summary = " | ".join(recent)
    return f"You have {count} note{'s' if count != 1 else ''}. Most recent: {summary}"


def flip_coin() -> str:
    return f"It landed on {random.choice(['heads', 'tails'])}."


def roll_dice(sides: int = 6) -> str:
    return f"You rolled a {random.randint(1, sides)}."


def random_wikipedia() -> str:
    try:
        r = requests.get(
            "https://en.wikipedia.org/api/rest_v1/page/random/summary",
            headers={"User-Agent": "JARVIS/0.1"},
            timeout=5,
        ).json()
        title = r.get("title", "something")
        extract = r.get("extract", "")
        sentences = extract.split(". ")
        short = ". ".join(sentences[:2]).strip()
        return f"Random article: {title}. {short}"
    except Exception:
        return "Couldn't fetch a random article."


# ---------- Voice I/O ----------

def trim_silence(audio, threshold=0.01):
    mask = np.abs(audio) > threshold
    if not mask.any():
        return audio
    start = np.argmax(mask)
    end = len(audio) - np.argmax(mask[::-1])
    return audio[start:end]


def listen_voice() -> str:
    print("[Listening... speak now]")
    audio = sd.rec(int(DURATION * SAMPLE_RATE),
                   samplerate=SAMPLE_RATE, channels=1,
                   dtype="float32", device=DEVICE)
    sd.wait()
    audio = trim_silence(audio.flatten())
    if len(audio) < SAMPLE_RATE * 0.3:
        print("[Too short — nothing captured]")
        return ""
    result = whisper_model.transcribe(
        audio, fp16=False, language="en",
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
    )
    text = result["text"].strip()
    print(f"You (voice): {text}")
    return text


def listen() -> str:
    typed = input("\n[Type a message, or press Enter to speak]: ").strip()
    if typed:
        print(f"You (typed): {typed}")
        return typed
    return listen_voice()


# ---------- Brain ----------

def think(user_text: str) -> str:
    text = user_text.lower().strip()

    # ---- Notes ----
    if text.startswith("take a note") or text.startswith("note this"):
        note = user_text
        for prefix in ["take a note:", "take a note", "note this:", "note this"]:
            if note.lower().startswith(prefix):
                note = note[len(prefix):].strip()
                break
        if note:
            return take_note(note)
        return "What should I note?"

    if "read my notes" in text or "my notes" in text or "show notes" in text:
        return read_notes()

    # ---- Timer ----
    if "set a timer" in text or "set timer" in text:
        import re
        # Look for "X minute(s)" or "X second(s)" or "X hour(s)"
        m = re.search(r"(\d+)\s*(second|minute|hour)s?", text)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            seconds = n * {"second": 1, "minute": 60, "hour": 3600}[unit]
            return set_timer(seconds, f"{n} {unit} timer")
        return "How long should the timer be?"

    # ---- System info ----
    if any(w in text for w in ["battery", "system info", "cpu", "ram usage", "memory usage"]):
        return get_system_info()
    if "ip address" in text or "my ip" in text or "public ip" in text:
        return get_ip()

    # ---- Coin / dice ----
    if "flip a coin" in text or "toss a coin" in text or "heads or tails" in text:
        return flip_coin()
    if "roll a dice" in text or "roll a die" in text or "roll dice" in text:
        return roll_dice()

    # ---- Random Wikipedia ----
    if "random fact" in text or "something random" in text or "random article" in text:
        return random_wikipedia()

    # ---- Calculator ----
        # ---- Calculator ----
    calc_triggers = ["what's", "whats", "what is", "calculate", "how much is", "compute"]
    has_trigger = any(text.startswith(t) for t in calc_triggers)
    has_digit = any(c.isdigit() for c in text)
    has_op = any(op in text for op in ["+", "-", "*", "/", "plus", "minus", "times", "multiplied", "divided", "over", "power"])
    if has_trigger and has_digit and has_op:
        expr = text
        for prefix in ["what's", "whats", "what is", "calculate", "how much is", "compute"]:
            if expr.startswith(prefix):
                expr = expr[len(prefix):].strip()
                break
        return calculate(expr)

    # ---- Spotify playback ----
    if text.startswith("play ") and len(text) > 5:
        query = text.replace("play", "").replace("on spotify", "").strip()
        if query and query not in ("music", "a song", "something", "spotify"):
            return play_on_spotify(query)

    # ---- Open app or website ----
    if text.startswith("open ") or "open up" in text:
        target = text.replace("open up", "").replace("open", "").strip()
        apps_known = ["spotify", "chrome", "edge", "notepad", "calculator",
                      "explorer", "cmd", "vscode"]
        if any(a in target for a in apps_known):
            return open_app(target)
        return open_website(target)

    # ---- Wikipedia ----
    if "wikipedia" in text or text.startswith("who is ") or text.startswith("what is "):
        query = user_text
        for prefix in ["wikipedia", "who is", "what is", "tell me about"]:
            query = query.lower().replace(prefix, "")
        query = query.strip("?.!,")
        if query:
            return search_wikipedia(query)

    # ---- Weather ----
    if "weather" in text:
        words = user_text.split()
        for i, w in enumerate(words):
            if w.lower() in ("in", "for") and i + 1 < len(words):
                return get_weather(words[i + 1].strip("?.!,"))
        return get_weather("Kanpur")

    # ---- Time / date ----
        # ---- Time / date ----
    # Use word-boundary matching to avoid "times" matching "time"
    import re as _re
    if _re.search(r"\btime\b", text) and "timer" not in text:
        return get_time()
    if _re.search(r"\bdate\b", text) or _re.search(r"\bday\b", text):
        return get_date()


def speak(text: str) -> None:
    print(f"JARVIS: {text}")
    tts.say(text)
    tts.runAndWait()


# ---------- Main loop ----------

def main():
    speak("JARVIS online.")
    try:
        while True:
            user_text = listen()
            if not user_text:
                continue
            if any(w in user_text.lower() for w in
                   ["exit", "goodbye", "shut down", "stop", "quit"]):
                speak("Shutting down.")
                break
            reply = think(user_text)
            speak(reply)
    except KeyboardInterrupt:
        speak("Interrupted. Goodbye.")


if __name__ == "__main__":
    main()