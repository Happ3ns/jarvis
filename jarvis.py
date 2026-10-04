import sounddevice as sd
import numpy as np
import whisper
import pyttsx3
import requests
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
    """Fetch current weather for a city via open-meteo (no API key needed)."""
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
        audio,
        fp16=False,
        language="en",
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
    )
    text = result["text"].strip()
    print(f"You (voice): {text}")
    return text


def listen() -> str:
    """Type a message, or press Enter to use voice."""
    typed = input("\n[Type a message, or press Enter to speak]: ").strip()
    if typed:
        print(f"You (typed): {typed}")
        return typed
    return listen_voice()


# ---------- Brain (temporary — swaps to Claude on Oct 22) ----------

def think(user_text: str) -> str:
    text = user_text.lower()

    if "weather" in text:
        words = user_text.split()
        for i, w in enumerate(words):
            if w.lower() in ("in", "for") and i + 1 < len(words):
                return get_weather(words[i + 1].strip("?.!,"))
        return get_weather("Kanpur")

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