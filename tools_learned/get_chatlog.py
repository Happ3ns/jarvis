def get_chatlog(file_path: str) -> str:
    """Read and return the full contents of a chatlog file.
    Args:
        file_path: Path to the chatlog text file.
    Returns:
        The file contents as a string, or an error message if reading fails.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f'Error reading file: {e}'
