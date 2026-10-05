"""LLM brain for JARVIS — streaming with model fallback."""

import json
import os
import time

from openai import OpenAI

from claude_tools import TOOLS

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY"),
)

# Try these in order. If one is overloaded, fall back to the next.
# Try these in order. If one is overloaded, fall back to the next.
MODELS = [
    "openai/gpt-oss-120b",   # Best reasoning + tool calling
    "openai/gpt-oss-20b",    # Lighter, faster fallback
    "qwen/qwen3-32b",        # Also supports tool calling
]

SYSTEM_PROMPT = (
    "You are JARVIS, a concise voice assistant that can chain multiple tools "
    "together to accomplish complex tasks. "
    "Keep replies to 1-2 sentences unless the user asks for detail. "
    "Use the tools provided. "
    "For music, ALWAYS use play_on_youtube by default. Only use play_on_spotify "
    "if the user explicitly says 'on spotify'. "
    "To stop music, call stop_youtube. "
    "When the user gives a multi-step request, call the tools in sequence. "
    "For screen-related requests, use analyze_screen or read_screen_text. "
    "For questions about the user's own files, use ask_documents. "
    "Never make up data — use tools for facts."
)


def _call_with_fallback(messages, stream: bool = False):
    """Try each model until one succeeds. Returns the API response/stream."""
    last_error = None
    for model in MODELS:
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=512,
                temperature=0.3,
                stream=stream,
            )
        except Exception as e:
            err_str = str(e)
            print(f"[brain] {model} failed: {err_str[:80]}")
            last_error = e
            # Only fall back on 503 / overload errors
            if "503" in err_str or "over capacity" in err_str or "overloaded" in err_str:
                continue
            # Other errors — stop trying
            raise
    raise last_error


def ask(user_text: str, execute_tool_fn, max_steps: int = 8) -> str:
    """Non-streaming version."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    for _ in range(max_steps):
        try:
            response = _call_with_fallback(messages, stream=False)
        except Exception as e:
            return f"Brain error: {e}"

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

    return "That request took too many steps — try simplifying it."


def ask_stream(user_text: str, execute_tool_fn, max_steps: int = 8):
    """Streaming version. Yields (kind, text) tuples."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    for _ in range(max_steps):
        try:
            stream = _call_with_fallback(messages, stream=True)
        except Exception as e:
            yield ("content", f"Brain error: {e}")
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