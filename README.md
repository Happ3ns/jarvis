# JARVIS

An autonomous AI assistant with voice I/O, tool calling, code execution, browser automation, and multi-agent orchestration.

![Stark HUD Interface](docs/hud.png)

## Features

**Interfaces:**
- Terminal (`jarvis.py`) — type or speak
- Web UI (`app.py`) — Stark Industries–style HUD with an animated arc reactor, live telemetry, streaming transcript, and gold-bordered plan rendering

**Voice I/O:**
- Speech-to-text via Whisper (`base` model), auto language detection (English + Hindi)
- Text-to-speech via edge-tts (Microsoft neural voice)
- Hybrid input — type commands or use voice
- Wake word detection (optional) — say "Hey Jarvis"

**LLM brain:**
- Groq API (free tier) with multi-model fallback: `openai/gpt-oss-120b` → `gpt-oss-20b` → `qwen/qwen3-32b`
- Streaming responses (token-by-token)
- Autonomous planning — LLM writes a `PLAN:` block for multi-step tasks
- Up to 25 tool calls per request
- Tool hallucination guard — rejects invalid tool names and retries
- Optional local fallback via Ollama when Groq is unavailable

**40+ tools across 11 categories:**

| Category | Tools |
|---|---|
| Intelligence | Weather, Wikipedia, random Wikipedia, web search, news search |
| Workspace | Send email, open apps (Spotify, Chrome, VS Code, etc.), open websites |
| Productivity | Screenshot, clipboard read/write, file search, notes, timer, reminders |
| System | System info (battery, CPU, RAM), public IP |
| Entertainment | YouTube playback (yt-dlp + mpv), Spotify web player fallback |
| Utility | Calculator, coin flip, dice roll, morning briefing |
| Conversion | Unit conversion (length, weight, temperature), currency (live rates) |
| Language | Translation (30+ languages), PDF text extraction |
| **Code execution** | Sandboxed Python — computes, analyzes CSV/JSON, plots data |
| **Screen vision** | Analyze screen, read screen text, explain screen errors, translate screen |
| **RAG over files** | Index a folder once, then ask questions about your PDFs/notes |
| **Browser automation** | Playwright — open URLs, search Google/YouTube, click, type, scrape |
| **Multi-agent** | Spawn parallel sub-agents (researcher, coder, writer, planner) |

**Long-term memory:**
- Persistent SQLite store for user facts ("remember X")
- Full conversation history — searchable, queryable by date
- Session memory for "repeat that" / "what did I just ask"
- Slash commands: `/remember`, `/memory`, `/forget`, `/history`, `/stats`

**Slash commands + shell features:**
- `/w [city]` → weather · `/s [query]` → search · `/p [song]` → play · `/stop` → stop music
- `/t [text] to [lang]` → translate · `/wiki [topic]` → Wikipedia · `/c [expr]` → calculate
- `/note` · `/remind` · `/screen` · `/read` · `/error` · `/index` · `/ask` · `/clear` · `/help`
- Command history (↑/↓ arrow keys)
- Tab completion for common commands

## Architecture

```mermaid
flowchart LR
    subgraph INPUT["1 · Input"]
        direction TB
        I1["Microphone"]
        I2["Typed text"]
        I3["Wake word"]
    end

    subgraph VOICE["2 · voice.py + wake_word.py"]
        direction TB
        V1["Whisper → text"]
        V2["edge-tts → speech"]
    end

    subgraph BRAIN["3 · brain.py"]
        direction TB
        B1["Groq multi-model<br/>gpt-oss-120b → 20b → qwen3"]
        B2["Streaming + fallback"]
        B3["Autonomous planner<br/>PLAN: detection"]
    end

    subgraph ROUTER["4 · jarvis.py"]
        R1["think_stream()"]
        R2["execute_tool()"]
    end

    subgraph TOOLS["5 · Tools"]
        direction TB
        T1["tools.py + search.py"]
        T2["productivity.py"]
        T3["advanced.py"]
        T4["screen_vision.py"]
        T5["document_rag.py"]
        T6["code_runner.py"]
        T7["browser_control.py"]
        T8["agents.py"]
        T9["memory.py"]
    end

    subgraph OUTPUT["6 · Output"]
        O1["Streaming text"]
        O2["Spoken response"]
        O3["Web HUD"]
    end

    I1 --> V1
    I2 --> R1
    I3 --> V1
    V1 --> R1
    R1 --> B1 --> B2
    B2 --> B3 --> R2
    R2 --> T1 & T2 & T3 & T4 & T5 & T6 & T7 & T8 & T9
    T1 & T2 & T3 & T4 & T5 & T6 & T7 & T8 & T9 --> B2
    B2 --> R1
    R1 --> O1 --> V2 --> O2
    R1 --> O3
