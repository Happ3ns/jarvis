"""LLM brain for JARVIS — uses Groq's free API with OpenAI-compatible client."""

import json
import os

from openai import OpenAI

from claude_tools import TOOLS

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY"),
)

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = (
    "You are JARVIS, a concise voice assistant. "
    "Keep replies to 1-2 sentences. "
    "Use the tools provided to answer questions. "
    "For music playback, ALWAYS use play_on_youtube by default. "
    "Only use play_on_spotify if the user explicitly says 'on spotify'. "
    "If the user asks to stop music, use stop_youtube. "
    "If the user asks something that no tool handles, answer directly. "
    "Never make up data — use tools for facts."
)


def ask(user_text: str, execute_tool_fn, max_steps: int = 5) -> str:
    """Send user text to the LLM, execute any tool calls, return final reply."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    for _ in range(max_steps):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=512,
                temperature=0.3,
            )
        except Exception as e:
            return f"Brain error: {e}"

        msg = response.choices[0].message

        # No tool calls — final answer
        if not msg.tool_calls:
            return msg.content or "I'm not sure how to help with that."

        # Append assistant's tool-call request
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

        # Execute each tool
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