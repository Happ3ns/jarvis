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
    """Record from mic and transcribe."""
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


def think(user_text: str) -> str:
    return f"I heard you say: {user_text}. My brain isn't connected yet."


def speak(text: str) -> None:
    print(f"JARVIS: {text}")
    tts.say(text)
    tts.runAndWait()


def main():
    speak("JARVIS online.")
    try:
        while True:
            user_text = listen()
            if not user_text:
                continue
            if any(w in user_text.lower() for w in ["exit", "goodbye", "shut down", "stop", "quit"]):
                speak("Shutting down.")
                break
            reply = think(user_text)
            speak(reply)
    except KeyboardInterrupt:
        speak("Interrupted. Goodbye.")


if __name__ == "__main__":
    main()