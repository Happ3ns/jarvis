"""Smart Tool Router — sends only relevant tools to the LLM.

Saves ~2,500 tokens per request by omitting tools the current message
is unlikely to need. Falls back to the full set on demand.
"""

# Tools always sent (used by everything or critical for meta-behavior)
CORE_TOOLS = {
    "run_code", "compute", "calculate",
    "get_weather", "search_web", "search_wikipedia", "search_news",
    "open_url",
    "remember_fact", "recall_facts",
    "create_tool", "run_experiment", "list_experiments", "show_experiment",
    "get_time", "get_date",
}

# Tool categories — keyword tags. Higher match score = more likely to
# be relevant to the user's message.
CATEGORIES = {
    "music": {
        "keywords": ["play", "song", "music", "listen", "spotify", "youtube",
                     "audio", "track", "album", "artist", "stop music"],
        "tools": ["play_on_youtube", "play_on_spotify", "stop_youtube"],
    },
    "vision": {
        "keywords": ["screen", "look at", "see my", "what's on my", "screenshot",
                     "read the screen", "error on", "look at this"],
        "tools": ["analyze_screen", "read_screen_text", "explain_screen_error",
                  "translate_screen", "take_screenshot"],
    },
    "browser": {
        "keywords": ["browser", "website", "url", "open website", "click",
                     "type into", "scrape", "chrome", "navigate", "google",
                     "search google", "youtube search",
                     "web", "site", "page", "link", "source", "reference",
                     "read", "fetch", "look up"],
        "tools": ["open_url", "search_google", "search_youtube", "get_page_text",
                  "click_element", "type_into", "run_browser_code", "close_browser"],
    },
    "files": {
        "keywords": ["file", "pdf", "csv", "json", "folder", "document",
                     "analyze", "read file", "open file", "vscode", "edit"],
        "tools": ["analyze_file", "index_folder", "ask_documents", "clear_index",
                  "open_file_in_editor"],
    },
    "memory": {
        "keywords": ["remember", "forget", "history", "past conversations",
                     "what do you know", "when did i", "yesterday"],
        "tools": ["remember_fact", "recall_facts", "forget_fact",
                  "search_past_conversations", "get_conversations_on",
                  "get_recent_conversations", "memory_stats", "clear_all_facts"],
    },
    "productivity": {
        "keywords": ["email", "send", "translate", "convert", "remind",
                     "note", "screenshot", "briefing", "schedule", "reminder",
                     "watch for", "notify me", "task"],
        "tools": ["send_email", "translate_text", "convert_currency",
                  "convert_units", "set_reminder", "take_note", "read_notes",
                  "morning_briefing", "schedule_task", "watch_for",
                  "list_scheduled_tasks", "delete_scheduled_task",
                  "take_screenshot"],
    },
    "apps": {
        "keywords": ["open app", "launch", "open spotify", "open chrome",
                     "open vscode", "notepad", "calculator", "explorer"],
        "tools": ["open_app", "open_website"],
    },
    "system": {
        "keywords": ["battery", "cpu", "ram", "system", "ip address",
                     "system info", "my ip", "memory usage"],
        "tools": ["get_system_info", "get_ip"],
    },
    "agents": {
        "keywords": ["agents", "parallel", "spawn", "multiple tasks",
                     "research agents", "orchestrate"],
        "tools": ["spawn_agents", "list_agent_roles"],
    },
    "utility": {
        "keywords": ["coin", "dice", "flip", "roll", "random"],
        "tools": ["flip_coin", "roll_dice"],
    },
}

# Meta-tool that unlocks the full set. Always available.
LOAD_ALL_TOOL = {
    "type": "function",
    "function": {
        "name": "load_all_tools",
        "description": (
            "Call this if you need a tool that is not in the current list. "
            "It expands the available tools to the full set for the next turn."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


def score_category(message: str, category_name: str) -> int:
    """Count keyword hits for one category."""
    lower = message.lower()
    keywords = CATEGORIES[category_name]["keywords"]
    return sum(1 for kw in keywords if kw in lower)


def pick_tools(message: str, all_tools: list) -> tuple:
    """Return (subset_of_tools, did_route).

    Subset always includes CORE_TOOLS + load_all_tools.
    Adds category tools when their score is > 0.
    """
    if not message:
        return all_tools, False

    # Score every category
    scores = {name: score_category(message, name) for name in CATEGORIES}

    # Start with core
    selected_names = set(CORE_TOOLS)
    selected_names.add("load_all_tools")

    # Add tools from any category with score > 0
    for name, score in scores.items():
        if score > 0:
            selected_names.update(CATEGORIES[name]["tools"])

    # If nothing scored, add productivity + files (most commonly needed)
    if all(s == 0 for s in scores.values()):
        selected_names.update(CATEGORIES["productivity"]["tools"])
        selected_names.update(CATEGORIES["files"]["tools"])

    # Filter the full tools list
    subset = [t for t in all_tools if t["function"]["name"] in selected_names]
    subset.append(LOAD_ALL_TOOL)

    # Did we actually reduce? If subset >= original, no routing happened.
    did_route = len(subset) < len(all_tools)
    return subset, did_route


def stats(message: str, all_tools: list) -> dict:
    """For debugging — how many tools would be sent for this message."""
    subset, routed = pick_tools(message, all_tools)
    return {
        "total": len(all_tools),
        "sent": len(subset),
        "saved": len(all_tools) - len(subset),
        "routed": routed,
    }