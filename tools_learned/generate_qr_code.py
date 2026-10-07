import requests
import os

def generate_qr_code(url: str) -> str:
    """Generate a QR code image for the given URL using an online API and save it to disk."""
    api_url = "https://api.qrserver.com/v1/create-qr-code/"
    params = {
        "data": url,
        "size": "200x200"
    }
    response = requests.get(api_url, params=params)
    response.raise_for_status()
    # Sanitize URL for filename
    safe_url = url.replace('://', '_').replace('/', '_').replace(':', '_')
    filename = f"qr_{safe_url}.png"
    with open(filename, "wb") as f:
        f.write(response.content)
    return os.path.abspath(filename)
