# JARVIS

A voice assistant in Python. Listens through your mic, transcribes with Whisper, responds via text-to-speech.

## Status

**Working:**
- Voice input (Whisper `base` model)
- Typed input (fallback when you can't speak)
- Speech output (pyttsx3)
- Conversation loop with exit commands

**In progress:**
- Tool calling (weather, time, search)
- LLM brain — currently a stub that echoes input

## Setup

```bash
pip install sounddevice numpy openai-whisper pyttsx3 scipy requests
