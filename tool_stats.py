"""Track tool call success/failure/timing over time."""

import json
import time
from pathlib import Path

STATS_FILE = Path(__file__).parent / "tool_stats.json"
_stats = None


def _load():
    global _stats
    if _stats is None:
        if STATS_FILE.exists():
            try:
                _stats = json.loads(STATS_FILE.read_text(encoding="utf-8"))
            except Exception:
                _stats = {}
        else:
            _stats = {}
    return _stats


def _save():
    try:
        STATS_FILE.write_text(json.dumps(_stats, indent=2), encoding="utf-8")
    except Exception:
        pass


def record(tool_name: str, success: bool, duration: float) -> None:
    stats = _load()
    if tool_name not in stats:
        stats[tool_name] = {"calls": 0, "successes": 0, "failures": 0, "total_time": 0.0}
    e = stats[tool_name]
    e["calls"] += 1
    e["total_time"] += duration
    if success:
        e["successes"] += 1
    else:
        e["failures"] += 1
    _save()


def summary_for_prompt() -> str:
    stats = _load()
    if not stats:
        return ""
    lines = ["Tool performance from past runs:"]
    added = 0
    for name, s in sorted(stats.items(), key=lambda x: -x[1]["calls"]):
        if s["calls"] < 2:
            continue
        rate = s["successes"] / s["calls"] * 100
        avg = s["total_time"] / s["calls"]
        lines.append(f"  {name}: {rate:.0f}% success, {avg:.1f}s avg, {s['calls']} calls")
        added += 1
    if added == 0:
        return ""
    return "\n".join(lines)


def full_report() -> str:
    stats = _load()
    if not stats:
        return "No tool stats yet."
    lines = ["Tool statistics:"]
    for name, s in sorted(stats.items(), key=lambda x: -x[1]["calls"]):
        rate = s["successes"] / s["calls"] * 100 if s["calls"] else 0
        avg = s["total_time"] / s["calls"] if s["calls"] else 0
        lines.append(
            f"  {name}: {s['calls']} calls, "
            f"{rate:.0f}% success, {avg:.1f}s avg"
        )
    return "\n".join(lines)