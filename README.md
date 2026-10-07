# JARVIS

An autonomous AI assistant with voice I/O, tool calling, code execution, browser automation, multi-agent orchestration, and self-extension — JARVIS writes its own tools.

Built in Python, JARVIS combines a Groq-powered LLM brain with a growing toolset (55+ built-in, unlimited learned), persistent memory, autonomous experiment mode, and a Stark Industries-style web HUD.

![Stark HUD Interface](docs/hud.png)

---

## Features

### Interfaces
- **Terminal** (`jarvis.py`) — type or speak
- **Web UI** (`app.py`) — Stark Industries-style HUD with an animated arc reactor, live telemetry, streaming transcript, and gold-bordered plan rendering

### Voice I/O
- Speech-to-text via **Whisper** (`base` model), auto language detection (English + Hindi)
- Text-to-speech via **edge-tts** (Microsoft neural voice)
- Hybrid input — type commands or use voice
- Wake word detection (optional) — say "Hey Jarvis"

### LLM Brain
- **Groq API** (free tier) with multi-model fallback: `openai/gpt-oss-120b` → `openai/gpt-oss-20b` → `qwen/qwen3.8-27b`
- **Ollama** local fallback (`qwen2.5:3b`) for offline use
- Streaming responses (token-by-token)
- Autonomous planning — LLM writes a `PLAN:` block for multi-step tasks
- Up to 8 tool calls per request (loop-protected)
- Tool hallucination guard — rejects invalid tool names and retries
- JSON retry handling for malformed tool calls
- Groq channel-suffix normalization (strips `.channel` / `commentary` artifacts)
- Narration detection — catches LLMs that describe tool calls in text instead of emitting them
- Automatic `TOOLS` reload after `create_tool` succeeds, so new tools are usable in the same session

### Self-Extension — JARVIS Writes Its Own Tools
This is the headline feature. When you ask JARVIS for something none of its 55+ built-in tools can do, it:

1. **Recognizes the gap** — the LLM checks the tool list, finds no match
2. **Writes new Python code** for the tool
3. **Tests it** in a subprocess sandbox
4. **Retries with correction** if the test fails or the JSON is malformed
5. **Saves it permanently** to `tools_learned/`
6. **Auto-loads it** on every restart, and reloads it mid-session after successful creation

**Example:**
