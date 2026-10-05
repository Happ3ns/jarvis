"""All JARVIS tools — one function each."""

import os
import subprocess
import webbrowser
import threading
import random
import requests
from datetime import datetime
from pathlib import Path


# ---------- Info tools ----------

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
        parts.append(f"CPU at {psutil.cpu_percent(interval=0.5)}%")
        parts.append(f"RAM at {psutil.virtual_memory().percent}%")
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


# ---------- Launcher tools ----------

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


# ---------- Wikipedia ----------

def search_wikipedia(query: str) -> str:
    from urllib.parse import quote
    headers = {"User-Agent": "JARVIS/0.1 (personal voice assistant)"}
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
        print(f"[Spotify search: '{query}']")
        results = sp.search(q=query, limit=5, type="track", market="IN")
        items = results["tracks"]["items"]

        if items:
            # Pick the most popular match — this is usually the original song
            items = sorted(items, key=lambda t: t.get("popularity", 0), reverse=True)

        if not items:
            return f"Couldn't find {query} on Spotify."

        track = items[0]
        uri = track["uri"]
        name = track["name"]
        artist = track["artists"][0]["name"]

        devices = sp.devices().get("devices", [])

        def is_browser(d):
            n = d.get("name", "").lower()
            return any(b in n for b in
                       ["chrome", "edge", "firefox", "brave", "opera",
                        "web player", "safari"])

        def usable(d):
            n = d.get("name", "").lower()
            if "echo" in n or "alexa" in n or "_amzn_" in d.get("id", ""):
                return False
            return True

        # Always target the browser web player
        chosen = next((d for d in devices if is_browser(d) and usable(d)), None)

        if chosen is None:
            return ("Open open.spotify.com in Chrome first, play any song "
                    "for 3 seconds, pause it, then try again.")

        device_id = chosen["id"]
        print(f"[Using device: {chosen.get('name', 'unknown')}]")

        try:
            sp.transfer_playback(device_id, force_play=False)
        except Exception as e:
            print(f"[transfer warning: {e}]")

        sp.start_playback(device_id=device_id, uris=[uri])
        return f"Playing {name} by {artist}."
    except Exception as e:
        return f"Spotify error: {e}"


# ---------- Calculator ----------

def calculate(expression: str) -> str:
    import re
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
    expr = expr.strip(" ?.!,")
    if not re.fullmatch(r"[0-9+\-*/(). %]+", expr):
        return "That calculation has characters I can't handle."
    try:
        result = eval(expr, {"__builtins__": {}}, {})
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"That's {result}."
    except ZeroDivisionError:
        return "You can't divide by zero."
    except Exception:
        return "I couldn't parse that math."


# ---------- Utilities ----------

_timers = []


def set_timer(seconds: int, label: str = "timer") -> str:
    def _ring():
        import time
        time.sleep(seconds)
        try:
            from voice import speak as _speak
            _speak(f"Your {label} is up.")
        except Exception:
            print(f"Timer up: {label}")
    t = threading.Thread(target=_ring, daemon=True)
    t.start()
    _timers.append(t)
    if seconds >= 60:
        mins = seconds // 60
        return f"Timer set for {mins} minute{'s' if mins != 1 else ''}."
    return f"Timer set for {seconds} seconds."


def take_note(text: str) -> str:
    try:
        NOTES_FILE = Path("notes.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with NOTES_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {text}\n")
        return "Note saved."
    except Exception as e:
        return f"Couldn't save note: {e}"


def read_notes() -> str:
    NOTES_FILE = Path("notes.txt")
    if not NOTES_FILE.exists() or NOTES_FILE.stat().st_size == 0:
        return "You don't have any notes yet."
    lines = NOTES_FILE.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-3:]
    count = len(lines)
    summary = " | ".join(recent)
    return f"You have {count} note{'s' if count != 1 else ''}. Most recent: {summary}"


def flip_coin() -> str:
    return f"It landed on {random.choice(['heads', 'tails'])}."


def roll_dice(sides: int = 6) -> str:
    return f"You rolled a {random.randint(1, sides)}."