"""LLM brain for JARVIS — Groq with Ollama fallback.

Streams responses, detects plans, filters hallucinated tool names,
retries on tool validation errors.
"""

import json
import os
import tool_stats
import lessons
from openai import OpenAI
import recovery
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
    (_groq_client, "qwen/qwen3.8-27b"),    
    (_ollama_client, "llama3.2:1b"),
]

# Valid tool names — used to reject hallucinated tool calls
VALID_TOOL_NAMES = {t["function"]["name"] for t in TOOLS}

import re as _re

def _normalize_tool_name(name: str) -> str:
    """Strip Groq-specific channel suffixes like '.channel' or 'commentary'."""
    if not name:
        return name
    # Strip everything from the first '<' or '.' or '|'
    cleaned = _re.split(r"[<.|]", name)[0].strip()
    return cleaned or name

SYSTEM_PROMPT = (
    "You are JARVIS, an autonomous agent that accomplishes complex goals "
    "by chaining tools together. "

    # ---- Tool name rules (fix for Groq channel suffixes) ----
    "CRITICAL: You may ONLY call tools that appear in the tools list. "
    "Do NOT invent tool names. Do NOT append suffixes like '.channel' or "
    "'commentary' to tool names. If a tool is 'run_code', call it as "
    "'run_code' — never 'run_code.channel' or 'run_code.commentary'. "
    "Use exact tool names. The weather tool is 'get_weather' "
    "(not search_weather). The web search tool is 'search_web' "
    "(not web_search). "

    # ---- Tool selection ----
    "Choose the MOST SPECIFIC tool for each task. "
    "For CSV or JSON analysis: use analyze_file. "
    "For word frequency in text files: use the learned 'top_words' tool "
    "if available, otherwise use run_code. "
    "For merging CSVs in a folder: use 'merge_csv_folder' if available. "
    "For general math or data computation: use compute or run_code. "

    # ---- Planning ----
    "For any task requiring more than 2 tool calls, START your response "
    "with 'PLAN:' followed by a short numbered list (max 6 items, one line "
    "each). Then execute each step using tools, one after the other. "
    "Finally, give a 1-2 sentence summary of the result. "
    "For simple questions, answer directly without a plan. "
    "You have up to 25 tool calls per request. "
    "If a tool fails, adapt and try a different approach. "

    # ---- Self-extension ----
    "If the user asks for something NO existing tool can do, use create_tool "
    "to write and save a new tool. Write SHORT code (under 30 lines if "
    "possible). Use single quotes for strings inside the code. Avoid "
    "triple-quoted strings and regex with many escapes. Include a small "
    "test_code that exercises the function. "

    # ---- Response style ----
    "Keep individual replies to 1-2 sentences unless the user asks for "
    "detail. Be concise. "

    # ---- Specific tool guidance ----
    "For music, ALWAYS use play_on_youtube by default. Only use "
    "play_on_spotify if the user explicitly says 'on spotify'. "
    "To stop music, call stop_youtube. "
    "For screen-related requests, use analyze_screen or read_screen_text. "
    "For browser tasks (searching sites, clicking, scraping), use the "
    "browser tools: open_url, search_google, search_youtube, get_page_text, "
    "click_element, type_into, run_browser_code. "
    "For code or data analysis, use run_code, compute, or analyze_file. "
    "For questions about the user's own files, use ask_documents (after "
    "the user has indexed a folder with index_folder). "
    "For multi-part research that can be parallelized, use spawn_agents. "
    "For complex multi-step goals, plan first, then execute. "

    # ---- Memory ----
    "When the user says 'remember X' or 'note that X', call remember_fact. "
    "When the user asks 'what do you know about me', call recall_facts. "
    "When the user asks about past conversations, use "
    "search_past_conversations or get_conversations_on. "

    # ---- Anti-hallucination ----
    "Never make up data — use tools for facts. "
    "Never claim to have done something you didn't do. "

        # ---- Why chain (reasoning steps for judgment questions) ----
    "When the user asks a question that requires judgment — like which option "
    "is better, what should I do, or is X worth it — include 3-5 short "
    "reasoning steps before your conclusion. Format each as 'Step N: ...'. "
    "Then give a one-sentence recommendation. "
    "For factual questions, skip the reasoning and answer directly. "
)


def _call_with_fallback(messages, stream: bool = False, _retry: bool = False):
    """Try each model in order. On recoverable errors, retry once with a
    corrective system message. On unrecoverable errors, move to next model."""
    last_error = None

    for client, model in MODELS:
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=4096,
                temperature=0.05 if _retry else 0.3,
                stream=stream,
            )
        except Exception as e:
            err_str = str(e)
            result = recovery.classify(err_str)

            print(f"[brain] {model} failed ({result['category']}): {err_str[:100]}")

            if result["should_retry"] and not _retry:
                corrected = recovery.build_correction(messages, err_str)
                if corrected is not None:
                    print(f"[brain] retrying {model} with correction")
                    try:
                        return _call_with_fallback(corrected, stream=stream, _retry=True)
                    except Exception as retry_err:
                        print(f"[brain] {model} retry failed: {str(retry_err)[:80]}")
                        last_error = retry_err
                        continue

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

def _critique_plan(user_text: str, plan: str) -> str:
    """Ask the LLM to critique a plan and return improved plan text."""
    try:
        response = _call_with_fallback(
            [
                {"role": "system", "content": (
                    "You critique task plans. Identify 1-3 concrete weaknesses "
                    "or missing steps. Then output the IMPROVED plan with the "
                    "same PLAN: format. Be brief."
                )},
                {"role": "user", "content": (
                    f"User request: {user_text}\n\n"
                    f"Draft plan:\n{plan}\n\n"
                    "What's missing or wrong? Then give the improved plan."
                )},
            ],
            stream=False,
        )
        return response.choices[0].message.content or plan
    except Exception as e:
        print(f"[brain] critique failed: {e}")
        return plan

def _quick_plan(user_text: str) -> str:
    """Get a fast non-streaming draft plan for critique."""
    try:
        response = _call_with_fallback(
            [
                {"role": "system", "content": (
                    "Write a short numbered plan (3-6 items) for this task. "
                    "Start with 'PLAN:' and keep it under 60 words."
                )},
                {"role": "user", "content": user_text},
            ],
            stream=False,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        print(f"[brain] quick_plan failed: {e}")
        return ""

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

    # ---- Inject tool stats + lessons into context ----
    stats_text = tool_stats.summary_for_prompt()
    lessons_text = lessons.lessons_for_prompt()
    if stats_text or lessons_text:
        extra = "\n\n".join(t for t in [stats_text, lessons_text] if t)
        messages.append({"role": "system", "content": extra})

    # ---- Self-critique for complex requests ----
    complex_markers = [
        "plan", "research", "compare", "and then", "then save",
        "then email", "then write", "build a tool",
    ]
    is_complex = (
        len(user_text) > 120
        or any(m in user_text.lower() for m in complex_markers)
    )
    if is_complex:
        print("[brain] Complex request detected — running self-critique")
        draft = _quick_plan(user_text)
        if draft:
            critique = _critique_plan(user_text, draft)
            messages.append({
                "role": "system",
                "content": f"Reviewed plan to follow:\n{critique}",
            })

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
            # Normalize tool name (strips Groq channel suffixes)
            original_name = tc["name"]
            tc["name"] = _normalize_tool_name(tc["name"])

            if original_name != tc["name"]:
                print(f"[brain] normalized tool name: '{original_name}' -> '{tc['name']}'")

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

            # 2. Parse JSON arguments with retry feedback
        try:
                args = json.loads(tc["arguments"] or "{}")
        except json.JSONDecodeError as e:
                print(f"[brain] JSON parse failed for {tc['name']}: {e}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": (
                        "Error: your tool call arguments were not valid JSON. "
                        "This usually happens when the code field is too long "
                        "or contains unescaped characters. "
                        "Please retry with shorter code and properly escaped "
                        "strings (use \\n for newlines)."
                    ),
                })
                continue

            # 3. Execute the tool
        yield ("status", f"[Calling {tc['name']}...]")
        try:
                result = execute_tool_fn(tc["name"], args)
        except Exception as e:
                result = f"Tool error: {e}"

            # 4. Feed the result back to the LLM
        messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result),
            })

    yield ("content", "\n[Max steps reached]")