import urllib.parse
import urllib.request
import tempfile
import os

def generate_qr_code_image(data: str) -> str:
    """Generate a QR code PNG for the given data using an online API.
    Returns the absolute path to the saved image file.
    """
    # Encode the data for URL query
    encoded = urllib.parse.quote_plus(data)
    api_url = f'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded}'
    try:
        with urllib.request.urlopen(api_url) as response:
            if response.status != 200:
                raise RuntimeError(f'QR API returned status {response.status}')
            img_data = response.read()
    except Exception as e:
        raise RuntimeError(f'Failed to retrieve QR code: {e}')
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
        tmp.write(img_data)
        return os.path.abspath(tmp.name)
