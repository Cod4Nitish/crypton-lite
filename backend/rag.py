"""Local RAG: PDF/TXT/MD -> page-aware chunks -> Ollama embeddings -> ChromaDB.

Unchanged files are skipped by SHA-256 (documents table), so re-uploading is free.
Search results carry doc name + page so citations are always real.
"""
import hashlib
import io
import os
import re

import chromadb
import httpx
from pypdf import PdfReader

from . import store
from . import agent

EMBED_MODEL = os.environ.get("CRYPTON_EMBED_MODEL", "nomic-embed-text")
CHROMA_DIR = os.environ.get("CRYPTON_CHROMA", os.path.join(os.path.dirname(__file__), "..", "data", "chroma"))
CHUNK_CHARS = 900
OVERLAP = 150
# Cosine distance above this = not relevant enough to count as evidence.
# Calibrated on the sample agenda: relevant queries scored 0.31-0.44, off-topic 0.46+.
MAX_DISTANCE = float(os.environ.get("CRYPTON_MAX_DISTANCE", "0.455"))
ALLOWED = {".pdf", ".txt", ".md", ".markdown"}

_client = None


def collection():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
    return _client.get_or_create_collection("knowledge", metadata={"hnsw:space": "cosine"})


def embed(texts: list[str], kind: str = "document") -> list[list[float]]:
    # nomic-embed-text expects task prefixes for best retrieval quality.
    prefix = "search_document: " if kind == "document" else "search_query: "
    r = httpx.post(f"{agent.OLLAMA_URL}/api/embed", json={"model": EMBED_MODEL, "input": [prefix + t for t in texts]}, timeout=120)
    r.raise_for_status()
    return r.json()["embeddings"]


def extract(name: str, data: bytes) -> list[tuple[int | None, str]]:
    """Returns [(page_number or None, text)]."""
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED:
        raise ValueError(f"unsupported file type {ext}; use PDF, TXT or Markdown")
    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        return [(i + 1, (p.extract_text() or "")) for i, p in enumerate(reader.pages)]
    return [(None, data.decode("utf-8", errors="replace"))]


def chunk(text: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):  # prefer to cut at a paragraph/sentence boundary
            cut = max(text.rfind("\n", start + CHUNK_CHARS // 2, end), text.rfind(". ", start + CHUNK_CHARS // 2, end))
            if cut > start:
                end = cut + 1
        out.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - OVERLAP, start + 1)
    return [c for c in out if c]


def ingest(name: str, data: bytes, source_id: str | None = None) -> dict:
    """Index a file. Returns {"document": row, "cached": bool}."""
    sha = hashlib.sha256(data).hexdigest()
    existing = store.find_document(sha)
    if existing:
        return {"document": existing, "cached": True}
    pages = extract(name, data)
    ids, docs, metas = [], [], []
    for page, text in pages:
        for i, c in enumerate(chunk(text)):
            ids.append(f"{sha[:16]}:{page or 0}:{i}")
            docs.append(c)
            metas.append({"doc": name, "page": page or 0, "sha": sha, "source": source_id or "file"})
    if not docs:
        raise ValueError("no extractable text (scanned PDFs need OCR, which is not supported)")
    vectors = []
    for i in range(0, len(docs), 32):
        vectors += embed(docs[i:i + 32])
    collection().upsert(ids=ids, documents=docs, metadatas=metas, embeddings=vectors)
    row = store.add_document(name, sha, len(pages) if name.lower().endswith(".pdf") else None, len(docs))
    return {"document": row, "cached": False}


def wipe() -> None:
    """Drop the whole vector collection (demo reset)."""
    global _client
    collection()
    _client.delete_collection("knowledge")


def remove(doc_id: int) -> dict | None:
    row = store.delete_document(doc_id)
    if row:
        collection().delete(where={"sha": row["sha256"]})
    return row


def search(query: str, k: int = 4) -> dict:
    """Returns {"chunks": [...], "insufficient": bool}. Only chunks under MAX_DISTANCE count."""
    col = collection()
    if col.count() == 0:
        return {"chunks": [], "insufficient": True, "reason": "knowledge base is empty"}
    res = col.query(query_embeddings=embed([query], "query"), n_results=min(k, col.count()))
    chunks = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        if dist <= MAX_DISTANCE:
            chunks.append({"doc": meta["doc"], "page": meta["page"] or None, "text": doc, "score": round(1 - dist, 3)})
    return {"chunks": chunks, "insufficient": not chunks,
            **({"reason": "no passage was relevant enough"} if not chunks else {})}
