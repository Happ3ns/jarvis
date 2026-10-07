def open_pdf(file_path: str, open_in_browser: bool = False) -> str:
    import webbrowser
    import os
    if not os.path.isfile(file_path):
        return f"File not found: {file_path}"
    if open_in_browser:
        # Open in browser
        webbrowser.open(f"file://{os.path.abspath(file_path)}")
    else:
        # Open with default application
        webbrowser.open(file_path)
    return f"Opened {file_path}"
