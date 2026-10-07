"""LLM brain for JARVIS — Groq with Ollama fallback.

Streams responses, detects plans, filters hallucinated tool names,
retries on tool validation errors. Uses smart tool router to save tokens.
"""
import ambient
import json
import tool_router
import os
import anticipate
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
    cleaned = _re.split(r"[<.|]", name)[0].strip()
    return cleaned or name


SYSTEM_PROMPT = (
    "You are JARVIS, an autonomous agent. Chain tools to complete goals. "

    # ---- Tool name discipline ----
    "ONLY call tools that appear in the tools list. Never invent names. "
    "Never append suffixes like '.channel', 'commentary', or "
    "'<|channel|>commentary'. Use 'open_app', not 'open_app.channel'. "
    "The weather tool is 'get_weather' (not search_weather). "
    "The search tool is 'search_web' (not web_search). "

    # ---- Tool selection ----
    "Choose the most specific tool. "
    "For CSV/JSON analysis: analyze_file. "
    "For word frequency: learned 'top_words' if present, else run_code. "
    "For merging CSVs in a folder: 'merge_csv_folder' if present. "
    "For math/data: compute or run_code. "
    "For websites ('check if X', 'check about X', 'look up X', 'is X a site'): "
    "search_web or open_url with the domain. "
    "NEVER use open_app for websites — open_app is for local apps only "
    "(Spotify, Chrome, VS Code, Notepad). "
    "For 'open X in vscode' or 'open file X' or 'edit X': open_file_in_editor. "
    "For music: play_on_youtube by default; play_on_spotify only if user says "
    "'on spotify' or 'spotify X'. To stop music: stop_youtube. "
    "For screen requests: analyze_screen or read_screen_text. "
    "For browser tasks: open_url, search_google, search_youtube, get_page_text, "
    "click_element, type_into, run_browser_code. "
    "For user's own files: ask_documents (after index_folder). "
    "For parallel research: spawn_agents. "
    "For experiments ('investigate', 'test whether', 'find out why', "
    "'run an experiment on', 'compare X and Y empirically'): use "
    "run_experiment. Actually run it — do not just search the web. "
    "For past experiments: list_experiments. For one: show_experiment with ID. " 


    "If the user sends a URL (http://, https://, or a domain like github.com), "
    "ALWAYS use open_url with that exact URL. NEVER use open_app for URLs. "

    "When you intend to create a tool, you MUST call create_tool with "
    "the structured tool_calls mechanism. Do NOT describe the tool in "
    "text. Do NOT write 'I will create a tool' — either call create_tool, "
    "or if you can't, say so plainly. Narrating intent without calling "
    "the tool is a failure. "

    # ---- Universities/admissions ----
    "For university, admissions, SAT, or academic program questions: search "
    "the web and share what you find. Give the user information, not a formal "
    "guarantee. Do not refuse. "

    # ---- Planning ----
    "For 3+ tool-call tasks, start with 'PLAN:' followed by max 3 short lines, "
    "each ending with a newline, then a blank line. Skip PLAN for simple "
    "single-tool tasks. NEVER write tool-call JSON as plain text — use the "
    "structured tool_calls mechanism, or answer directly. "
    "Execute the steps one after another, then give a 1-2 sentence summary. "
    "Max 25 tool calls per request. If a tool fails, try a different approach. "

    # ---- Self-extension ----
    "If no existing tool fits, use create_tool. Short code (under 30 lines), "
    "single quotes for strings, avoid triple-quotes and heavy regex escapes. "
    "Include a small test_code. "
    "After create_tool succeeds, STOP. Do not call the new tool in the same "
    "response — it becomes available next turn. Just tell the user it was created. "

    # ---- Response style ----
    "1-2 sentences unless the user asks for detail. Be concise. "
    "For judgment questions ('which is better', 'what should I do', 'is X "
    "worth it'): give 3-5 short 'Step N: ...' reasoning steps, then a "
    "one-sentence recommendation. For facts, skip the reasoning. "

    # ---- Memory ----
    "'remember X' or 'note that X' → remember_fact. "
    "'what do you know about me' → recall_facts. "
    "Past conversations → search_past_conversations or get_conversations_on. "

    # ---- Context ----
    "You may receive ambient context (active app, idle, battery, git, recent "
    "files). Use it for 'what should I do', 'am I productive', 'should I "
    "take a break'. Do not mention it unless directly useful. "

    # ---- Scheduling ----
    "'remind me every X', 'every morning at 8', 'daily at 9pm' → schedule_task. "
    "'tell me when X happens', 'notify me if Y' → watch_for. "

    # ---- Anti-hallucination ----
    "Never make up data — use tools. Never claim to have done something you did not do. "

    "If you need a tool that is not in your current list, call "
    "load_all_tools. It will expand the available tools next turn. "
)


def _call_with_fallback(messages, stream: bool = False, _retry: bool = False,
                        use_all_tools: bool = False):
    """Try each model in order. On recoverable errors, retry once.

    Router-miss recovery: if the LLM tries to call a tool that wasn't in
    the sent subset, retry the SAME model with just that one tool added.
    Costs ~100 extra tokens, not ~4,000.
    """
    last_error = None

    # Pick tools based on the latest user message
    user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = m.get("content", "")
            break

    active_tools = TOOLS

    for client, model in MODELS:
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                tools=active_tools,
                tool_choice="auto",
                max_tokens=4096,
                temperature=0.05 if _retry else 0.3,
                stream=stream,
            )
        except Exception as e:
            err_str = str(e)

            # ── Router-miss recovery ──
            # The LLM tried to call a tool not in the sent subset. Add just
            # that tool and retry the same model. Cheap, bounded, no loops.
            is_router_miss = (
                "not in request.tools" in err_str
                or "tool call validation" in err_str
                or "attempted to call tool" in err_str
            )
            if is_router_miss and not use_all_tools:
                import re as _re2
                m = _re2.search(r"attempted to call tool '([^']+)'", err_str)
                missing_name = m.group(1) if m else None

                if missing_name:
                    print(f"[brain] router miss: '{missing_name}' — "
                          f"retrying {model} with that tool added")
                    extra = [t for t in TOOLS
                             if t["function"]["name"] == missing_name]
                    if extra:
                        # Only add if not already in the subset
                        existing_names = {t["function"]["name"]
                                          for t in active_tools}
                        if missing_name not in existing_names:
                            new_tools = list(active_tools) + extra
                        else:
                            new_tools = active_tools
                        try:
                            return client.chat.completions.create(
                                model=model,
                                messages=messages,
                                tools=new_tools,
                                tool_choice="auto",
                                max_tokens=4096,
                                temperature=0.05 if _retry else 0.3,
                                stream=stream,
                            )
                        except Exception as retry_err:
                            print(f"[brain] miss-retry on {model} failed: "
                                  f"{str(retry_err)[:80]}")
                            last_error = retry_err
                            continue  # next model

                # Could not parse the tool name — fall back to full tool set
                print(f"[brain] router miss (no tool name) — trying full set")
                try:
                    return _call_with_fallback(
                        messages, stream=stream, _retry=True,
                        use_all_tools=True,
                    )
                except Exception as retry_err:
                    print(f"[brain] full-set retry failed: {str(retry_err)[:80]}")
                    last_error = retry_err
                    continue  # next model

            # ── Standard recovery path ──
            result = recovery.classify(err_str)
            print(f"[brain] {model} failed ({result['category']}): {err_str[:100]}")

            if result["should_retry"] and not _retry:
                corrected = recovery.build_correction(messages, err_str)
                if corrected is not None:
                    print(f"[brain] retrying {model} with correction")
                    try:
                        return _call_with_fallback(
                            corrected, stream=stream, _retry=True,
                            use_all_tools=use_all_tools,
                        )
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

    _recent_calls = []

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

            # Loop protection — blocks 3rd identical call
            call_sig = (tc.function.name, tc.function.arguments)
            if _recent_calls.count(call_sig) >= 2:
                print(f"[brain] loop detected: {tc.function.name} called with same args")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": (
                        f"Error: {tc.function.name} was already called twice with "
                        f"these exact arguments. Do not repeat. Try a different "
                        f"tool, or tell the user the task cannot be completed "
                        f"with current tools."
                    ),
                })
                continue
            _recent_calls.append(call_sig)

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

    # ── Anticipation cache check ──
    hit, cached = anticipate.get_cached(user_text)
    if hit:
        anticipate.log_query(user_text, [])
        yield ("content", cached)
        yield ("status", "[⚡ Precomputed]")
        yield ("done", "")
        return

    _used_tools = []
    _recent_calls = []
    _force_all_tools = False

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    plan_state = "detecting"

    # ── Conditional context injection ──
    lower = user_text.lower()

    needs_ambient = any(k in lower for k in (
        "what should i", "am i productive", "should i take", "break",
        "on my screen", "current", "right now", "recent",
        "what am i", "what's on my",
    ))
    if needs_ambient:
        ambient_text = ambient.context_summary()
        if ambient_text:
            messages.append({"role": "system", "content": ambient_text})

    needs_stats = any(k in lower for k in (
        "tool", "failed", "error", "why doesn't", "broken", "what can you do",
    ))
    if needs_stats:
        stats_text = tool_stats.summary_for_prompt()
        lessons_text = lessons.lessons_for_prompt()
        if stats_text or lessons_text:
            extra = "\n\n".join(t for t in [stats_text, lessons_text] if t)
            messages.append({"role": "system", "content": extra})

    # ── Self-critique for complex requests ──
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

    # ── Self-replying tools ──
    SELF_REPLYING_TOOLS = {
        "play_on_spotify", "play_on_youtube", "stop_youtube",
        "stop_music", "stop_all_music",
        "open_app", "close_app", "open_file_in_editor",
        "take_note", "set_reminder", "set_timer",
        "shutdown", "restart", "sleep_system",
    }

    for _ in range(max_steps):
        try:
            stream = _call_with_fallback(messages, stream=True,
                                          use_all_tools=_force_all_tools)
        except Exception as e:
            err = str(e).lower()
            if "not in request.tools" in err or "tool call validation" in err:
                print(f"[brain] Groq channel-suffix rejection — retrying")
                messages.append({
                    "role": "system",
                    "content": (
                        "CRITICAL: Your last response tried to call a tool "
                        "with an invalid name. It contained extra tokens like "
                        "'<|channel|>commentary'. Use ONLY the exact tool "
                        "names from the tools list. Example: 'open_app', not "
                        "'open_app<|channel|>commentary'. Retry now with a "
                        "clean tool name."
                    ),
                })
                try:
                    stream = _call_with_fallback(messages, stream=True,
                                                  use_all_tools=_force_all_tools)
                except Exception as e2:
                    anticipate.log_query(user_text, _used_tools)
                    yield ("content", f"Retry failed: {e2}")
                    return
            else:
                anticipate.log_query(user_text, _used_tools)
                yield ("content", f"All models failed: {e}")
                return

        content_buffer = ""
        tool_calls_buffer = {}
        has_tool_calls = False
        _json_handled = False

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
                    after = content_buffer.split("PLAN:", 1)[-1]
                    after = after.split("Plan:", 1)[-1]
                    after = after.split("plan:", 1)[-1]
                    lines = after.split("\n")
                    exit_plan = False
                    for i, line in enumerate(lines):
                        s = line.strip()
                        if not s:
                            continue
                        if s[0].isdigit() or s[0] in "-*•":
                            continue
                        if i > 0:
                            exit_plan = True
                            break
                    if exit_plan:
                        plan_state = "after_plan"
                        yield ("content", delta.content)
                    else:
                        yield ("plan", delta.content)
                    continue

                # ── Qwen raw-JSON tool call workaround ──
                if (not _json_handled
                        and plan_state == "after_plan"
                        and '{"name"' in content_buffer):
                    import re as _re
                    m = _re.search(
                        r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"'
                        r'(?:parameters|arguments)"\s*:\s*(\{.*?\})\s*\}',
                        content_buffer,
                        _re.DOTALL,
                    )
                    if m:
                        _json_handled = True
                        tool_name = m.group(1)
                        tool_args_json = m.group(2)
                        try:
                            tool_args = json.loads(tool_args_json)
                        except json.JSONDecodeError:
                            tool_args = {}
                        print(f"[brain] detected raw JSON tool call: {tool_name}")

                        # Loop protection
                        call_sig = (tool_name, json.dumps(tool_args, sort_keys=True))
                        if _recent_calls.count(call_sig) >= 2:
                            print(f"[brain] loop detected (json path): {tool_name}")
                            messages.append({
                                "role": "system",
                                "content": (
                                    f"Error: {tool_name} was already called "
                                    f"twice with these arguments. Do not "
                                    f"repeat. Try a different approach or "
                                    f"tell the user it cannot be completed."
                                ),
                            })
                            content_buffer = content_buffer[:m.start()]
                            continue
                        _recent_calls.append(call_sig)

                        yield ("status", f"[Calling {tool_name}...]")
                        try:
                            result = execute_tool_fn(tool_name, tool_args)
                            _used_tools.append({"name": tool_name, "args": tool_args})
                        except Exception as e:
                            result = f"Tool error: {e}"

                        content_buffer = content_buffer[:m.start()]

                        if tool_name in SELF_REPLYING_TOOLS:
                            yield ("content", str(result))
                            anticipate.log_query(user_text, _used_tools)
                            yield ("done", "")
                            return

                        yield ("content", "\n\n" + str(result))
                        content_buffer += "\n\n" + str(result)
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
            anticipate.log_query(user_text, _used_tools)
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
            original_name = tc["name"]
            tc["name"] = _normalize_tool_name(tc["name"])

            if original_name != tc["name"]:
                print(f"[brain] normalized tool name: '{original_name}' -> '{tc['name']}'")

            # ── Router meta-tool: expand to full tool set ──
            if tc["name"] == "load_all_tools":
                print("[brain] load_all_tools called — expanding tool set")
                _force_all_tools = True
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": (
                        "Full tool set loaded. On your next turn you have "
                        "access to all tools."
                    ),
                })
                continue

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

            # ── Loop protection — blocks 3rd identical call ──
            call_sig = (tc["name"], tc["arguments"])
            if _recent_calls.count(call_sig) >= 2:
                print(f"[brain] loop detected: {tc['name']} called with same args")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": (
                        f"Error: {tc['name']} was already called twice with "
                        f"these exact arguments. Do not repeat it. Try a "
                        f"different tool, or tell the user the task cannot "
                        f"be completed with current tools."
                    ),
                })
                continue
            _recent_calls.append(call_sig)

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

            yield ("status", f"[Calling {tc['name']}...]")
            try:
                result = execute_tool_fn(tc["name"], args)
            except Exception as e:
                result = f"Tool error: {e}"

            if tc["name"] not in ("create_tool",):
                _used_tools.append({"name": tc["name"], "args": args})

            # Self-replying tools: stream result directly, skip LLM round-trip
            if (tc["name"] in SELF_REPLYING_TOOLS
                    and not str(result).startswith("Tool error")):
                yield ("content", str(result))
                anticipate.log_query(user_text, _used_tools)
                yield ("done", "")
                return

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result),
            })

    anticipate.log_query(user_text, _used_tools)
    yield ("content", "\n[Max steps reached]")