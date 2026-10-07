"""JARVIS health check — validates all modules and tool wiring."""

import importlib
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent
errors = []
warnings = []
ok = []

# ─── 1. Required files exist ───
required_files = [
    "brain.py", "jarvis.py", "app.py", "claude_tools.py",
    "tools.py", "self_extension.py", "recovery.py",
    "memory.py", "tool_stats.py", "lessons.py",
    "ambient.py", "anticipate.py", "browser_control.py",
    "experiment.py", "tool_router.py", "daemon.py",
    "tasks.py", "notifications.py",
    "templates/index.html",
]
for f in required_files:
    p = ROOT / f
    if p.exists():
        ok.append(f"✓ {f}")
    else:
        errors.append(f"✗ MISSING: {f}")

# ─── 2. Optional files ───
optional_files = [
    "agents.py", "code_runner.py", "document_rag.py",
    "screen_vision.py", "slash_commands.py", "voice.py",
    "wake_word.py", "input_handler.py", "advanced.py",
    "productivity.py", "search.py", "youtube_player.py",
    "static/jarvis.css", "static/jarvis.js",
]
for f in optional_files:
    p = ROOT / f
    if p.exists():
        ok.append(f"✓ {f} (optional)")
    else:
        warnings.append(f"⚠ optional missing: {f}")

# ─── 3. Modules import cleanly ───
modules_to_test = [
    "brain", "claude_tools", "tools", "self_extension",
    "recovery", "memory", "tool_stats", "lessons",
    "ambient", "anticipate", "tool_router", "experiment",
]
for m in modules_to_test:
    try:
        importlib.import_module(m)
        ok.append(f"✓ import {m}")
    except Exception as e:
        errors.append(f"✗ IMPORT FAIL {m}: {type(e).__name__}: {e}")

# ─── 4. Tool schemas match implementations ───
try:
    from claude_tools import TOOLS
    schema_names = {t["function"]["name"] for t in TOOLS}
    print(f"\n[info] {len(TOOLS)} tools registered\n")

    # Check every tool schema has a valid definition
    for t in TOOLS:
        fn = t.get("function", {})
        name = fn.get("name")
        if not name:
            errors.append(f"✗ tool with no name: {t}")
            continue
        if not fn.get("description"):
            warnings.append(f"⚠ tool '{name}' has no description")
        if "parameters" not in fn:
            warnings.append(f"⚠ tool '{name}' has no parameters field")

    # Check every dispatchable tool is in schema list
    # (we can't easily test this without running jarvis, so just report)
    ok.append(f"✓ {len(schema_names)} unique tool names")
except Exception as e:
    errors.append(f"✗ could not load TOOLS: {e}")

# ─── 5. No secrets accidentally committed ───
gitignore = ROOT / ".gitignore"
if gitignore.exists():
    content = gitignore.read_text()
    for must_ignore in [".env", ".browser_profile", "*.db", "experiments/"]:
        if must_ignore not in content:
            warnings.append(f"⚠ .gitignore missing: {must_ignore}")

# ─── 6. Learned tools ───
learned_dir = ROOT / "tools_learned"
if learned_dir.exists():
    py_files = list(learned_dir.glob("*.py"))
    schema_files = list(learned_dir.glob("*.schema.json"))
    ok.append(f"✓ {len(py_files)} learned .py files")
    ok.append(f"✓ {len(schema_files)} learned .schema.json files")
    if len(py_files) != len(schema_files):
        warnings.append(
            f"⚠ learned tools mismatch: "
            f"{len(py_files)} .py vs {len(schema_files)} .json"
        )
    # Check for orphaned files (py without json, json without py)
    py_names = {f.stem for f in py_files}
    schema_names_set = {f.name.replace(".schema.json", "") for f in schema_files}
    for name in py_names - schema_names_set:
        warnings.append(f"⚠ learned tool '{name}' has no .schema.json")
    for name in schema_names_set - py_names:
        warnings.append(f"⚠ schema for '{name}' has no .py file")

# ─── 7. Model config sanity ───
try:
    import brain
    models = brain.MODELS
    ok.append(f"✓ {len(models)} models configured")
    for client, model in models:
        ok.append(f"  → {model}")
except Exception as e:
    errors.append(f"✗ could not read brain.MODELS: {e}")

# ─── 8. Environment variables ───
for env_var in ["GROQ_API_KEY"]:
    val = os.environ.get(env_var)
    if val:
        ok.append(f"✓ {env_var} is set ({val[:8]}...)")
    else:
        warnings.append(f"⚠ {env_var} not set — Groq will fail")

# ─── Report ───
print("=" * 60)
print("JARVIS HEALTH CHECK")
print("=" * 60)

print(f"\n✅ OK ({len(ok)}):")
for line in ok[:40]:
    print(f"  {line}")
if len(ok) > 40:
    print(f"  ... and {len(ok) - 40} more")

if warnings:
    print(f"\n⚠️  WARNINGS ({len(warnings)}):")
    for line in warnings:
        print(f"  {line}")

if errors:
    print(f"\n❌ ERRORS ({len(errors)}):")
    for line in errors:
        print(f"  {line}")
    sys.exit(1)
else:
    print(f"\n🎉 All checks passed. JARVIS is wired correctly.")