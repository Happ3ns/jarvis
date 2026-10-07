def extract_conversation_from_url(url: str) -> str:
    import requests, re
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        html = resp.text
        # Remove script and style blocks
        html = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style.*?>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove all HTML tags
        text = re.sub(r'<.*?>', '', html)
        # Collapse whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)
        return cleaned
    except Exception as e:
        return f"Error extracting conversation: {e}"

if __name__ == "__main__":
    print(extract_conversation_from_url("https://example.com")[:200])