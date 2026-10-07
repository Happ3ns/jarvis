import requests, time

def check_website(url: str) -> str:
    """Return status and response time in ms for a given URL."""
    try:
        start = time.time()
        resp = requests.get(url, timeout=10)
        elapsed = (time.time() - start) * 1000
        if resp.status_code == 200:
            return f"Website is up. Response time: {elapsed:.1f} ms."
        else:
            return f"Website returned status {resp.status_code}. Response time: {elapsed:.1f} ms."
    except requests.RequestException as e:
        return f"Website is down or unreachable: {e}."

# Test code
if __name__ == "__main__":
    print(check_website("https://www.google.com"))
