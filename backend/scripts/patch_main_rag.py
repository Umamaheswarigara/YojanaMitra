"""
Patch script: integrate RAG into main.py
Run from backend directory:
  .\.venv\Scripts\python.exe scripts/patch_main_rag.py
"""
import sys
from pathlib import Path

src = Path("app/main.py").read_text(encoding="utf-8")

# ── 1. Add RAG imports after the pypdf import ──────────────────────────────────
old_import = "from pypdf import PdfReader"
new_import = """from pypdf import PdfReader

# RAG module — degrades gracefully if sentence-transformers is unavailable
from app import rag as _rag"""

if "from app import rag" not in src:
    src = src.replace(old_import, new_import, 1)
    print("✓ Added RAG import")
else:
    print("  RAG import already present — skipped")

# ── 2. Update /api/assistant to use RAG context ────────────────────────────────
old_assistant = '''@app.post("/api/assistant")
@_limiter.limit("30/minute")
async def assistant(request: Request, data: QuestionInput):
    relevant = _retrieve_schemes(data.question)
    if not relevant:
        return {"answer": _language_disclaimer(data.language), "sources": [], "grounded": True, "uncertain": True}
    intent = _question_intent(data.question)
    context = "\\n\\n".join(
        f"Scheme: {s['name']}\\nCategory: {s['category']}\\n"
        f"Relevant {intent} information: {_scheme_evidence(s, intent, 'en')}\\n"
        f"Official source: {s['official_url']}"
        for s in relevant
    )
    # Provider priority: Gemini → OpenAI → deterministic fallback
    answer = await _call_gemini(data.question, context, intent, data.language, data.history)
    if not answer:
        answer = await _call_openai(data.question, context, intent, data.language, data.history)
    if not answer:
        evidence = [_scheme_evidence(s, intent, data.language) for s in relevant]
        if intent == "overview" and any(s["id"] == "nsp-scholarships" for s in relevant) and len(relevant) == 1:
            answer = LOCALIZED_ANSWERS["nsp-scholarships"].get(data.language, {}).get("overview") or (
                "The National Scholarship Portal lists central and state scholarship schemes. Eligibility and benefits vary by scheme and academic year; check the official scheme list and eligibility checker for current options."
            )
        elif len(relevant) == 1:
            answer = evidence[0]
        else:
            answer = "\\n".join(f"{scheme['name']}: {fact}" for scheme, fact in zip(relevant, evidence))
    uncertain = intent == "deadline" or (intent == "benefits" and any(s["id"] == "nsp-scholarships" for s in relevant))
    return {
        "answer": answer,
        "sources": [{"name": s["name"], "url": s["official_url"]} for s in relevant],
        "grounded": True,
        "uncertain": uncertain,
    }'''

new_assistant = '''@app.post("/api/assistant")
@_limiter.limit("30/minute")
async def assistant(request: Request, data: QuestionInput):
    relevant = _retrieve_schemes(data.question)
    if not relevant:
        return {"answer": _language_disclaimer(data.language), "sources": [], "grounded": True, "uncertain": True}
    intent = _question_intent(data.question)

    # ── RAG: semantic retrieval from the vector store (if available) ──
    rag_chunks = _rag.query_rag(data.question, n_results=5)
    rag_context = _rag.format_rag_context(rag_chunks)

    # Combine scheme catalogue context + RAG context
    scheme_context = "\\n\\n".join(
        f"Scheme: {s['name']}\\nCategory: {s['category']}\\n"
        f"Relevant {intent} information: {_scheme_evidence(s, intent, 'en')}\\n"
        f"Official source: {s['official_url']}"
        for s in relevant
    )
    context = scheme_context
    if rag_context:
        context = f"{scheme_context}\\n\\n--- Additional retrieved context ---\\n{rag_context}"

    # Provider priority: Gemini → OpenAI → deterministic fallback
    answer = await _call_gemini(data.question, context, intent, data.language, data.history)
    if not answer:
        answer = await _call_openai(data.question, context, intent, data.language, data.history)
    if not answer:
        evidence = [_scheme_evidence(s, intent, data.language) for s in relevant]
        if intent == "overview" and any(s["id"] == "nsp-scholarships" for s in relevant) and len(relevant) == 1:
            answer = LOCALIZED_ANSWERS["nsp-scholarships"].get(data.language, {}).get("overview") or (
                "The National Scholarship Portal lists central and state scholarship schemes. Eligibility and benefits vary by scheme and academic year; check the official scheme list and eligibility checker for current options."
            )
        elif len(relevant) == 1:
            answer = evidence[0]
        else:
            answer = "\\n".join(f"{scheme['name']}: {fact}" for scheme, fact in zip(relevant, evidence))

    uncertain = intent == "deadline" or (intent == "benefits" and any(s["id"] == "nsp-scholarships" for s in relevant))

    # Merge scheme sources + RAG citations (deduplicated)
    scheme_sources = [{"name": s["name"], "url": s["official_url"], "doc_type": "scheme"} for s in relevant]
    rag_citations = _rag.build_citations(rag_chunks)
    seen_urls: set[str] = {src["url"] for src in scheme_sources}
    merged_sources = scheme_sources + [c for c in rag_citations if c["url"] not in seen_urls]

    return {
        "answer": answer,
        "sources": merged_sources,
        "grounded": True,
        "uncertain": uncertain,
        "rag_used": bool(rag_chunks),
    }'''

if "rag_chunks = _rag.query_rag" not in src:
    if old_assistant in src:
        src = src.replace(old_assistant, new_assistant, 1)
        print("✓ Updated assistant endpoint with RAG context")
    else:
        print("ERROR: Could not find assistant endpoint to patch. Check manually.")
        sys.exit(1)
else:
    print("  Assistant RAG already patched — skipped")

# ── 3. Add RAG status + ingest endpoints BEFORE the summarize endpoint ─────────
old_summarize_line = '@app.post("/api/documents/summarize")'
new_endpoints = '''@app.get("/api/rag/status")
def rag_status():
    """Return the current state of the RAG vector store."""
    return {
        "available": _rag.rag_available(),
        "chunk_count": _rag.collection_size(),
        "model": "paraphrase-multilingual-MiniLM-L12-v2" if _rag.rag_available() else None,
        "note": (
            "RAG is active and ready." if _rag.rag_available()
            else "RAG is not available. Install sentence-transformers to enable it."
        ),
    }


@app.post("/api/rag/ingest")
@_limiter.limit("5/minute")
async def rag_ingest(
    request: Request,
    file: UploadFile = File(...),
    source_url: str = "",
):
    """
    Ingest a government scheme PDF into the RAG vector store.

    - Validates file type and size (max 10 MB).
    - Extracts text using pypdf.
    - Splits into chunks and stores embeddings.
    - Idempotent: re-uploading the same filename replaces existing chunks.
    """
    if not _rag.rag_available():
        raise HTTPException(503, "RAG is not available. Install sentence-transformers to enable document ingestion.")
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Please upload a PDF file.")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "This PDF is over the 10 MB limit. Choose a smaller file.")
    if not content.startswith(b"%PDF"):
        raise HTTPException(400, "This file does not appear to be a valid PDF.")
    filename = (file.filename or "document.pdf")[:120]
    # Validate source URL if provided
    if source_url and not source_url.startswith(("http://", "https://")):
        raise HTTPException(422, "source_url must start with http:// or https://")
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(content))
        pages_text = [page.extract_text() or "" for page in reader.pages]
    except Exception:
        raise HTTPException(400, "We could not read this PDF. Try a valid, unprotected PDF.")
    total_text = "".join(pages_text).strip()
    if len(total_text) < 80:
        raise HTTPException(422, "This PDF has no readable text. Scanned PDFs need OCR, which is not supported.")
    # Remove old chunks for this file (re-ingest = replace)
    removed = _rag.delete_pdf_chunks(filename)
    # Ingest new chunks
    added = _rag.add_pdf_chunks(
        filename=filename,
        official_url=source_url,
        pages_text=pages_text,
        doc_type="pdf",
    )
    return {
        "filename": filename,
        "pages": len(reader.pages),
        "chunks_added": added,
        "chunks_replaced": removed,
        "rag_total_chunks": _rag.collection_size(),
        "note": "Document ingested into RAG. It will appear in assistant answers for relevant queries.",
    }


'''

if '"available": _rag.rag_available()' not in src:
    if old_summarize_line in src:
        src = src.replace(old_summarize_line, new_endpoints + old_summarize_line, 1)
        print("✓ Added /api/rag/status and /api/rag/ingest endpoints")
    else:
        print("ERROR: Could not find summarize endpoint to place RAG endpoints before.")
        sys.exit(1)
else:
    print("  RAG endpoints already present — skipped")

Path("app/main.py").write_text(src, encoding="utf-8")
print("\\n✓ main.py patched successfully.")
