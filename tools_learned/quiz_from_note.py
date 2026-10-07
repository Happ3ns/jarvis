def quiz_from_note(file_path: str, top_n: int = 5) -> str:
    """Read a note file and generate multiple-choice questions.
    Returns a string containing up to `top_n` questions with 4 options each.
    """
    import os, re, random
    from pathlib import Path
    # Read file safely
    try:
        text = Path(file_path).read_text(encoding='utf-8')
    except FileNotFoundError:
        return f"File {file_path} not found."
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return "No content to generate questions."
    random.seed(42)
    chosen = random.sample(sentences, min(top_n, len(sentences)))
    questions = []
    for i, sent in enumerate(chosen, 1):
        words = sent.split()
        if len(words) < 5:
            continue
        idx = random.randint(0, len(words)-1)
        answer = words[idx]
        words[idx] = '____'
        q = ' '.join(words)
        distractors = set()
        while len(distractors) < 3:
            d = random.choice(sentences).split()[0]
            if d.lower() != answer.lower() and d not in distractors:
                distractors.add(d)
        options = list(distractors) + [answer]
        random.shuffle(options)
        questions.append(f"{i}. {q}\nA) {options[0]}\nB) {options[1]}\nC) {options[2]}\nD) {options[3]}\nAnswer: {answer}")
    return '\n\n'.join(questions)
