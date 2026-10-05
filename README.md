# JARVIS

An autonomous AI assistant with voice I/O, tool calling, code execution, browser automation, multi-agent orchestration, and self-extension — JARVIS writes its own tools.

Built in Python, JARVIS combines a Groq-powered LLM brain with a growing toolset (40+ built-in, unlimited learned), persistent memory, and a Stark Industries-style web HUD.

![Stark HUD Interface](docs/hud.png)

---

## Features

### Interfaces
- **Terminal** (`jarvis.py`) - type or speak
- **Web UI** (`app.py`) - Stark Industries-style HUD with an animated arc reactor, live telemetry, streaming transcript, and gold-bordered plan rendering

### Voice I/O
- Speech-to-text via **Whisper** (`base` model), auto language detection (English + Hindi)
- Text-to-speech via **edge-tts** (Microsoft neural voice)
- Hybrid input - type commands or use voice
- Wake word detection (optional) - say "Hey Jarvis"

### LLM Brain
- **Groq API** (free tier) with multi-model fallback: `openai/gpt-oss-120b` -> `gpt-oss-20b` -> `qwen/qwen3-32b`
- Streaming responses (token-by-token)
- Autonomous planning - LLM writes a `PLAN:` block for multi-step tasks
- Up to 25 tool calls per request
- Tool hallucination guard - rejects invalid tool names and retries
- JSON retry handling for malformed tool calls
- Groq channel-suffix normalization (strips `.channel` / `commentary` artifacts)
- Optional local fallback via **Ollama** when Groq is unavailable

### Self-Extension - JARVIS Writes Its Own Tools
This is the headline feature. When you ask JARVIS for something none of its 40+ built-in tools can do, it:

1. **Recognizes the gap** - the LLM checks the tool list, finds no match
2. **Writes new Python code** for the tool
3. **Tests it** in a subprocess sandbox
4. **Retries with correction** if the test fails or the JSON is malformed
5. **Saves it permanently** to `tools_learned/`
6. **Auto-loads it** on every restart - it becomes indistinguishable from a built-in tool

**Example:**

```
You: build a tool that reads a text file and returns the 10 most common words
JARVIS:
  [Calling create_tool...]
  [self-ext] Testing new tool: top_words...
  [self-ext] Test PASSED for top_words
  [self-ext] SAVED: tools_learned/top_words.py
  New tool 'top_words' created and saved.
```

Tomorrow:

```
You: what are the most common words in test.txt
JARVIS: [Calling top_words...]
        Top words: the (5), quick (2), brown (2), fox (2), jumps (1)...
```

**No code-writing needed the second time.** The tool is permanent.

**Safety:**
- Every new tool must pass a test before being saved
- Blocked imports: `os.system`, `subprocess`, `socket`, `eval`, `exec`, `shutil.rmtree`, `requests.post`
- Function name must match the tool name
- Manual review via `/learned <name>`
- Manual delete via `/forget-tool <name>`
- Everything stays local - nothing uploaded

### 40+ Built-in Tools Across 11 Categories

| Category | Tools |
|----------|-------|
| Intelligence | Weather, Wikipedia, random Wikipedia, web search, news search |
| Workspace | Send email, open apps (Spotify, Chrome, VS Code, etc.), open websites |
| Productivity | Screenshot, clipboard read/write, file search, notes, timer, reminders |
| System | System info (battery, CPU, RAM), public IP |
| Entertainment | YouTube playback (yt-dlp + mpv), Spotify web player fallback |
| Utility | Calculator, coin flip, dice roll, morning briefing |
| Conversion | Unit conversion (length, weight, temperature), currency (live rates) |
| Language | Translation (30+ languages), PDF text extraction |
| Code execution | Sandboxed Python - computes, analyzes CSV/JSON, plots data |
| Screen vision | Analyze screen, read screen text, explain screen errors, translate screen |
| RAG over files | Index a folder once, then ask questions about your PDFs/notes |
| Browser automation | Playwright - open URLs, search Google/YouTube, click, type, scrape |
| Multi-agent | Spawn parallel sub-agents (researcher, coder, writer, planner) |

### Long-term Memory
- Persistent **SQLite** store for user facts ("remember X")
- Full conversation history - searchable, queryable by date
- Session memory for "repeat that" / "what did I just ask"
- Slash commands: `/remember`, `/memory`, `/forget`, `/history`, `/stats`

### Slash Commands + Shell Features
- `/w [city]` -> weather | `/s [query]` -> search | `/p [song]` -> play | `/stop` -> stop music
- `/t [text] to [lang]` -> translate | `/wiki [topic]` -> Wikipedia | `/c [expr]` -> calculate
- `/note` | `/remind` | `/screen` | `/read` | `/error` | `/index` | `/ask` | `/clear` | `/help`
- `/tools` - list all learned tools
- `/learned [name]` - show the source code of a learned tool
- `/forget-tool [name]` - delete a learned tool
- Command history (Up/Down arrow keys)
- Tab completion for common commands

---

## Architecture

```mermaid
flowchart LR
    subgraph INPUT["1 - Input"]
        direction TB
        I1["Microphone"]
        I2["Typed text"]
        I3["Wake word"]
    end

    subgraph VOICE["2 - voice.py + wake_word.py"]
        direction TB
        V1["Whisper to text"]
        V2["edge-tts to speech"]
    end

    subgraph BRAIN["3 - brain.py"]
        direction TB
        B1["Groq multi-model
        gpt-oss-120b to 20b to qwen3"]
        B2["Streaming + fallback"]
        B3["Autonomous planner
        PLAN: detection"]
        B4["JSON retry
        channel-suffix fix"]
    end

    subgraph ROUTER["4 - jarvis.py"]
        R1["think_stream()"]
        R2["execute_tool()"]
    end

    subgraph TOOLS["5 - Tools"]
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
        T10["self_extension.py
        (writes new tools)"]
    end

    subgraph LEARNED["6 - tools_learned/"]
        direction TB
        L1["*.py + *.schema.json
        written at runtime"]
    end

    subgraph OUTPUT["7 - Output"]
        O1["Streaming text"]
        O2["Spoken response"]
        O3["Web HUD"]
    end

    I1 --> V1
    I2 --> R1
    I3 --> V1
    V1 --> R1
    R1 --> B1 --> B2
    B2 --> B3 --> B4 --> R2
    R2 --> T1 & T2 & T3 & T4 & T5 & T6 & T7 & T8 & T9 & T10
    T10 --> L1
    L1 --> T1
    T1 & T2 & T3 & T4 & T5 & T6 & T7 & T8 & T9 --> B2
    B2 --> R1
    R1 --> O1 --> V2 --> O2
    R1 --> O3
```

The pipeline flows through seven stages:

1. **Input** - microphone, typed text, or wake word.
2. **Voice** - Whisper converts speech to text; edge-tts converts text to speech.
3. **Brain** - Groq multi-model LLM handles streaming, fallback, planning, JSON retry, and channel-suffix normalization.
4. **Router** - `think_stream()` and `execute_tool()` in `jarvis.py` orchestrate the flow.
5. **Tools** - ten tool modules covering intelligence, productivity, code execution, vision, RAG, browser automation, multi-agent orchestration, memory, and self-extension.
6. **Learned tools** - `self_extension.py` writes new tools at runtime; they persist in `tools_learned/` and load automatically on restart.
7. **Output** - streaming text to the terminal, spoken response via TTS, and the web HUD.

---

## Project Structure

```
jarvis/
├── app.py                 # Flask web server - Stark HUD interface
├── jarvis.py              # Main terminal entry point & router
├── brain.py               # LLM brain: Groq calls, streaming, planning, retry
├── voice.py               # Speech-to-text (Whisper) & text-to-speech (edge-tts)
├── wake_word.py           # Vosk-based wake word detection
├── wake_listener.py       # Wake word listener with browser polling
├── input_handler.py       # Hybrid input handling (typed / voice)
├── tools.py               # Core tool registry & dispatcher
├── search.py              # Web search, news, Wikipedia, weather
├── productivity.py        # Screenshot, clipboard, notes, timer, reminders
├── advanced.py            # Unit conversion, currency, translation, PDF
├── screen_vision.py       # Screen analysis (Qwen vision model)
├── document_rag.py        # RAG over local PDFs / notes
├── code_runner.py         # Sandboxed Python execution
├── browser_control.py     # Playwright browser automation
├── agents.py              # Multi-agent orchestration
├── memory.py              # SQLite long-term memory & conversation history
├── self_extension.py      # Self-extending agent - writes new tools
├── slash_commands.py      # Slash command definitions & handling
├── youtube_player.py      # YouTube playback via yt-dlp + mpv
├── claude_tools.py        # Tool schemas (auto-loads tools_learned/)
├── tools_learned/         # Learned tools (auto-generated, in .gitignore)
├── templates/             # HTML templates for the web HUD
├── docs/                  # Documentation & screenshots
├── requirements.txt       # Python dependencies
└── README.md
```

---

## Installation

### Prerequisites
- Python 3.10+
- **Groq API key** (free tier at [console.groq.com](https://console.groq.com))
- Optional: **Ollama** for local LLM fallback
- Optional: **Playwright** browsers for browser automation
- Optional: **Vosk** model for wake word detection

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/Happ3ns/jarvis.git
   cd jarvis
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux / macOS
   venv\Scripts\activate      # Windows
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**
   ```bash
   playwright install
   ```

5. **Set up environment variables**
   Create a `.env` file in the project root:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   # Optional
   OLLAMA_BASE_URL=http://localhost:11434
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   ```

6. **Download the Vosk model** (if using wake word)
   ```bash
   wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
   unzip vosk-model-small-en-us-0.15.zip -d models/
   ```

---

## Usage

### Terminal Mode
```bash
python jarvis.py
```
- Type commands or press `v` to speak.
- Say "Hey Jarvis" (if wake word enabled).
- Use slash commands for quick actions.

### Web HUD
```bash
python app.py
```
Open `http://localhost:5000`.

### Example Commands
```
"What's the weather in Tokyo?"
"Search for the latest AI news"
"Play Bohemian Rhapsody on YouTube"
"Translate 'Good morning' to Spanish"
"Take a screenshot and read the text"
"Analyze this CSV file: /path/to/data.csv"
"Remember that my favorite color is blue"
"/index /home/user/documents"
"/ask What are the key points in my notes?"
"Spawn a researcher and a writer to create a report on quantum computing"
"build a tool that generates a QR code for any URL"
```

---

## Self-Extension in Action

### Example 1 - Word frequency counter

```
You: build a tool that reads a text file and returns the 10 most common words
JARVIS:
  [Calling create_tool...]
  [self-ext] Testing new tool: top_words...
  [self-ext] Test PASSED for top_words
  [self-ext] SAVED: tools_learned/top_words.py
  Tool 'top_words' created and saved.
```

Then:
```
You: what are the most common words in test.txt
JARVIS: [Calling top_words...]
        the (5), quick (2), brown (2), fox (2)...
```

### Example 2 - CSV merger

```
You: build a tool that reads a folder of CSVs, merges them all into one
JARVIS:
  [Calling create_tool...]
  Tool created: merge_csv_folder
  This tool reads all .csv files in a folder, concatenates them vertically,
  and saves the merged DataFrame to merged.csv.
```

### Managing learned tools

| Command | What it does |
|---|---|
| `/tools` | Lists every tool JARVIS has written |
| `/learned top_words` | Shows the source code |
| `/forget-tool top_words` | Deletes it permanently |

### Where the tools live

```
tools_learned/
├── top_words.py
├── top_words.schema.json
├── merge_csv_folder.py
└── merge_csv_folder.schema.json
```

Each `.py` is the implementation. Each `.schema.json` is the OpenAI-format schema the LLM sees. On startup, `claude_tools.py` scans this folder and appends every schema to `TOOLS`.

---

## Memory System

JARVIS stores long-term memory in a local SQLite database (`memory.db`).
- **Facts** - use `/remember` to persist user facts; retrieve with `/memory`.
- **Conversation history** - every session is logged and searchable by date.
- **Session memory** - in-context recall for "repeat that" or "what did I just ask".

Slash commands:
- `/remember <fact>` - store a fact
- `/memory` - list stored facts
- `/forget <fact>` - remove a fact
- `/history` - show recent conversation history
- `/stats` - show memory statistics

---

## Tools Reference

| Module | Description |
|--------|-------------|
| `tools.py` | Central registry and dispatcher |
| `search.py` | Web search, news, Wikipedia, weather |
| `productivity.py` | Screenshot, clipboard, file search, notes, timer |
| `advanced.py` | Unit conversion, currency, translation, PDF |
| `screen_vision.py` | Screen analysis using Qwen vision model |
| `document_rag.py` | RAG over local PDFs and notes |
| `code_runner.py` | Sandboxed Python execution |
| `browser_control.py` | Playwright automation |
| `agents.py` | Parallel sub-agents |
| `memory.py` | SQLite long-term memory |
| `self_extension.py` | Write new tools at runtime |
| `youtube_player.py` | YouTube playback via yt-dlp + mpv |

---

## Multi-Agent Orchestration

JARVIS can spawn parallel sub-agents:

- **Researcher** - gathers information from the web and local files.
- **Coder** - writes and executes code in a sandbox.
- **Writer** - composes reports, summaries, and creative content.
- **Planner** - breaks down large goals into actionable steps.

Example:
> "Spawn a researcher and a writer to create a report on the latest advances in fusion energy."

---

## Dependencies

Core dependencies (see `requirements.txt`):

- `sounddevice`, `numpy` - audio capture
- `openai-whisper` - speech-to-text
- `edge-tts` - text-to-speech
- `ddgs` - web search
- `requests` - HTTP client
- `spotipy` - Spotify integration
- `psutil` - system info
- `flask` - web HUD
- `pyperclip`, `pyautogui` - clipboard and screen automation
- `openai` - Groq API client
- `vosk` - wake word detection
- `playwright` - browser automation
- `chromadb`, `sentence-transformers` - RAG embeddings
- `yt-dlp`, `mpv` - YouTube playback

---

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## License

MIT License - use, modify, and extend freely. See [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [Groq](https://groq.com) for fast LLM inference.
- [OpenAI Whisper](https://github.com/openai/whisper) for speech recognition.
- [edge-tts](https://github.com/rany2/edge-tts) for neural text-to-speech.
- [Playwright](https://playwright.dev) for browser automation.
- [Vosk](https://alphacephei.com/vosk/) for offline wake word detection.
- [ChromaDB](https://www.trychroma.com/) for embeddings.
- The open-source community for the many libraries that make JARVIS possible.

---

*"Sometimes you gotta run before you can walk." - Tony Stark*
