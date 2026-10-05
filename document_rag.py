"""RAG over local files — ask questions about PDFs, notes, text files."""

import hashlib
import os
from pathlib import Path

# Lazy-loaded to avoid slow startup
_embedder = None
_collection = None

SUPPORTED_EXT = {".txt", ".md", ".pdf", ".py", ".csv", ".json", ".log"}
DB_PATH = "./rag_db"


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def _get_collection():
    global _collection
    if _collection is None:
        import chromadb
        client = chromadb.PersistentClient(path=DB_PATH)
        _collection = client.get_or_create_collection("jarvis_docs")
    return _collection


def _read_file(path: Path) -> str:
    """Extract text from a supported file."""
    try:
        if path.suffix.lower() == ".pdf":
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                return "\n".join(
                    (page.extract_text() or "") for page in pdf.pages
                )
        else:
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f""


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def index_folder(folder_path: str, force: bool = False) -> str:
    """Index all supported files in a folder."""
    folder = Path(folder_path)
    if not folder.exists():
        return f"Folder not found: {folder_path}"

    collection = _get_collection()
    embedder = _get_embedder()

    files = [f for f in folder.rglob("*") if f.is_file()
             and f.suffix.lower() in SUPPORTED_EXT]
    if not files:
        return f"No supported files in {folder_path}"

    indexed_count = 0
    for f in files:
        try:
            text = _read_file(f)
            if not text.strip():
                continue

            chunks = _chunk_text(text)
            file_id = hashlib.md5(str(f).encode()).hexdigest()[:8]

            # Skip if already indexed (unless force)
            if not force:
                existing = collection.get(where={"source": str(f)}, limit=1)
                if existing["ids"]:
                    continue

            embeddings = embedder.encode(chunks, show_progress_bar=False)

            ids = [f"{file_id}_{i}" for i in range(len(chunks))]
            metadatas = [{"source": str(f), "chunk": i}
                         for i in range(len(chunks))]

            collection.upsert(
                ids=ids,
                embeddings=embeddings.tolist(),
                documents=chunks,
                metadatas=metadatas,
            )
            indexed_count += 1
        except Exception as e:
            print(f"[RAG] Skipped {f.name}: {e}")

    return f"Indexed {indexed_count} files from {folder_path}."


def ask_documents(question: str, top_k: int = 3) -> str:
    """Ask a question against indexed documents."""
    collection = _get_collection()
    embedder = _get_embedder()

    try:
        query_emb = embedder.encode([question])[0].tolist()
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
        )

        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        if not docs:
            return "Nothing indexed yet. Say 'index my Documents folder' first."

        # Build context
        context_parts = []
        for doc, meta in zip(docs, metadatas):
            source = Path(meta.get("source", "unknown")).name
            context_parts.append(f"[From {source}]\n{doc}")

        context = "\n\n---\n\n".join(context_parts)

        # Ask the LLM to answer based on context
        from openai import OpenAI
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ.get("GROQ_API_KEY"),
        )

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system",
                 "content": "Answer the user's question using ONLY the provided "
                            "document excerpts. If the answer isn't in the excerpts, "
                            "say so. Keep it to 2-3 sentences."},
                {"role": "user",
                 "content": f"Question: {question}\n\nDocument excerpts:\n{context}"},
            ],
            max_tokens=400,
            temperature=0.2,
        )

        answer = response.choices[0].message.content

        # Add source info
        sources = list(set(
            Path(m.get("source", "?")).name for m in metadatas
        ))
        if sources:
            answer += f" (Sources: {', '.join(sources[:3])})"

        return answer
    except Exception as e:
        return f"RAG error: {e}"


def clear_index() -> str:
    """Delete all indexed documents."""
    global _collection
    try:
        import chromadb
        client = chromadb.PersistentClient(path=DB_PATH)
        client.delete_collection("jarvis_docs")
        _collection = None
        return "Index cleared."
    except Exception as e:
        return f"Clear error: {e}"