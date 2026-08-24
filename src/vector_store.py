import os
from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

VECTOR_DB_DIR = Path(__file__).parent.parent / "workspace" / "vectordb"
VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)

SHARED_COLLECTION = "shared_docs"
SESSION_PREFIX = "session_"

_embeddings = None
_store = None


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings


def _get_store():
    global _store
    if _store is None:
        _store = Chroma(
            collection_name=SHARED_COLLECTION,
            embedding_function=_get_embeddings(),
            persist_directory=str(VECTOR_DB_DIR),
        )
    return _store


def _get_session_store(session_id: str):
    """Get or create a Chroma collection for a specific session."""
    name = f"{SESSION_PREFIX}{session_id}"
    return Chroma(
        collection_name=name,
        embedding_function=_get_embeddings(),
        persist_directory=str(VECTOR_DB_DIR),
    )


def _split_text(text: str, max_len: int = 1000, overlap: int = 100) -> list[str]:
    if len(text) <= max_len:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_len
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += max_len - overlap
    return chunks


# ---------------------------------------------------------------------------
# Shared collection (user-uploaded docs, explicit saves)
# ---------------------------------------------------------------------------

def add_document(content: str, metadata: dict = None):
    """Add a document to the shared collection."""
    store = _get_store()
    meta = metadata or {}
    chunks = _split_text(content, max_len=1000, overlap=100)
    if not chunks:
        return 0
    store.add_texts(texts=chunks, metadatas=[meta] * len(chunks))
    return len(chunks)


def upload_and_index(filename: str, content_bytes: bytes) -> dict:
    """Extract text from uploaded file and index into shared collection.
    Returns extracted text for immediate use in chat context."""
    text = extract_text(filename=filename, content_bytes=content_bytes)
    if not text or not text.strip():
        return {"success": False, "message": "No text content found in file"}
    count = add_document(text, metadata={"title": filename, "source": "upload"})
    return {
        "success": True,
        "filename": filename,
        "chars": len(text),
        "chunks": count,
        "text": text[:8000],  # Return extracted text for chat injection
    }


def list_indexed_docs() -> list[dict]:
    """List documents in the shared collection."""
    store = _get_store()
    data = store._collection.get()
    docs = {}
    for doc, meta in zip(data["documents"], data["metadatas"]):
        title = meta.get("title", "unknown")
        if title not in docs:
            docs[title] = {"title": title, "chunks": 0, "source": meta.get("source", "unknown")}
        docs[title]["chunks"] += 1
    return list(docs.values())


# ---------------------------------------------------------------------------
# Session collections (agent memory, per-session)
# ---------------------------------------------------------------------------

def add_session_memory(session_id: str, content: str, goal: str = ""):
    """Save agent findings to a per-session collection."""
    if not session_id:
        return 0
    store = _get_session_store(session_id)
    meta = {"goal": goal[:100], "source": "agent_memory"}
    chunks = _split_text(content, max_len=1000, overlap=100)
    if not chunks:
        return 0
    store.add_texts(texts=chunks, metadatas=[meta] * len(chunks))
    return len(chunks)


def list_session_docs(session_id: str) -> list[dict]:
    """List documents in a session's collection."""
    if not session_id:
        return []
    store = _get_session_store(session_id)
    data = store._collection.get()
    docs = {}
    for doc, meta in zip(data["documents"], data["metadatas"]):
        goal = meta.get("goal", "unknown")
        if goal not in docs:
            docs[goal] = {"goal": goal, "chunks": 0}
        docs[goal]["chunks"] += 1
    return list(docs.values())


# ---------------------------------------------------------------------------
# Search (across all collections)
# ---------------------------------------------------------------------------

def search(query: str, k: int = 5, session_id: str = None) -> list[dict]:
    """Search vector store. If session_id given, search session + shared.
    Otherwise search shared only."""
    results = []

    # Search shared collection
    store = _get_store()
    if store._collection.count() > 0:
        shared = store.similarity_search_with_score(query, k=k)
        for doc, score in shared:
            results.append({
                "content": doc.page_content,
                "score": round(1 - score, 4),
                "metadata": doc.metadata,
                "source": "shared",
            })

    # Search session collection
    if session_id:
        sstore = _get_session_store(session_id)
        if sstore._collection.count() > 0:
            session_results = sstore.similarity_search_with_score(query, k=k)
            for doc, score in session_results:
                results.append({
                    "content": doc.page_content,
                    "score": round(1 - score, 4),
                    "metadata": doc.metadata,
                    "source": "session",
                })

    # Sort by score descending, return top k
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:k]


# ---------------------------------------------------------------------------
# File extraction
# ---------------------------------------------------------------------------

def extract_text(file_path: str = "", content_bytes: bytes = None, filename: str = "") -> str:
    name = filename or file_path
    ext = Path(name).suffix.lower()

    if ext == ".pdf":
        try:
            from pdfminer.high_level import extract_text as pdf_extract
            if content_bytes:
                import io
                return pdf_extract(io.BytesIO(content_bytes))
            return pdf_extract(file_path)
        except Exception:
            pass
        try:
            import subprocess
            result = subprocess.run(
                ["pdftotext", file_path, "-"],
                capture_output=True, text=True, timeout=30,
            )
            return result.stdout
        except Exception:
            return "(could not extract PDF text)"

    if content_bytes:
        return content_bytes.decode("utf-8", errors="replace")
    return Path(file_path).read_text(errors="replace") if Path(file_path).exists() else ""
