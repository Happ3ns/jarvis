"""LLM brain for JARVIS — Groq with Ollama fallback.

Streams responses, detects plans, filters hallucinated tool names,
retries on tool validation errors.
"""

import json
import os

from openai import OpenAI

from claude_tools import TOOLS

# ---- Groq (primary) ----
_groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY"),
)

# ---- Ollama (local fallback) ----
_ollama_client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

MODELS = [
    (_groq_client, "openai/gpt-oss-120b"),
    (_groq_client, "openai/gpt-oss-20b"),
    (_groq_client, "qwen/qwen3-32b"),
    (_ollama_client, "llama3.2:3b"),
]

# Valid tool names — used to reject hallucinated tool calls
VALID_TOOL_NAMES = {t["function"]["name"] for t in TOOLS}

SYSTEM_PROMPT = (
    "You are JARVIS, an autonomous agent that accomplishes complex goals "
    "by chaining tools together. "

    "CRITICAL: You may ONLY call tools that appear in the tools list. "
    "Do NOT invent tool names. The weather tool is 'get_weather' "
    "(not search_weather or weather). The web search tool is 'search_web' "
    "(not web_search or google_search). Use exact tool names. "

    "For any task requiring more than 2 tool calls, START your response "
    "with 'PLAN:' followed by a short numbered list (max 6 items). "
    "Then execute each step using tools, one after the other. "
    "Finally, give a 1-2 sentence summary of the result. "

    "If the user asks for something NO existing tool can do, use create_tool "
    "to write and save a new tool. Write clean, minimal code. Include a "
    "small test_code that exercises the function. "

    "Format itineraries, plans, and step-by-step lists as markdown with "
    "each step or day as its own line, using bold for time slots "
    "(**Morning**, **Afternoon**) and bullets for activities. "
    "Use blank lines between sections. Keep it scannable."

    "For simple questions, answer directly without a plan. "
    "You have up to 25 tool calls per request. "
    "If a tool fails, adapt and try a different approach. "

    "Keep replies to 1-2 sentences unless the user asks for detail. "
    "For music, use play_on_youtube. To stop music, call stop_youtube. "
    "For screen tasks, use analyze_screen or read_screen_text. "
    "For browser tasks, use open_url, search_google, or search_youtube. "
    "For code or data, use run_code or analyze_file. "
    "For multi-part research, use spawn_agents. "
    "Never make up data — use tools for facts."
)


def _call_with_fallback(messages, stream: bool = False, _retry: bool = False):
    """Try each model in order. On tool validation errors, retry once
    with a corrective system message and lower temperature."""
    last_error = None
    for client, model in MODELS:
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=512,
                temperature=0.05 if _retry else 0.3,
                stream=stream,
            )
        except Exception as e:
            err_str = str(e)

            # Retry once on tool validation errors
            if "tool call validation failed" in err_str.lower() and not _retry:
                print(f"[brain] {model}: tool validation error — retrying")
                corrected = list(messages)
                corrected.append({
                    "role": "system",
                    "content": (
                        "REMINDER: Only use tool names from the tools list. "
                        "Weather tool: 'get_weather'. "
                        "Search tool: 'search_web'. "
                        "Do not invent tool names."
                    ),
                })
                try:
                    return _call_with_fallback(corrected, stream=stream, _retry=True)
                except Exception as retry_err:
                    print(f"[brain] {model} retry failed: {str(retry_err)[:80]}")
                    last_error = retry_err
                    continue

            print(f"[brain] {model} failed: {err_str[:100]}")
            last_error = e
            continue

    raise last_error


def ask(user_text: str, execute_tool_fn, max_steps: int = 25) -> str:
    """Non-streaming version."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    for _ in range(max_steps):
        try:
            response = _call_with_fallback(messages, stream=False)
        except Exception as e:
            return f"All models failed: {e}"

        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or "I'm not sure how to help with that."

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
            if tc.function.name not in VALID_TOOL_NAMES:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": f"Error: '{tc.function.name}' is not a valid tool.",
                })
                continue

            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = execute_tool_fn(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result),
            })

    return "That request took too many steps."


def ask_stream(user_text: str, execute_tool_fn, max_steps: int = 25):
    """Streaming version. Yields (kind, text) tuples.

    kind is one of:
      'content' — normal reply text
      'plan'    — the initial PLAN: block
      'status'  — informational like "[Calling get_weather...]"
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    plan_state = "detecting"

    for _ in range(max_steps):
        try:
            stream = _call_with_fallback(messages, stream=True)
        except Exception as e:
            yield ("content", f"All models failed: {e}")
            return

        content_buffer = ""
        tool_calls_buffer = {}
        has_tool_calls = False

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                content_buffer += delta.content

                if plan_state == "detecting":
                    stripped = content_buffer.lstrip()
                    if stripped.startswith(("PLAN:", "Plan:", "plan:")):
                        plan_state = "in_plan"
                        yield ("plan", delta.content)
                        continue
                    elif len(stripped) >= 8:
                        plan_state = "after_plan"
                        yield ("content", delta.content)
                        continue
                    else:
                        yield ("content", delta.content)
                        continue

                if plan_state == "in_plan":
                    yield ("plan", delta.content)
                    after = content_buffer.split("PLAN:", 1)[-1]
                    after = after.split("Plan:", 1)[-1]
                    after = after.split("plan:", 1)[-1]
                    if "\n\n" in after:
                        plan_state = "after_plan"
                    continue

                yield ("content", delta.content)

            if delta.tool_calls:
                has_tool_calls = True
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {
                            "id": "", "name": "", "arguments": "",
                        }
                    if tc.id:
                        tool_calls_buffer[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_buffer[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_buffer[idx]["arguments"] += tc.function.arguments

        if not has_tool_calls:
            return

        messages.append({
            "role": "assistant",
            "content": content_buffer or "",
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                }
                for tc in tool_calls_buffer.values()
            ],
        })

        for tc in tool_calls_buffer.values():
            # Reject hallucinated tool names before executing
            if tc["name"] not in VALID_TOOL_NAMES:
                print(f"[brain] rejected hallucinated tool: {tc['name']}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": (
                        f"Error: '{tc['name']}' is not a valid tool. "
                        f"Use one of the tools in the tools list."
                    ),
                })
                continue

            try:
                args = json.loads(tc["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            yield ("status", f"[Calling {tc['name']}...]")
            try:
                result = execute_tool_fn(tc["name"], args)
            except Exception as e:
                result = f"Tool error: {e}"
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result),
            })

    yield ("content", "\n[Max steps reached]")