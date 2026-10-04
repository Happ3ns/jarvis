"""Voice I/O — listening (Whisper) and speaking (pyttsx3)."""

import sounddevice as sd
import numpy as np
import whisper
import pyttsx3

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


def speak(text: str) -> None:
    print(f"JARVIS: {text}")
    tts.say(text)
    tts.runAndWait()
