"""Browser automation using Playwright.

JARVIS can navigate to websites, search, extract text, and click elements.
Runs a visible Chromium window so you can watch what happens.

Common patterns are exposed as functions. For anything custom, the LLM
can call run_browser_code with raw Playwright code.
"""

import textwrap
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# Shared browser state
_playwright = None
_browser = None
_page = None


def _ensure_browser():
    """Start the browser on first use."""
    global _playwright, _browser, _page
    if _page is not None:
        try:
            # Check it's still alive
            _ = _page.url
            return _page
        except Exception:
            _page = None
    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(headless=False)
    _page = _browser.new_page()
    return _page


def close_browser() -> str:
    """Close the browser and clean up."""
    global _playwright, _browser, _page
    try:
        if _browser:
            _browser.close()
        if _playwright:
            _playwright.stop()
    except Exception:
        pass
    _playwright = None
    _browser = None
    _page = None
    return "Browser closed."


def open_url(url: str) -> str:
    """Open a URL and report the page title."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    page = _ensure_browser()
    try:
        page.goto(url, timeout=20000, wait_until="domcontentloaded")
        title = page.title()
        return f"Opened '{title}' at {url}."
    except PWTimeout:
        return f"Timed out loading {url}."
    except Exception as e:
        return f"Could not open {url}: {e}"


def search_youtube(query: str) -> str:
    """Search YouTube and return the titles of the top 5 results."""
    page = _ensure_browser()
    try:
        page.goto("https://www.youtube.com/results?search_query="
                  + query.replace(" ", "+"),
                  timeout=20000, wait_until="domcontentloaded")
        page.wait_for_selector("ytd-video-renderer", timeout=10000)
        titles = page.eval_on_selector_all(
            "ytd-video-renderer #video-title",
            "els => els.slice(0, 5).map(e => e.textContent.trim())"
        )
        if not titles:
            return f"No YouTube results for {query}."
        return "Top results:\n" + "\n".join(
            f"  {i+1}. {t}" for i, t in enumerate(titles)
        )
    except PWTimeout:
        return "YouTube search timed out."
    except Exception as e:
        return f"YouTube search error: {e}"


def search_google(query: str) -> str:
    """Search Google and return the top 5 result titles + URLs."""
    page = _ensure_browser()
    try:
        page.goto("https://www.google.com/search?q="
                  + query.replace(" ", "+"),
                  timeout=20000, wait_until="domcontentloaded")
        # Google may show a consent screen in some regions
        page.wait_for_timeout(1500)
        results = page.eval_on_selector_all(
            "div.g, div[data-sokoban-container]",
            """els => els.slice(0, 5).map(el => {
                const a = el.querySelector('a[href^="http"]');
                const h = el.querySelector('h3');
                return a && h ? {title: h.textContent.trim(), url: a.href} : null;
            }).filter(x => x)"""
        )
        if not results:
            return f"No Google results for {query}."
        return "Top results:\n" + "\n".join(
            f"  {i+1}. {r['title']}\n     {r['url']}"
            for i, r in enumerate(results)
        )
    except PWTimeout:
        return "Google search timed out."
    except Exception as e:
        return f"Google search error: {e}"


def get_page_text(max_chars: int = 2000) -> str:
    """Extract visible text from the currently open page."""
    page = _ensure_browser()
    try:
        text = page.inner_text("body")
        text = " ".join(text.split())  # collapse whitespace
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        return f"Page text ({page.url}):\n{text}"
    except Exception as e:
        return f"Could not read page: {e}"


def click_element(text: str) -> str:
    """Click an element by its visible text."""
    page = _ensure_browser()
    try:
        page.click(f"text={text}", timeout=5000)
        page.wait_for_timeout(1000)
        return f"Clicked '{text}'. Now at: {page.url}"
    except PWTimeout:
        return f"No element found with text '{text}'."
    except Exception as e:
        return f"Click error: {e}"


def type_into(selector: str, text: str, submit: bool = False) -> str:
    """Type text into an input field. Optionally press Enter."""
    page = _ensure_browser()
    try:
        page.fill(selector, text, timeout=5000)
        if submit:
            page.press(selector, "Enter")
            page.wait_for_timeout(1500)
        return f"Typed into {selector}."
    except PWTimeout:
        return f"Field {selector} not found."
    except Exception as e:
        return f"Type error: {e}"


def run_browser_code(code: str) -> str:
    """Run arbitrary Playwright code. `page` is pre-bound.

    Example:
        page.goto('https://example.com')
        title = page.title()
        print(title)
    """
    page = _ensure_browser()

    # Provide a print-based result
    output_lines = []

    def capture_print(*args, **kwargs):
        output_lines.append(" ".join(str(a) for a in args))

    local_env = {"page": page, "print": capture_print}

    try:
        exec(textwrap.dedent(code), {}, local_env)
    except Exception as e:
        return f"Browser code error: {e}"

    if output_lines:
        return "\n".join(output_lines)
    return "Code ran successfully (no output)."