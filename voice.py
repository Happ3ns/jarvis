"""Voice I/O — listening (Whisper) and speaking (edge-tts + ffplay).

Playback is via ffplay (shipped with ffmpeg) so it can be interrupted
mid-utterance. winsound.PlaySound gives no handle and cannot be stopped.
"""
import asyncio
import os
import subprocess
import tempfile
import threading
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

_speak_lock = threading.Lock()
_tts_proc = None          # handle to the currently-playing ffplay process


print("Loading Whisper...")
whisper_model = whisper.load_model("base")


# ───────────────────────── LISTENING ─────────────────────────

def listen_voice(duration: int = DURATION) -> str:
    """Record from the mic and transcribe with Whisper."""
    print("[Listening...]")
    try:
        audio = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=DEVICE,
        )
        sd.wait()
        audio = np.squeeze(audio)
        if np.abs(audio).max() < 0.01:
            return ""
        result = whisper_model.transcribe(audio, fp16=False)
        return result.get("text", "").strip()
    except Exception as e:
        print(f"[listen error: {e}]")
        return ""


# ───────────────────────── SPEAKING ─────────────────────────

async def _generate_mp3(text: str, out_path: str) -> None:
    communicate = edge_tts.Communicate(
        text, EDGE_VOICE, rate=EDGE_RATE, pitch=EDGE_PITCH
    )
    await communicate.save(out_path)


def _mp3_to_wav(mp3_path: str, wav_path: str) -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, wav_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[ffmpeg error: {e}]")
        return False


def stop_speaking() -> None:
    """Kill the currently playing TTS audio, if any. Safe to call anytime."""
    global _tts_proc
    p = _tts_proc
    _tts_proc = None
    if p and p.poll() is None:
        try:
            p.terminate()
        except Exception:
            pass
        try:
            p.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            try:
                p.kill()
            except Exception:
                pass


def speak(text: str, quiet: bool = False) -> None:
    """Generate speech and play it. Blocks until done OR until stop_speaking()
    is called from another thread."""
    print(f"JARVIS: {text}")
    if quiet or not text.strip():
        return

    stop_speaking()                       # cut off any previous utterance

    with _speak_lock:
        global _tts_proc
        mp3_path = None
        wav_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                mp3_path = f.name
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name

            asyncio.run(_generate_mp3(text, mp3_path))

            if not _mp3_to_wav(mp3_path, wav_path):
                print("[voice: conversion failed — text only]")
                return

            _tts_proc = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", wav_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _tts_proc.wait()              # returns immediately if stop_speaking() kills it
        except Exception as e:
            print(f"[TTS error: {e}]")
        finally:
            _tts_proc = None
            for path in (mp3_path, wav_path):
                if path:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass