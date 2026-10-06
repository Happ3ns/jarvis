"""Tool schemas for LLM tool-calling (JARVIS)."""
import self_extension
TOOLS = [
        {
        "type": "function",
        "function": {
            "name": "create_tool",
            "description": (
                "Create a new tool permanently when NO existing tool can "
                "handle the user's request. Use ONLY as a last resort — "
                "always check the tools list first. The tool will be tested "
                "in a sandbox; if tests fail, fix the code and retry. "
                "The tool becomes available to all future sessions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "Function name — lowercase letters, numbers, "
                            "underscores only. Must match the def name in code."
                        ),
                    },
                    "description": {
                        "type": "string",
                        "description": "What the tool does, in one sentence.",
                    },
                    "code": {
                        "type": "string",
                        "description": (
                            "The complete Python function. Must be named "
                            "exactly <name> and return a string. "
                            "Blocked imports: os.system, subprocess, socket, "
                            "eval, exec, requests.post."
                        ),
                    },
                    "parameters": {
                        "type": "object",
                        "description": (
                            "JSON schema for the function's parameters, "
                            "in OpenAI format: {type: 'object', properties: "
                            "{arg: {type: 'string', description: '...'}}, "
                            "required: ['arg']}"
                        ),
                    },
                    "test_code": {
                        "type": "string",
                        "description": (
                            "Python code that calls the function on small "
                            "sample data and prints the result. Used to "
                            "verify the tool works before saving."
                        ),
                    },
                },
                "required": ["name", "description", "code",
                             "parameters", "test_code"],
            },
        },
    },
    
        # ---------- Browser automation ----------
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL in a real Chrome browser window and return the page title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL or domain like 'youtube.com'"}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_youtube",
            "description": "Search YouTube in a real browser and return the top 5 video titles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_google",
            "description": "Search Google in a real browser and return the top 5 results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_page_text",
            "description": "Extract visible text from the currently open browser page.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": "Click an element on the current page by its visible text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Visible text of the element to click"}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_into",
            "description": "Type text into an input field on the current page. Optionally submit by pressing Enter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector like 'input#search'"},
                    "text": {"type": "string"},
                    "submit": {"type": "boolean", "description": "Press Enter after typing"}
                },
                "required": ["selector", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_browser_code",
            "description": "Run custom Playwright code on the current page. Use for anything the other browser tools can't do. The variable `page` is already bound to the active browser tab. Use print() to output results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code using the `page` object"}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_browser",
            "description": "Close the browser window",
            "parameters": {"type": "object", "properties": {}},
        },
    },
        {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Run Python code in a sandbox. Use for calculations, data analysis, plotting, or any task that needs computation. The code can print() its output. Available libraries: pandas, numpy, math, statistics, json, csv, re, datetime. Blocked: os, subprocess, socket, requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute",
            "description": "Quick math computation. Returns the result of a Python expression like '15 * 47' or 'sum(range(100))' or '2 ** 100'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_file",
            "description": "Analyze a CSV or JSON file: shows columns, shape, summary stats, first rows. Use when the user asks to analyze or summarize a data file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full file path"},
                    "question": {"type": "string", "description": "What to find out about the file"},
                },
                "required": ["path", "question"],
            },
        },
    },
        # ---------- Long-term memory ----------
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Store a fact about the user permanently. Use for 'remember X', 'note that X', 'keep in mind that X'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The fact to remember"}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_facts",
            "description": "Retrieve all stored facts about the user. Use for 'what do you know about me', 'what do you remember'.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_fact",
            "description": "Delete a stored fact about the user",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_past_conversations",
            "description": "Search the user's past conversations for a keyword. Use for 'when did I ask about X', 'search my history for X'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_conversations_on",
            "description": "Get the user's conversations from a specific date. Use for 'what did I ask yesterday', 'what did we talk about last Monday'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "today, yesterday, last Monday, N days ago, or YYYY-MM-DD"
                    }
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_conversations",
            "description": "Get the most recent conversation exchanges",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_stats",
            "description": "Show how many facts and conversations are stored",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_all_facts",
            "description": "Delete all stored facts. Use for 'forget everything about me', 'clear my data'.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
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
            "description": "Get current weather for a city. If no city is provided, defaults to Kanpur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": ["string", "null"],
                        "description": "City name. Pass null or omit for Kanpur.",
                    }
                },
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
# ---- Auto-load learned tools and add their schemas ----
_learned_schemas = self_extension.load_learned_schemas()
if _learned_schemas:
    TOOLS.extend(_learned_schemas)
    print(f"[claude_tools] Loaded {len(_learned_schemas)} learned tool schema(s)")
    for s in _learned_schemas:
        print(f"  - {s['function']['name']}: {s['function'].get('description', '')[:60]}")
else:
    print("[claude_tools] No learned tools found")
    
