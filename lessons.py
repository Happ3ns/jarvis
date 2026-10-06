"""Lessons learned from failed tool calls."""

import json
from datetime import datetime
from pathlib import Path

LESSONS_FILE = Path(__file__).parent / "lessons.json"


def _load() -> list:
    if LESSONS_FILE.exists():
        try:
            return json.loads(LESSONS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save(lessons: list) -> None:
    try:
        LESSONS_FILE.write_text(json.dumps(lessons, indent=2), encoding="utf-8")
    except Exception:
        pass


def record_lesson(context: str, lesson: str) -> str:
    lessons = _load()
    for existing in lessons:
        if existing.get("lesson", "").lower() == lesson.lower():
            return "Already learned that."
    lessons.append({
        "context": context[:200],
        "lesson": lesson[:300],
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    _save(lessons)
    return f"Learned: {lesson}"


def lessons_for_prompt(limit: int = 10) -> str:
    lessons = _load()
    if not lessons:
        return ""
    recent = lessons[-limit:]
    lines = ["Lessons from past mistakes (avoid repeating these):"]
    for l in recent:
        lines.append(f"  - {l['context']}: {l['lesson']}")
    return "\n".join(lines)


def all_lessons() -> str:
    lessons = _load()
    if not lessons:
        return "No lessons saved yet."
    lines = [f"Lessons ({len(lessons)}):"]
    for l in lessons[-20:]:
        lines.append(f"  [{l['date']}] {l['context']}: {l['lesson']}")
    return "\n".join(lines)


def clear_lessons() -> str:
    _save([])
    return "Lessons cleared."