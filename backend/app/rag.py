"""
YojanaMitra RAG module — SQLite vector store + sentence-transformers.

Design:
- Embeddings computed with sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2).
  This model supports English, Telugu and Hindi natively.
- Vectors are stored in SQLite (backend/data/vector_store.db) alongside metadata.
  Numpy matrix is re-built in memory at startup for fast cosine similarity search.
- Graceful degradation: if sentence-transformers / torch are unavailable,
  _RAG_AVAILABLE is False and all public functions return empty results so the
  rest of the app continues to work using the existing keyword fallback.
- No paid services, no C compiler, no ONNX runtime required.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
import threading
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger("yojanamitra.rag")

# ── Paths ──────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
_DATA_DIR = _ROOT / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = _DATA_DIR / "vector_store.db"

_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# ── Optional imports ───────────────────────────────────────────────────────────
_RAG_AVAILABLE = False
_model = None
_embed_dim: int = 0
_lock = threading.Lock()

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    _RAG_AVAILABLE = True
    logger.info("RAG: sentence-transformers available. Model will load on first use.")
except Exception as exc:  # pragma: no cover
    logger.warning("RAG unavailable — %s. Using keyword retrieval fallback.", exc)


def _get_model() -> "SentenceTransformer":
    """Lazy-load the embedding model on first use (saves ~300 MB at startup)."""
    global _model, _embed_dim
    if _model is None:
        with _lock:
            if _model is None:  # double-checked locking
                logger.info("RAG: loading embedding model '%s'…", _EMBED_MODEL)
                _model = SentenceTransformer(_EMBED_MODEL)
                _embed_dim = _model.get_sentence_embedding_dimension()
                logger.info("RAG: model ready, embedding dim=%d.", _embed_dim)
    return _model


# ── Database init ──────────────────────────────────────────────────────────────
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id          TEXT PRIMARY KEY,
            text        TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_url  TEXT NOT NULL DEFAULT '',
            doc_type    TEXT NOT NULL DEFAULT 'scheme',
            scheme_id   TEXT NOT NULL DEFAULT '',
            page        INTEGER NOT NULL DEFAULT -1,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            section     TEXT NOT NULL DEFAULT '',
            embedding   BLOB NOT NULL
        )
    """)
    conn.commit()
    return conn


if _RAG_AVAILABLE:
    _db = _get_conn()
else:
    _db = None  # type: ignore[assignment]


# ── In-memory index ─────────────────────────────────────────────────────────────
# We keep a numpy matrix + ordered list of row IDs for fast cosine search.
_index_ids: list[str] = []
_index_matrix = None   # np.ndarray shape (N, D) or None


def _rebuild_index() -> None:
    """Load all embeddings from SQLite into a numpy matrix."""
    global _index_ids, _index_matrix
    if not _RAG_AVAILABLE or _db is None:
        return
    import numpy as np
    rows = _db.execute("SELECT id, embedding FROM chunks ORDER BY rowid").fetchall()
    if not rows:
        _index_ids = []
        _index_matrix = None
        return
    _index_ids = [r["id"] for r in rows]
    vecs = [np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]
    _index_matrix = np.vstack(vecs)  # (N, D)
    logger.info("RAG: index rebuilt — %d chunks.", len(_index_ids))


if _RAG_AVAILABLE:
    _rebuild_index()


# ── Public types ───────────────────────────────────────────────────────────────
class RagChunk(TypedDict):
    text: str
    source_name: str
    source_url: str
    doc_type: str
    scheme_id: str
    page: int
    chunk_index: int


# ── Chunking helpers ───────────────────────────────────────────────────────────
_MAX_CHUNK_CHARS = 900
_MIN_CHUNK_CHARS = 60


def _split_text(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks at sentence/paragraph boundaries."""
    text = re.sub(r"\s+", " ", text).strip()
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= max_chars:
            current = (current + " " + para).strip()
        else:
            if current:
                chunks.append(current)
            if len(para) > max_chars:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                buf = ""
                for sent in sentences:
                    if len(buf) + len(sent) + 1 <= max_chars:
                        buf = (buf + " " + sent).strip()
                    else:
                        if buf:
                            chunks.append(buf)
                        buf = sent[:max_chars]
                if buf:
                    chunks.append(buf)
                current = ""
            else:
                current = para
    if current:
        chunks.append(current)
    return [c for c in chunks if len(c) >= _MIN_CHUNK_CHARS]


def _chunk_id(source_name: str, chunk_index: int, text: str) -> str:
    digest = hashlib.sha256(
        f"{source_name}:{chunk_index}:{text[:80]}".encode()
    ).hexdigest()[:12]
    safe = re.sub(r"[^a-z0-9]", "_", source_name.lower()[:40])
    return f"{safe}_{chunk_index}_{digest}"


def _embed(texts: list[str]):  # returns np.ndarray
    import numpy as np
    model = _get_model()
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vecs.astype(np.float32)


# ── Public API ─────────────────────────────────────────────────────────────────
def rag_available() -> bool:
    return _RAG_AVAILABLE and _db is not None


def collection_size() -> int:
    if not rag_available():
        return 0
    row = _db.execute("SELECT COUNT(*) FROM chunks").fetchone()  # type: ignore[union-attr]
    return row[0]


def _upsert_chunks(
    ids: list[str],
    texts: list[str],
    metadatas: list[dict],
    embeddings,  # np.ndarray
) -> None:
    import numpy as np
    with _lock:
        for cid, text, meta, vec in zip(ids, texts, metadatas, embeddings):
            blob = vec.astype(np.float32).tobytes()
            _db.execute(  # type: ignore[union-attr]
                """INSERT INTO chunks
                   (id, text, source_name, source_url, doc_type, scheme_id,
                    page, chunk_index, section, embedding)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     text=excluded.text, source_name=excluded.source_name,
                     source_url=excluded.source_url, doc_type=excluded.doc_type,
                     scheme_id=excluded.scheme_id, page=excluded.page,
                     chunk_index=excluded.chunk_index, section=excluded.section,
                     embedding=excluded.embedding""",
                (cid, text, meta["source_name"], meta["source_url"],
                 meta["doc_type"], meta["scheme_id"], meta["page"],
                 meta["chunk_index"], meta.get("section", ""), blob),
            )
        _db.commit()  # type: ignore[union-attr]
    _rebuild_index()


def add_scheme_chunks(
    scheme_id: str,
    scheme_name: str,
    official_url: str,
    text_sections: dict[str, str],
) -> int:
    """Add structured scheme data as text chunks. Idempotent via deterministic IDs."""
    if not rag_available():
        return 0
    ids, texts, metas = [], [], []
    idx = 0
    for section, text in text_sections.items():
        for sub in _split_text(f"{section}: {text}"):
            cid = _chunk_id(scheme_id, idx, sub)
            ids.append(cid)
            texts.append(sub)
            metas.append({
                "source_name": scheme_name,
                "source_url": official_url,
                "doc_type": "scheme",
                "scheme_id": scheme_id,
                "page": -1,
                "chunk_index": idx,
                "section": section,
            })
            idx += 1
    if not ids:
        return 0
    embeddings = _embed(texts)
    _upsert_chunks(ids, texts, metas, embeddings)
    return len(ids)


def add_pdf_chunks(
    filename: str,
    official_url: str,
    pages_text: list[str],
    doc_type: str = "pdf",
) -> int:
    """Ingest a PDF's per-page text into the vector store. Returns chunks added."""
    if not rag_available():
        return 0
    ids, texts, metas = [], [], []
    idx = 0
    for page_num, page_text in enumerate(pages_text):
        for chunk in _split_text(page_text):
            cid = _chunk_id(filename, idx, chunk)
            ids.append(cid)
            texts.append(chunk)
            metas.append({
                "source_name": filename,
                "source_url": official_url,
                "doc_type": doc_type,
                "scheme_id": "",
                "page": page_num,
                "chunk_index": idx,
                "section": f"page_{page_num + 1}",
            })
            idx += 1
    if not ids:
        return 0
    embeddings = _embed(texts)
    _upsert_chunks(ids, texts, metas, embeddings)
    return len(ids)


def query_rag(question: str, n_results: int = 5) -> list[RagChunk]:
    """
    Semantic search over the vector store.
    Returns up to n_results chunks sorted by relevance (cosine similarity ≥ 0.30).
    Returns [] if RAG unavailable or collection empty.
    """
    if not rag_available() or _index_matrix is None or len(_index_ids) == 0:
        return []
    try:
        import numpy as np
        q_vec = _embed([question])[0]  # shape (D,)
        # Cosine similarity — vectors are already L2-normalised by sentence-transformers
        scores = _index_matrix @ q_vec  # shape (N,)
        top_k = min(n_results, len(_index_ids))
        top_indices = np.argsort(scores)[::-1][:top_k]

        chunks: list[RagChunk] = []
        with _lock:
            for i in top_indices:
                sim = float(scores[i])
                if sim < 0.30:
                    break
                cid = _index_ids[i]
                row = _db.execute(  # type: ignore[union-attr]
                    "SELECT * FROM chunks WHERE id=?", (cid,)
                ).fetchone()
                if row:
                    chunks.append(RagChunk(
                        text=row["text"],
                        source_name=row["source_name"],
                        source_url=row["source_url"],
                        doc_type=row["doc_type"],
                        scheme_id=row["scheme_id"],
                        page=row["page"],
                        chunk_index=row["chunk_index"],
                    ))
        return chunks
    except Exception as exc:
        logger.warning("RAG query failed: %s", exc)
        return []


def delete_pdf_chunks(filename: str) -> int:
    """Remove all chunks for a given PDF filename. Returns count removed."""
    if not rag_available():
        return 0
    with _lock:
        cur = _db.execute(  # type: ignore[union-attr]
            "DELETE FROM chunks WHERE source_name=? AND doc_type='pdf'", (filename,)
        )
        _db.commit()  # type: ignore[union-attr]
    _rebuild_index()
    return cur.rowcount


def format_rag_context(chunks: list[RagChunk]) -> str:
    """Format retrieved chunks into a compact context string for the LLM."""
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source_label = chunk["source_name"]
        if chunk["page"] >= 0:
            source_label += f" (page {chunk['page'] + 1})"
        parts.append(f"[Source {i}: {source_label}]\n{chunk['text']}")
    return "\n\n".join(parts)


def build_citations(chunks: list[RagChunk]) -> list[dict]:
    """Return deduplicated citation dicts for the API response."""
    seen: set[str] = set()
    citations: list[dict] = []
    for chunk in chunks:
        key = chunk["source_url"] or chunk["source_name"]
        if key in seen:
            continue
        seen.add(key)
        cite: dict = {
            "name": chunk["source_name"],
            "url": chunk["source_url"],
            "doc_type": chunk["doc_type"],
        }
        if chunk["page"] >= 0:
            cite["page"] = chunk["page"] + 1  # 1-indexed for display
        citations.append(cite)
    return citations
