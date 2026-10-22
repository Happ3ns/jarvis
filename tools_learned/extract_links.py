def extract_links(url):
    import requests, urllib.parse
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return f"Error fetching URL: {e}"
    # Try BeautifulSoup first
    links = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all('a', href=True):
            href = urllib.parse.urljoin(url, a['href'])
            href, _ = urllib.parse.urldefrag(href)
            text = a.get_text(strip=True)
            links.append((href, text))
    except Exception:
        # Fallback to HTMLParser
        from html.parser import HTMLParser
        class LinkParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
                self.current_href = None
                self.current_text = ''
            def handle_starttag(self, tag, attrs):
                if tag == 'a':
                    attrs = dict(attrs)
                    if 'href' in attrs:
                        self.current_href = urllib.parse.urljoin(url, attrs['href'])
                        self.current_href, _ = urllib.parse.urldefrag(self.current_href)
                        self.current_text = ''
            def handle_data(self, data):
                if self.current_href is not None:
                    self.current_text += data
            def handle_endtag(self, tag):
                if tag == 'a' and self.current_href is not None:
                    self.links.append((self.current_href, self.current_text.strip()))
                    self.current_href = None
        parser = LinkParser()
        parser.feed(html)
        links = parser.links
    seen = set()
    out = []
    for href, text in links:
        if href not in seen:
            seen.add(href)
            line = href if not text else f"{href} - {text}"
            out.append(line)
        if len(out) >= 20:
            break
    return "\n".join(out)

if __name__ == "__main__":
    result = extract_links("https://news.ycombinator.com")
    for line in result.splitlines()[:5]:
        print(line)