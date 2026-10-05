"""Multi-agent orchestration.

Defines specialized sub-agents with restricted tool access and custom
system prompts. The main LLM can spawn them in parallel via the
`spawn_agents` tool.
"""

import json
import os
import threading

from openai import OpenAI

from claude_tools import TOOLS

_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY"),
)

MODEL = "openai/gpt-oss-120b"


AGENT_ROLES = {
    "researcher": {
        "system": (
            "You are a research sub-agent. Find accurate, up-to-date "
            "information using the search tools. Return a concise factual "
            "summary of 3-5 sentences with concrete specifics. "
            "Do NOT write code. Do NOT send emails. "
            "Use only: search_web, search_wikipedia, search_news, "
            "get_weather, open_url, search_google, get_page_text, search_youtube."
        ),
        "allowed_tools": [
            "search_web", "search_wikipedia", "search_news",
            "get_weather", "open_url", "search_google",
            "get_page_text", "search_youtube",
        ],
    },
    "coder": {
        "system": (
            "You are a code sub-agent. Write and run Python code to analyze "
            "data, compute values, or transform files. Return the output of "
            "the code plus a 1-2 sentence interpretation. "
            "Do NOT search the web. Do NOT send emails. "
            "Use only: run_code, compute, analyze_file."
        ),
        "allowed_tools": [
            "run_code", "compute", "analyze_file",
        ],
    },
    "writer": {
        "system": (
            "You are a writing sub-agent. Produce clear, well-structured "
            "prose based on the task. Return the final text only — no "
            "preamble, no acknowledgment."
        ),
        "allowed_tools": [
            "take_note", "read_notes", "remember_fact", "recall_facts",
        ],
    },
    "planner": {
        "system": (
            "You are a planning sub-agent. Given a goal, produce a numbered "
            "list of 4-7 concrete steps. Each step is one sentence. "
            "Return ONLY the numbered list. No preamble, no explanation."
        ),
        "allowed_tools": [],
    },
}


def _filtered_tools(role_name):
    """Return only the tools the given role is allowed to use."""
    allowed = set(AGENT_ROLES[role_name]["allowed_tools"])
    return [t for t in TOOLS if t["function"]["name"] in allowed]


def _run_agent(role_name, task, execute_tool_fn, max_steps=6):
    """Run one sub-agent and return its text result."""
    role = AGENT_ROLES[role_name]
    tools = _filtered_tools(role_name)

    messages = [
        {"role": "system", "content": role["system"]},
        {"role": "user", "content": task},
    ]

    for _ in range(max_steps):
        try:
            response = _client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                max_tokens=800,
                temperature=0.3,
            )
        except Exception as e:
            return f"[{role_name}] Error: {e}"

        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or f"[{role_name}] No response."

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                result = execute_tool_fn(tc.function.name, args)
            except Exception as e:
                result = f"Tool error: {e}"
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result),
            })

    return f"[{role_name}] Max steps reached."


def spawn_agents(tasks, execute_tool_fn, max_parallel: int = 5):
    """Run multiple sub-agents in parallel and combine their results.

    tasks: list of {"role": str, "task": str}
    """
    if not tasks:
        return "No tasks to run."

    tasks = tasks[:max_parallel]

    results = {}
    threads = []

    def worker(idx, role, task):
        print(f"[agents] Starting {role}: {task[:60]}")
        result = _run_agent(role, task, execute_tool_fn)
        results[idx] = {"role": role, "task": task, "result": result}
        print(f"[agents] Done: {role}")

    for i, item in enumerate(tasks):
        role = item.get("role", "researcher")
        task = item.get("task", "")
        if role not in AGENT_ROLES:
            results[i] = {
                "role": role, "task": task,
                "result": f"Unknown role: {role}",
            }
            continue
        t = threading.Thread(target=worker, args=(i, role, task), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=90)

    # Combine results in order
    lines = []
    for i in sorted(results.keys()):
        r = results[i]
        lines.append(f"=== {r['role'].upper()} AGENT ===")
        lines.append(f"Task: {r['task']}")
        lines.append(f"Result: {r['result']}")
        lines.append("")

    return "\n".join(lines)


def list_roles() -> str:
    """Return a description of available agent roles."""
    lines = ["Available agent roles:"]
    for name, role in AGENT_ROLES.items():
        first_line = role["system"].split(".")[0]
        lines.append(f"  - {name}: {first_line}.")
    return "\n".join(lines)