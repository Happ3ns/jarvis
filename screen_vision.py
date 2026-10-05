"""Screen vision — screenshot + vision LLM analysis."""

import base64
import io
import os
import tempfile

from openai import OpenAI

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ.get("GROQ_API_KEY"),
        )
    return _client


# Groq's current vision-capable model
VISION_MODEL = "qwen/qwen3.8-27b"


def _capture_screen_b64() -> str:
    """Take a screenshot and return as base64 PNG."""
    import pyautogui
    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def analyze_screen(question: str = "What's on this screen? Be brief.") -> str:
    """Take a screenshot and ask the vision LLM about it."""
    try:
        img_b64 = _capture_screen_b64()
    except Exception as e:
        return f"Screenshot failed: {e}"

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                ],
            }],
            max_tokens=500,
            temperature=0.3,
        )
        return response.choices[0].message.content or "No response from vision model."
    except Exception as e:
        return f"Vision error: {e}"


def read_screen_text() -> str:
    """Extract and read text from the screen."""
    return analyze_screen(
        "Read all the text visible on this screen. "
        "Then summarize what the screen is showing in 2-3 sentences. "
        "If there's code, describe what the code does."
    )


def explain_screen_error() -> str:
    """If there's an error on screen, explain it."""
    return analyze_screen(
        "Is there an error message or problem visible on this screen? "
        "If yes, explain what it means and suggest a fix. "
        "If no error, describe what's shown briefly."
    )


def translate_screen(target_lang: str = "English") -> str:
    """Translate text on screen to target language."""
    return analyze_screen(
        f"Translate all visible text on this screen to {target_lang}. "
        "Provide the translation directly."
    )