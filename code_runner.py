"""Sandboxed Python code execution.

Runs user-requested code in a subprocess with:
- Timeout (default 15s)
- Restricted imports (blocks os, subprocess, socket, etc.)
- Temp working directory
- Captured stdout
"""

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

# Imports the sandbox blocks
BLOCKED_KEYWORDS = [
    "os.system", "os.popen", "subprocess", "socket",
    "shutil.rmtree", "__import__", "eval(", "exec(",
    "open('/etc", "open('C:\\Windows",
    "requests.post", "urllib.request",
]

# Safe imports that JARVIS commonly needs
SAFE_PREAMBLE = textwrap.dedent("""
    import sys
    import math
    import json
    import csv
    import re
    import random
    import statistics
    from collections import Counter, defaultdict
    from datetime import datetime, timedelta
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        pass
""")


def _check_safety(code: str) -> str:
    """Return error message if code has blocked patterns, else empty string."""
    lowered = code.lower()
    for keyword in BLOCKED_KEYWORDS:
        if keyword.lower() in lowered:
            return f"Blocked: '{keyword}' is not allowed in the sandbox."
    return ""


def run_code(code: str, timeout: int = 15) -> str:
    """Execute Python code in a sandbox. Returns stdout or error message."""
    if not code.strip():
        return "No code provided."

    safety_error = _check_safety(code)
    if safety_error:
        return safety_error

    # Write code to a temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "jarvis_code.py"
        full_code = SAFE_PREAMBLE + "\n\n" + code
        script_path.write_text(full_code, encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired:
            return f"Code ran for more than {timeout}s and was killed."
        except Exception as e:
            return f"Execution error: {e}"

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            error_lines = stderr.split("\n")[-5:]
            return "Code failed:\n" + "\n".join(error_lines)

        if not stdout:
            return "Code ran successfully but printed nothing."

        # Truncate very long output
        if len(stdout) > 2000:
            stdout = stdout[:2000] + "\n... (output truncated)"

        return stdout


def compute(expression: str) -> str:
    """Quick computation wrapper — evaluate an expression and print result."""
    code = f"print({expression})"
    return run_code(code, timeout=5)


def analyze_file(path: str, question: str) -> str:
    """Generate code to analyze a CSV/JSON file and answer a question."""
    p = Path(path)
    if not p.exists():
        return f"File not found: {path}"

    suffix = p.suffix.lower()

    if suffix == ".csv":
        code = f'''
import pandas as pd
df = pd.read_csv(r"{path}")
print("Columns:", list(df.columns))
print("Shape:", df.shape)
print()
print(df.describe())
print()
print("First 5 rows:")
print(df.head())
'''
    elif suffix == ".json":
        code = f'''
import json
with open(r"{path}", "r", encoding="utf-8") as f:
    data = json.load(f)
print("Type:", type(data).__name__)
if isinstance(data, list):
    print("Length:", len(data))
    if data:
        print("First item keys:", list(data[0].keys()) if isinstance(data[0], dict) else "not dict")
elif isinstance(data, dict):
    print("Keys:", list(data.keys()))
'''
    else:
        return f"Only CSV and JSON are supported for analysis, got {suffix}."

    return run_code(code, timeout=20)