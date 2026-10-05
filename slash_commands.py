"""Slash command expansion and handling.

Slash commands are shortcuts for common commands. They get expanded
to full commands before being sent to the LLM, saving typing.
"""

# Mapping of /shortcut → full command prefix
SLASH_COMMANDS = {
     "/tools":    "list learned tools",
    "/learned":  "show source of learned tool",
    "/forget-tool": "delete learned tool",
    "/yt":        "search youtube for",
    "/google":    "search google for",
    "/browse":    "open url",
    "/closebrowser": "close browser",
    "/remember":  "remember",
    "/forget":    "forget",
    "/memory":    "what do you know about me",
    "/history":   "what did we talk about recently",
    "/stats":     "memory stats",
    "/w":         "what's the weather in",
    "/weather":   "what's the weather in",
    "/s":         "search for",
    "/search":    "search for",
    "/n":         "latest news about",
    "/news":      "latest news about",
    "/p":         "play",
    "/play":      "play",
    "/t":         "translate",
    "/translate": "translate",
    "/wiki":      "tell me about",
    "/c":         "what's",
    "/calc":      "what's",
    "/note":      "take a note:",
    "/remind":    "remind me",
    "/index":     "index folder",
    "/ask":       "ask my documents",
    "/screen":    "what's on my screen",
    "/read":      "read my screen",
    "/error":     "what error is on my screen",
}


HELP_TEXT = (
    "/tools - list learned tools | "
    "/learned [name] - show source | "
    "/forget-tool [name] - delete | "
    "Slash commands: "
    "/remember [text] — save a fact | "
    "/memory — recall facts | "
    "/forget [text] — delete a fact | "
    "/history — recent conversations | "
    "/stats — memory stats | "
    "/w [city] — weather | "
    "/s [query] — web search | "
    "/n [topic] — news | "
    "/p [song] — play music | "
    "/stop — stop music | "
    "/t [text] to [lang] — translate | "
    "/wiki [topic] — wikipedia | "
    "/c [expr] — calculate | "
    "/note [text] — save a note | "
    "/remind [time] — set a reminder | "
    "/screen — analyze screen | "
    "/read — read screen text | "
    "/error — explain screen error | "
    "/index [path] — index a folder | "
    "/ask [question] — query indexed docs | "
    "/clear — clear transcript | "
    "/help — this message"
)


def expand(text: str) -> str:
    """Expand a /shortcut into its full command.

    Returns the full command, or the original text if no shortcut matches.
    Handles '/clear' and '/help' by passing them through unchanged —
    those are intercepted in jarvis.py's think_stream.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return text

    parts = stripped.split(" ", 1)
    shortcut = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    # Special commands handled elsewhere
    if shortcut in ("/clear", "/help", "/stop"):
        return stripped

    if shortcut in SLASH_COMMANDS:
        if rest:
            return f"{SLASH_COMMANDS[shortcut]} {rest}".strip()
        return SLASH_COMMANDS[shortcut]

    # Unknown slash command — pass through as-is
    return text


def is_clear(text: str) -> bool:
    """Check if the user typed /clear."""
    return text.strip().lower() == "/clear"


def is_help(text: str) -> bool:
    """Check if the user typed /help."""
    return text.strip().lower() == "/help"


def is_stop(text: str) -> bool:
    """Check if the user typed /stop."""
    return text.strip().lower() == "/stop"


def get_help() -> str:
    """Return the help text."""
    return HELP_TEXT

def is_tools_command(text: str) -> bool:
    return text.strip().lower() in ("/tools", "list learned tools")


def is_learned_command(text: str) -> bool:
    return text.strip().lower().startswith("/learned ")


def is_forget_tool_command(text: str) -> bool:
    return text.strip().lower().startswith("/forget-tool ")


def handle_special_commands(text: str):
    """Return a response string for /tools, /learned X, /forget-tool X, or None."""
    import self_extension

    stripped = text.strip()

    if stripped.lower() == "/tools":
        return self_extension.list_learned()

    if stripped.lower().startswith("/learned "):
        name = stripped[len("/learned "):].strip()
        return self_extension.show_tool(name)

    if stripped.lower().startswith("/forget-tool "):
        name = stripped[len("/forget-tool "):].strip()
        return self_extension.delete_tool(name)

    return None