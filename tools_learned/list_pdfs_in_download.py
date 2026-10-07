import os
import json

def list_pdfs_in_download(folder_path: str) -> str:
    """Return the first PDF file path in the given folder, or an empty string if none."""
    try:
        files = os.listdir(folder_path)
    except Exception as e:
        return json.dumps({'error': str(e)})
    pdfs = [f for f in files if f.lower().endswith('.pdf')]
    if not pdfs:
        return json.dumps({'error': 'No PDF found'})
    first_pdf = pdfs[0]
    full_path = os.path.join(folder_path, first_pdf)
    return json.dumps({'path': full_path})

# Test code
if __name__ == '__main__':
    print(list_pdfs_in_download('C:/Users/Public/Downloads'))
