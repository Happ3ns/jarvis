"""Universal error recovery for LLM calls.

Classifies errors from any provider and returns correction messages
that help the LLM fix its own mistakes on retry.
"""

CORRECTIONS = {
    "rate_limit": {
        "keywords": ["429", "rate limit", "quota", "too many requests"],
        "message": None,
        "should_retry": False,
    },
    "json_parse": {
        "keywords": [
            "tool call validation failed",
            "failed to parse tool call arguments",
            "invalid json",
            "unterminated string",
        ],
        "message": (
            "Your previous tool call arguments were not valid JSON. This usually "
            "happens when the `code` field is too long or contains unescaped "
            "characters. Retry with SHORTER code (under 30 lines), use single "
            "quotes for strings, escape backslashes as \\\\, and avoid "
            "triple-quoted strings."
        ),
        "should_retry": True,
    },
    "invalid_tool": {
        "keywords": [
            "not in request.tools",
            "is not a valid tool",
            "tool not found",
            "unknown tool",
        ],
        "message": (
            "Your previous tool call used a name that doesn't exist in the "
            "tools list. Use ONLY exact tool names from the list. Do NOT append "
            "suffixes like '.channel' or 'commentary'."
        ),
        "should_retry": True,
    },
    "null_value": {
        "keywords": [
            "expected string, but got null",
            "expected integer, but got null",
            "does not match schema",
        ],
        "message": (
            "A parameter was null but the schema requires a real value. "
            "Provide a concrete value for every required parameter."
        ),
        "should_retry": True,
    },
    "context_length": {
        "keywords": [
            "context length", "too long", "maximum context",
            "exceeds the max", "token limit",
        ],
        "message": (
            "Your response was too long. Keep replies under 100 words and "
            "tool code under 30 lines."
        ),
        "should_retry": True,
    },
    "model_not_found": {
        "keywords": ["model not found", "does not exist", "404"],
        "message": None,
        "should_retry": False,
    },
    "connection": {
        "keywords": ["connection error", "connection refused",
                     "timed out", "network"],
        "message": None,
        "should_retry": False,
    },
}


def classify(error_str: str) -> dict:
    """Return {'category': str, 'message': str|None, 'should_retry': bool}."""
    lower = error_str.lower()
    for category, info in CORRECTIONS.items():
        if any(kw in lower for kw in info["keywords"]):
            return {
                "category": category,
                "message": info["message"],
                "should_retry": info["should_retry"],
            }
    return {
        "category": "unknown",
        "message": None,
        "should_retry": False,
    }


def build_correction(messages: list, error_str: str):
    """Return a corrected message list for retry, or None if not retryable."""
    result = classify(error_str)
    if not result["should_retry"] or result["message"] is None:
        return None

    corrected = list(messages)
    corrected.append({
        "role": "system",
        "content": f"CORRECTION ({result['category']}): {result['message']}",
    })
    return corrected