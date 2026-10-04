# JARVIS

A voice assistant in Python. Listens through your mic, transcribes with Whisper, does things, and speaks back.

## Working

**14 tools:**
- Weather (open-meteo, no API key)
- Time and date
- Open apps: Spotify, Chrome, Edge, Notepad, Calculator, Explorer, CMD, VS Code
- Wikipedia search (with disambiguation handling)
- Open websites: YouTube, Gmail, GitHub, Reddit, Twitter, Stack Overflow
- Spotify playback (requires Premium + developer setup)
- Calculator
- System info (battery, CPU, RAM)
- Public IP address
- Timer
- Notes
- Coin flip / dice roll
- Random Wikipedia article

**Interface:**
- Voice input via Whisper (`base` model)
- Typed input fallback (press Enter with no text to speak)
- Speech output via pyttsx3
- Graceful shutdown (Ctrl+C or "exit")

## Architecture

```mermaid
flowchart LR
    subgraph INPUT["1 · Input"]
        direction TB
        I1["Microphone"]
        I2["Typed text"]
    end

    subgraph VOICE["2 · voice.py"]
        direction TB
        V1["Whisper → text"]
        V2["pyttsx3 → speech"]
    end

    subgraph BRAIN["3 · jarvis.py"]
        B1["think() — keyword routing"]
    end

    subgraph TOOLS["4 · tools.py"]
        direction TB
        T1["Weather · Time · Date"]
        T2["Open app · Open website"]
        T3["Wikipedia · Random wiki"]
        T4["Spotify playback"]
        T5["Calculator · System info · IP"]
        T6["Timer · Notes · Coin · Dice"]
    end

    I1 --> V1
    I2 --> B1
    V1 --> B1
    B1 --> T1 & T2 & T3 & T4 & T5 & T6
    T1 & T2 & T3 & T4 & T5 & T6 --> V2

    classDef input fill:#eef4f0,stroke:#2f6f4e,stroke-width:1.5px,color:#18181b
    classDef voice fill:#eff4fb,stroke:#1d4ed8,stroke-width:1.5px,color:#18181b
    classDef brain fill:#fdf6e3,stroke:#a16207,stroke-width:1.5px,color:#18181b
    classDef tools fill:#f4effb,stroke:#7c3aed,stroke-width:1.5px,color:#18181b

    class I1,I2 input
    class V1,V2 voice
    class B1 brain
    class T1,T2,T3,T4,T5,T6 tools
