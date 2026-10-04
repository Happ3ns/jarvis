"""Voice I/O — listening (Whisper) and speaking (edge-tts)."""

import asyncio
import os
import tempfile

import sounddevice as sd
import numpy as np
import whisper
import edge_tts

SAMPLE_RATE = 16000
DEVICE = 11
DURATION = 5

# edge-tts voice — en-US-AndrewNeural is rated one of the most natural male voices
EDGE_VOICE = "en-US-AndrewNeural"
EDGE_RATE = "-5%"   # slight slowdown sounds more human
EDGE_PITCH = "+0Hz"

print("Loading Whisper...")
whisper_model = whisper.load_model("base")


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


async def _speak_async(text: str) -> None:
    """Generate speech with edge-tts and play it."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name

    try:
        communicate = edge_tts.Communicate(
            text, EDGE_VOICE, rate=EDGE_RATE, pitch=EDGE_PITCH
        )
        await communicate.save(path)
        _play_mp3(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _play_mp3(path: str) -> None:
    """Play an mp3 file on Windows."""
    import winsound
    # winsound can't play mp3 — use the OS default player via subprocess
    # For mp3, we'll use the Windows Media Player COM or simple os.startfile
    # Simplest reliable way: use pygame mixer if available, else os.startfile
    try:
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(30)
        pygame.mixer.quit()
    except ImportError:
        # Fallback: use PowerShell to play the file and wait
        import subprocess
        subprocess.run(
            ["powershell", "-c",
             f"(New-Object Media.SoundPlayer '{path}').PlaySync();"],
            capture_output=True,
        )


def speak(text: str) -> None:
    """Convert text to speech and play it."""
    print(f"JARVIS: {text}")
    try:
        asyncio.run(_speak_async(text))
    except Exception as e:
        print(f"[TTS error: {e}]")