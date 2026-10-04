import sounddevice as sd
import numpy as np
import whisper
import pyttsx3
import requests
import subprocess
import os
import webbrowser
from datetime import datetime

SAMPLE_RATE = 16000
DEVICE = 11
DURATION = 5

print("Loading Whisper...")
whisper_model = whisper.load_model("base")
tts = pyttsx3.init()
tts.setProperty("rate", 175)

for v in tts.getProperty("voices"):
    if "David" in v.name or "Mark" in v.name:
        tts.setProperty("voice", v.id)
        break


# ---------- Tools ----------

def get_weather(city: str) -> str:
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=5,
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
        "spotify":  os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        "chrome":   r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "edge":     r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "notepad":  "notepad.exe",
        "calculator": "calc.exe",
        "explorer": "explorer.exe",
        "cmd":      "cmd.exe",
        "vscode":   os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
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
    """Fetch a short summary of a Wikipedia article."""
    from urllib.parse import quote

    headers = {
        "User-Agent": "JARVIS/0.1 (personal voice assistant; contact: akshatkharkwal39@gmail.com)"
    }

    try:
        # Find the top matching article titles
        search = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "opensearch",
                "search": query,
                "limit": 5,           # grab a few, not just one
                "format": "json",
            },
            headers=headers,
            timeout=5,
        ).json()

        candidates = search[1]
        if not candidates:
            return f"I couldn't find a Wikipedia article for {query}."

        # Try each candidate until we find one that isn't a disambiguation page
        for title in candidates:
            summary = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
                headers=headers,
                timeout=5,
            ).json()

            if summary.get("type") == "disambiguation":
                continue  # skip and try the next one

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
    """Open a website in the default browser."""
    # Common site shortcuts
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

    # If it's a known shortcut, use it
    if name in shortcuts:
        webbrowser.open(shortcuts[name])
        return f"Opening {site}."

    # Otherwise, try to construct a URL
    if "." in name:
        url = name if name.startswith("http") else f"https://{name}"
        webbrowser.open(url)
        return f"Opening {site}."

    # Fall back to a Google search for unknown names
    webbrowser.open(f"https://www.google.com/search?q={site}")
    return f"I didn't recognize {site}, so I searched for it on Google."


# ---------- Spotify (needs setup — see README) ----------

_spotify_client = None

def get_spotify_client():
    """Lazy-init Spotify client. Returns None if not configured."""
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

        # Find a usable device — skip Echo/Alexa, prefer active
        devices = sp.devices().get("devices", [])

        def usable(d):
            """Echo dots have buggy IDs that return 404."""
            name = d.get("name", "").lower()
            if "echo" in name or "alexa" in name or "_amzn_" in d.get("id", ""):
                return False
            return True

        # Prefer an active device
        chosen = next((d for d in devices if d.get("is_active") and usable(d)), None)

        # Fall back to any non-Echo device
        if chosen is None:
            chosen = next((d for d in devices if usable(d)), None)

        # If nothing usable, launch Spotify desktop and wait
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
                return ("No playable Spotify device found. Open the Spotify "
                        "desktop app manually first, then try again.")

        device_id = chosen["id"]
        device_name = chosen.get("name", "unknown")
        print(f"[Using device: {device_name}]")

        # Ensure this device is active before playing
        try:
            sp.transfer_playback(device_id, force_play=False)
            time.sleep(0.5)
        except Exception as e:
            print(f"[Transfer warning: {e}]")

        sp.start_playback(device_id=device_id, uris=[uri])
        return f"Playing {name} by {artist}."

    except Exception as e:
        return f"Spotify error: {e}"

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
    text = user_text.lower()

    # Spotify playback (check before generic "open")
    if "play" in text and "spotify" not in text.replace("on spotify", ""):
        # "play X on spotify" or "play X"
        query = text.replace("play", "").replace("on spotify", "").strip()
        if query:
            return play_on_spotify(query)

    # Open app
    if text.startswith("open ") or "open up" in text:
        target = text.replace("open up", "").replace("open", "").strip()
        # Is it an app or a website?
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
                return get_weather(words[i + 1].strip("?.!,"))
        return get_weather("Kanpur")

    # Time / date
    if "time" in text:
        return get_time()
    if "date" in text or "day" in text:
        return get_date()

    return f"I heard you say: {user_text}. I don't have a tool for that yet."


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