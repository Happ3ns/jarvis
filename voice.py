"""Voice I/O — listening (Whisper) and speaking (edge-tts + winsound)."""

import asyncio
import os
import subprocess
import tempfile
import winsound

import sounddevice as sd
import numpy as np
import whisper
import edge_tts

SAMPLE_RATE = 16000
DEVICE = 11
DURATION = 5

EDGE_VOICE = "en-US-AndrewNeural"
EDGE_RATE = "-5%"
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


async def _generate_mp3(text: str, path: str) -> None:
    communicate = edge_tts.Communicate(
        text, EDGE_VOICE, rate=EDGE_RATE, pitch=EDGE_PITCH
    )
    await communicate.save(path)


def _mp3_to_wav(mp3_path: str, wav_path: str) -> bool:
    """Convert mp3 → wav using ffmpeg. Returns True on success."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, wav_path],
            capture_output=True,
            timeout=15,
        )
        return result.returncode == 0 and os.path.exists(wav_path)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def speak(text: str) -> None:
    print(f"JARVIS: {text}")

    mp3_path = None
    wav_path = None
    try:
        # Generate MP3 with edge-tts
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            mp3_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name

        asyncio.run(_generate_mp3(text, mp3_path))

        # Convert to WAV so winsound can play it
        if _mp3_to_wav(mp3_path, wav_path):
            winsound.PlaySound(wav_path, winsound.SND_FILENAME)
        else:
            # Fallback: use PowerShell MediaPlayer for MP3
            subprocess.run(
                ["powershell", "-c",
                 f"Add-Type -AssemblyName presentationCore; "
                 f"$p = New-Object System.Windows.Media.MediaPlayer; "
                 f"$p.Open([Uri]'{mp3_path}'); "
                 f"$p.Play(); Start-Sleep -Seconds 5"],
                capture_output=True,
            )
    except Exception as e:
        print(f"[TTS error: {e}]")
    finally:
        for p in (mp3_path, wav_path):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass