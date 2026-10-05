"""Tool schemas for LLM tool-calling (JARVIS)."""

TOOLS = [
    # ---------- Vision ----------
    {
        "type": "function",
        "function": {
            "name": "analyze_screen",
            "description": (
                "Take a screenshot and analyze what's on the user's screen. "
                "Use for 'what's on my screen', 'look at this', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "What to ask about the screen",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_screen_text",
            "description": "Read and summarize all text visible on the screen",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_screen_error",
            "description": "Explain any error message visible on the screen",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "translate_screen",
            "description": "Translate text on the screen to another language",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_lang": {
                        "type": "string",
                        "description": "Target language like Spanish, French, Hindi",
                    }
                },
                "required": ["target_lang"],
            },
        },
    },

    # ---------- RAG over files ----------
    {
        "type": "function",
        "function": {
            "name": "index_folder",
            "description": (
                "Index all files (PDFs, notes, text files) in a folder so JARVIS "
                "can answer questions about them. Only needs to be done once."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Full path like C:\\Users\\91902\\Documents",
                    }
                },
                "required": ["folder_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_documents",
            "description": "Ask a question about previously indexed documents",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_index",
            "description": "Clear the indexed documents database",
            "parameters": {"type": "object", "properties": {}},
        },
    },

    # ---------- Music ----------
    {
        "type": "function",
        "function": {
            "name": "play_on_youtube",
            "description": (
                "Play a song or artist from YouTube. This is the DEFAULT music player. "
                "ALWAYS include the artist name in the query when you know it — "
                "for example 'Kesariya Pritam' instead of just 'Kesariya'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Song and artist, e.g. 'Kesariya Pritam'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_youtube",
            "description": "Stop current YouTube playback",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_on_spotify",
            "description": (
                "Play a song on Spotify. Use ONLY if the user explicitly "
                "says 'on spotify' or 'using spotify'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Song or artist name"}
                },
                "required": ["query"],
            },
        },
    },

    # ---------- Info ----------
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city. Defaults to Kanpur if no city is given.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name. Optional — defaults to Kanpur.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current information",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wikipedia",
            "description": "Look up a Wikipedia article on any topic or person",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": "Search recent news for a topic",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a math expression like '15 * 40' or '2 ** 10'",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current time",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_date",
            "description": "Get today's date",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get battery, CPU, and RAM usage",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ip",
            "description": "Get the public IP address",
            "parameters": {"type": "object", "properties": {}},
        },
    },

    # ---------- Launchers ----------
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": (
                "Open a Windows application. Supported: spotify, chrome, "
                "edge, notepad, calculator, explorer, cmd, vscode"
            ),
            "parameters": {
                "type": "object",
                "properties": {"app_name": {"type": "string"}},
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": (
                "Open a website in the browser. Shortcuts: youtube, "
                "gmail, github, reddit, twitter, google, wikipedia"
            ),
            "parameters": {
                "type": "object",
                "properties": {"site": {"type": "string"}},
                "required": ["site"],
            },
        },
    },

    # ---------- Productivity ----------
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot and save it",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email via Gmail",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "translate_text",
            "description": "Translate text to another language",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "target_lang": {
                        "type": "string",
                        "description": "Language like Spanish, French, Hindi",
                    },
                },
                "required": ["text", "target_lang"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_currency",
            "description": "Convert between currencies using live rates",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Like '100 USD to INR'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_units",
            "description": "Convert between units (length, weight, temperature)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Like '10 km to miles'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a reminder for a future time",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "integer",
                        "description": "Seconds from now",
                    },
                    "message": {
                        "type": "string",
                        "description": "What to remind about",
                    },
                },
                "required": ["seconds", "message"],
            },
        },
    },

    # ---------- Utilities ----------
    {
        "type": "function",
        "function": {
            "name": "flip_coin",
            "description": "Flip a coin",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "Roll a six-sided die",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "morning_briefing",
            "description": "Give a morning briefing: date, time, weather, battery",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_notes",
            "description": "Read saved notes",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_note",
            "description": "Save a note",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
]