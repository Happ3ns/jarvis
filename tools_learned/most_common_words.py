import json, collections, re, os, tempfile

def most_common_words(file_path: str, top_n: int = 10) -> str:
    """Return the top N most common words in a text file as a JSON string.
    Words are sequences of alphabetic characters (a‑z) at least two letters long.
    """
    if not os.path.isfile(file_path):
        return json.dumps({"error": "File not found"})
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read().lower()
    words = re.findall(r'\b[a-z]{2,}\b', text)
    counter = collections.Counter(words)
    most = counter.most_common(top_n)
    return json.dumps(most)

# test_code
if __name__ == '__main__':
    sample = """Hello world! This is a test. Hello again, world. Test test test.
    Another line with words: hello, test, world."""
    with tempfile.NamedTemporaryFile('w+', delete=False, suffix='.txt') as tmp:
        tmp.write(sample)
        tmp_path = tmp.name
    result = most_common_words(tmp_path, 5)
    print('Result:', result)
    os.remove(tmp_path)