"""Advanced tools — conversation memory, reminders, conversion, translation, PDF reading."""

import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# ============================================================
# 1. CONVERSATION MEMORY
# ============================================================

_conversation = []  # list of {"user": ..., "reply": ..., "time": ...}
MAX_HISTORY = 20


def remember(user_text: str, reply: str) -> None:
    """Store one exchange in memory."""
    _conversation.append({
        "user": user_text,
        "reply": reply,
        "time": datetime.now(),
    })
    if len(_conversation) > MAX_HISTORY:
        _conversation.pop(0)


def clear_memory() -> str:
    _conversation.clear()
    return "Conversation history cleared."


def recall_last_question() -> str:
    if not _conversation:
        return "You haven't asked me anything yet."
    # Skip internal/system messages
    for entry in reversed(_conversation):
        u = entry["user"].lower()
        if not u.startswith("__"):
            return f'You asked: "{entry["user"]}"'
    return "You haven't asked me anything yet."


def recall_last_reply() -> str:
    if not _conversation:
        return "I haven't said anything yet."
    return f'I said: "{_conversation[-1]["reply"]}"'


def recall_recent(n: int = 3) -> str:
    if not _conversation:
        return "No conversation history."
    lines = []
    for entry in _conversation[-n:]:
        lines.append(f'You: {entry["user"]}')
        lines.append(f'Me: {entry["reply"]}')
    return " | ".join(lines)


def get_memory_length() -> int:
    return len(_conversation)


# ============================================================
# 2. REMINDERS
# ============================================================

_reminders = []


def set_reminder(when_seconds: int, message: str, speak_fn=None) -> str:
    """Schedule a reminder. speak_fn is the voice function to call when it fires."""
    if when_seconds <= 0:
        return "That time has already passed."

    fire_at = datetime.now() + timedelta(seconds=when_seconds)
    reminder = {
        "message": message,
        "fire_at": fire_at,
        "thread": None,
    }

    def _fire():
        remaining = (fire_at - datetime.now()).total_seconds()
        if remaining > 0:
            time.sleep(remaining)
        # Speak the reminder
        if speak_fn:
            try:
                speak_fn(f"Reminder: {message}")
            except Exception:
                pass

    t = threading.Thread(target=_fire, daemon=True)
    t.start()
    reminder["thread"] = t
    _reminders.append(reminder)

    delta = fire_at - datetime.now()
    mins = int(delta.total_seconds() // 60)
    if mins >= 60:
        hours = mins // 60
        return f"Reminder set for {hours} hour{'s' if hours != 1 else ''} from now."
    if mins >= 1:
        return f"Reminder set for {mins} minute{'s' if mins != 1 else ''} from now."
    return f"Reminder set for {int(delta.total_seconds())} seconds from now."


def list_reminders() -> str:
    if not _reminders:
        return "No active reminders."
    lines = []
    for r in _reminders:
        remaining = (r["fire_at"] - datetime.now()).total_seconds()
        if remaining > 0:
            mins = int(remaining // 60)
            lines.append(f"{r['message']} — in {mins} min")
    if not lines:
        return "No active reminders."
    return " | ".join(lines)


def parse_reminder_time(text: str) -> tuple:
    """Parse time expressions. Returns (seconds_from_now, matched_text) or (None, None)."""
    text_lower = text.lower()

        # "in X minutes" OR "after X minutes" OR "for X minutes"
    m = re.search(r"(?:in|after|for)\s+(\d+)\s*(second|minute|hour|sec|min|hr)s?",
                  text_lower)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        mult = {"second": 1, "sec": 1, "minute": 60, "min": 60,
                "hour": 3600, "hr": 3600}[unit]
        return n * mult, m.group(0)

    # "at 5pm" / "at 17:30" / "at 5:30pm"
    m = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text_lower)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)

        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        elif ampm is None and hour < 8:
            # Heuristic: if no am/pm and hour is small, assume pm
            hour += 12

        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)  # next day

        seconds = (target - now).total_seconds()
        return int(seconds), m.group(0)

    return None, None


# ============================================================
# 3. UNIT + CURRENCY CONVERSION
# ============================================================

# Common unit conversions (factor to base unit)
_LENGTH = {
    "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
    "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
    "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
    "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
    "mile": 1609.344, "miles": 1609.344, "mi": 1609.344,
    "foot": 0.3048, "feet": 0.3048, "ft": 0.3048,
    "inch": 0.0254, "inches": 0.0254, "in": 0.0254,
    "yard": 0.9144, "yards": 0.9144, "yd": 0.9144,
}

_WEIGHT = {
    "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0, "kilo": 1.0, "kilos": 1.0,
    "g": 0.001, "gram": 0.001, "grams": 0.001,
    "mg": 0.000001, "milligram": 0.000001, "milligrams": 0.000001,
    "lb": 0.453592, "lbs": 0.453592, "pound": 0.453592, "pounds": 0.453592,
    "oz": 0.0283495, "ounce": 0.0283495, "ounces": 0.0283495,
    "ton": 1000.0, "tons": 1000.0, "tonne": 1000.0,
}

_TEMP_UNITS = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}


def _convert_unit(value: float, from_u: str, to_u: str) -> tuple:
    """Returns (result, kind) or (None, None)."""
    f = from_u.lower().strip().rstrip(".")
    t = to_u.lower().strip().rstrip(".")

    # Temperature (special case)
    if f in _TEMP_UNITS and t in _TEMP_UNITS:
        # Convert from → C → to
        if f in ("c", "celsius"):
            c = value
        elif f in ("f", "fahrenheit"):
            c = (value - 32) * 5 / 9
        else:  # kelvin
            c = value - 273.15

        if t in ("c", "celsius"):
            out = c
        elif t in ("f", "fahrenheit"):
            out = c * 9 / 5 + 32
        else:
            out = c + 273.15
        return round(out, 2), "temperature"

    # Length
    if f in _LENGTH and t in _LENGTH:
        return round(value * _LENGTH[f] / _LENGTH[t], 4), "length"

    # Weight
    if f in _WEIGHT and t in _WEIGHT:
        return round(value * _WEIGHT[f] / _WEIGHT[t], 4), "weight"

    return None, None


def convert_units(query: str) -> str:
    """Parse '10 km to miles' or 'convert 100 F to C'."""
    # Strip leading verbs
    text = query.lower()
    for prefix in ["convert ", "how many ", "change "]:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    # Strip "is X in Y" / "X to Y"
    m = re.search(
        r"(-?\d+\.?\d*)\s*([a-zA-Z°]+)\s+(?:to|in|into|as)\s+([a-zA-Z°]+)",
        text,
    )
    if not m:
        return ""

    value = float(m.group(1))
    from_u = m.group(2).replace("°", "")
    to_u = m.group(3).replace("°", "")

    result, kind = _convert_unit(value, from_u, to_u)
    if result is None:
        return f"I don't know how to convert {from_u} to {to_u}."

    return f"{value} {from_u} is {result} {to_u}."


def convert_currency(query: str) -> str:
    """Parse '100 USD to INR' using live rates from open.er-api.com (no key)."""
    m = re.search(
        r"(\d+\.?\d*)\s*([a-zA-Z]{3})\s+(?:to|in|into|as)\s+([a-zA-Z]{3})",
        query,
    )
    if not m:
        return ""

    amount = float(m.group(1))
    from_cur = m.group(2).upper()
    to_cur = m.group(3).upper()

    try:
        r = requests.get(
            f"https://open.er-api.com/v6/latest/{from_cur}",
            timeout=6,
        ).json()
        if r.get("result") != "success":
            return f"Couldn't fetch {from_cur} exchange rates."
        rate = r["rates"].get(to_cur)
        if not rate:
            return f"I don't recognize currency {to_cur}."
        result = round(amount * rate, 2)
        return f"{amount} {from_cur} is about {result} {to_cur}."
    except Exception as e:
        return f"Currency error: {e}"


# ============================================================
# 4. TRANSLATION
# ============================================================

_LANG_CODES = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de",
    "italian": "it", "portuguese": "pt", "russian": "ru", "japanese": "ja",
    "chinese": "zh-CN", "korean": "ko", "arabic": "ar", "hindi": "hi",
    "bengali": "bn", "tamil": "ta", "telugu": "te", "urdu": "ur",
    "dutch": "nl", "polish": "pl", "turkish": "tr", "vietnamese": "vi",
    "thai": "th", "greek": "el", "hebrew": "he", "swedish": "sv",
    "indonesian": "id", "malay": "ms",
}


def translate_text(text: str, target_lang: str) -> str:
    """Translate using the free Google Translate endpoint."""
    lang = target_lang.lower().strip()
    code = _LANG_CODES.get(lang, lang[:2] if lang else "en")

    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": "auto",
                "tl": code,
                "dt": "t",
                "q": text,
            },
            timeout=6,
        )
        data = r.json()
        if data and data[0]:
            translated = "".join(seg[0] for seg in data[0] if seg[0])
            return translated
        return "Translation failed."
    except Exception as e:
        return f"Translation error: {e}"


# ============================================================
# 5. PDF / DOCUMENT READER
# ============================================================

def read_pdf(path: str, max_pages: int = 5) -> str:
    """Extract text from a PDF and return the first N pages' worth."""
    p = Path(path)
    if not p.exists():
        return f"File not found: {path}"
    if p.suffix.lower() != ".pdf":
        return f"Only PDF files are supported, got {p.suffix}."

    try:
        import pdfplumber
    except ImportError:
        return "Install pdfplumber: pip install pdfplumber"

    try:
        text_parts = []
        with pdfplumber.open(p) as pdf:
            total = len(pdf.pages)
            for i, page in enumerate(pdf.pages[:max_pages]):
                t = page.extract_text() or ""
                if t:
                    text_parts.append(t)

        if not text_parts:
            return "No extractable text found (the PDF might be scanned images)."

        full_text = "\n".join(text_parts)
        # Trim to a reasonable summary length
        if len(full_text) > 800:
            full_text = full_text[:800].rsplit(" ", 1)[0] + "..."
        return f"From {p.name} ({total} page{'s' if total != 1 else ''}): {full_text}"

    except Exception as e:
        return f"PDF read error: {e}"