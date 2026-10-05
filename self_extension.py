"""Self-extension: JARVIS writes new tools when it hits a gap.

Each tool lives in tools_learned/ with two files:
  - <name>.py            — the Python implementation
  - <name>.schema.json   — the OpenAI function-calling schema

On startup, claude_tools.py scans this folder and appends every schema
to the TOOLS list, so learned tools are indistinguishable from built-ins.
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).parent / "tools_learned"
TOOLS_DIR.mkdir(exist_ok=True)

# Safety: reject generated code that tries to do dangerous things
BLOCKED_PATTERNS = [
    "os.system", "os.popen", "subprocess", "socket",
    "shutil.rmtree", "__import__", "eval(", "exec(",
    "open('/etc", "open('C:\\Windows",
    "requests.post", "urllib.request",
    "shutil.move", "shutil.copy",
]

VALID_NAME = re.compile(r"^[a-z][a-z0-9_]{2,40}$")


def _check_safety(code: str) -> str:
    lowered = code.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in lowered:
            return f"Blocked: '{pattern}' is not allowed in generated tools."
    return ""


def _test_tool(code: str, test_code: str, timeout: int = 15) -> tuple:
    """Run code + test_code in a subprocess. Return (passed, output)."""
    safety = _check_safety(code) or _check_safety(test_code)
    if safety:
        return False, safety

    full = code + "\n\n# ---- test ----\n" + test_code

    with tempfile.TemporaryDirectory() as tmpdir:
        script = Path(tmpdir) / "test_tool.py"
        script.write_text(full, encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, timeout=timeout, cwd=tmpdir,
            )
        except subprocess.TimeoutExpired:
            return False, f"Test timed out after {timeout}s"
        except Exception as e:
            return False, f"Test error: {e}"

        if result.returncode != 0:
            err = result.stderr.strip().split("\n")[-6:]
            return False, "Test failed:\n" + "\n".join(err)

        return True, (result.stdout.strip() or "Test passed.")


def create_tool(name: str, description: str, code: str,
                parameters: dict, test_code: str) -> str:
    """Create, test, and save a new tool."""

    # 1. Validate the name
    if not VALID_NAME.match(name):
        return (f"Invalid tool name '{name}'. Use lowercase letters, "
                f"numbers, and underscores only (min 3 chars).")

    # 2. Reject if the tool already exists
    py_path = TOOLS_DIR / f"{name}.py"
    schema_path = TOOLS_DIR / f"{name}.schema.json"
    if py_path.exists():
        return f"Tool '{name}' already exists. Choose a different name."

    # 3. Safety check
    safety = _check_safety(code) + _check_safety(test_code)
    if safety:
        return safety

    # 4. Extract the function definition and verify it matches `name`
    func_match = re.search(r"def\s+(\w+)\s*\(", code)
    if not func_match:
        return "Code must contain a function definition."
    if func_match.group(1) != name:
        return (f"Function is named '{func_match.group(1)}' "
                f"but tool name is '{name}'. They must match.")

    # 5. Run the test
    print(f"[self-ext] Testing new tool: {name}...")
    passed, output = _test_tool(code, test_code)
    if not passed:
        print(f"[self-ext] Test FAILED for {name}")
        return f"Test failed. Fix the code and try again.\n\n{output}"

    print(f"[self-ext] Test PASSED for {name}")

    # 6. Save the tool
    py_path.write_text(code, encoding="utf-8")

    schema = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    print(f"[self-ext] SAVED: {py_path}")

    return (
        f"New tool '{name}' created and saved. "
        f"It's now available for all future sessions. "
        f"Review with /learned {name} or delete with /forget-tool {name}."
    )


def load_learned_tools() -> dict:
    """Return {name: function} for all tools in tools_learned/."""
    tools = {}
    for py_file in TOOLS_DIR.glob("*.py"):
        name = py_file.stem
        try:
            spec = importlib.util.spec_from_file_location(name, py_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            func = getattr(module, name, None)
            if callable(func):
                tools[name] = func
        except Exception as e:
            print(f"[self-ext] Failed to load {name}: {e}")
    return tools


def load_learned_schemas() -> list:
    """Return all schemas from tools_learned/ for inclusion in TOOLS."""
    schemas = []
    for schema_file in TOOLS_DIR.glob("*.schema.json"):
        try:
            schemas.append(json.loads(schema_file.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[self-ext] Bad schema {schema_file.name}: {e}")
    return schemas


def list_learned() -> str:
    """Text listing of all learned tools."""
    files = sorted(TOOLS_DIR.glob("*.py"))
    if not files:
        return "No learned tools yet."

    lines = [f"Learned tools ({len(files)}):"]
    for py_file in files:
        name = py_file.stem
        schema_file = TOOLS_DIR / f"{name}.schema.json"
        desc = ""
        if schema_file.exists():
            try:
                schema = json.loads(schema_file.read_text(encoding="utf-8"))
                desc = schema["function"].get("description", "")
            except Exception:
                pass
        lines.append(f"  - {name}: {desc[:80]}")
    return "\n".join(lines)


def show_tool(name: str) -> str:
    """Show the source code of a learned tool."""
    py_file = TOOLS_DIR / f"{name}.py"
    if not py_file.exists():
        return f"No learned tool named '{name}'."
    return py_file.read_text(encoding="utf-8")


def delete_tool(name: str) -> str:
    """Delete a learned tool."""
    py_file = TOOLS_DIR / f"{name}.py"
    schema_file = TOOLS_DIR / f"{name}.schema.json"

    if not py_file.exists():
        return f"No learned tool named '{name}'."

    py_file.unlink()
    if schema_file.exists():
        schema_file.unlink()

    return f"Deleted '{name}'."