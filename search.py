"""Web search tool using ddgs (DuckDuckGo) — free, no API key."""

from ddgs import DDGS


def search_web(query: str, max_results: int = 3) -> str:
    """Search the web and return a short summary of top results."""
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return f"I couldn't find results for {query}."

        # Build a short spoken summary from the top 2 results
        parts = []
        for r in results[:2]:
            title = r.get("title", "").strip()
            body = r.get("body", "").strip()
            if body:
                # Truncate to first sentence or 200 chars
                if ". " in body:
                    body = body.split(". ")[0] + "."
                if len(body) > 200:
                    body = body[:200].rsplit(" ", 1)[0] + "..."
                parts.append(f"{title}: {body}" if title else body)

        if not parts:
            return "I found results but couldn't extract a summary."

        return "Here's what I found: " + " Also, ".join(parts)

    except Exception as e:
        return f"Search error: {e}"


def search_news(query: str, max_results: int = 3) -> str:
    """Search recent news via DuckDuckGo."""
    try:
        results = DDGS().news(query, max_results=max_results)
        if not results:
            return f"No recent news for {query}."
        parts = []
        for r in results[:2]:
            title = r.get("title", "").strip()
            body = r.get("body", "").strip()
            if body:
                if len(body) > 180:
                    body = body[:180].rsplit(" ", 1)[0] + "..."
                parts.append(f"{title}: {body}" if title else body)
        return "Recent news: " + " Also, ".join(parts)
    except Exception as e:
        return f"News search error: {e}"