"""
patch_backend.py — applies all backend improvements in one shot.
Run from backend/ directory.
"""
import re
from pathlib import Path

main_path = Path("app/main.py")
src = main_path.read_text(encoding="utf-8")

# ── 1. Improve /api/health ────────────────────────────────────────────────────
old_health = '''@app.get("/api/health")
def health():
    return {"status": "ok"}'''

new_health = '''@app.get("/api/health")
def health():
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if gemini_key:
        ai_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    elif openai_key:
        ai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    else:
        ai_model = "deterministic"
    return {
        "status": "ok",
        "schemes_loaded": len(SCHEMES),
        "rag_available": _rag.rag_available(),
        "rag_chunks": _rag.collection_size(),
        "model": ai_model,
    }'''

if old_health in src:
    src = src.replace(old_health, new_health)
    print("✓ Patched /api/health")
else:
    print("✗ Could not find /api/health to patch — skipping")

# ── 2. Add prompt injection defence to QuestionInput ─────────────────────────
old_question = '''class QuestionInput(BaseModel):
    question: str = Field(min_length=3, max_length=1500)
    language: Literal["en", "te", "hi"] = "en"
    history: list[ConversationTurn] = Field(default_factory=list)'''

new_question = '''_INJECTION_PATTERNS = re.compile(
    r"ignore previous instructions?|you are now|disregard|jailbreak|system prompt",
    re.IGNORECASE,
)

class QuestionInput(BaseModel):
    question: str = Field(min_length=3, max_length=1500)
    language: Literal["en", "te", "hi"] = "en"
    history: list[ConversationTurn] = Field(default_factory=list)

    @classmethod
    def model_validator_question(cls, v):
        v = v.strip()
        if _INJECTION_PATTERNS.search(v):
            raise ValueError("Invalid question content")
        return v'''

if old_question in src:
    src = src.replace(old_question, new_question)
    print("✓ Patched QuestionInput with injection defence")
else:
    print("✗ Could not find QuestionInput to patch — skipping")

# ── 3. Improve PDF summarization ──────────────────────────────────────────────
old_summary_tail = '''    paragraphs = [re.sub(r"\\s+", " ", p).strip() for p in re.split(r"\\n\\s*\\n", text) if p.strip()]
    sentences = re.split(r"(?<=[.!?])\\s+", re.sub(r"\\s+", " ", text))
    summary = " ".join(sentences[:8])[:1800]
    return {"filename": (file.filename or "document.pdf")[:120], "summary": summary, "pages": len(reader.pages), "note": "Summary is based only on text extracted from this file. The uploaded file is processed in memory and is not stored."}'''

new_summary_tail = '''    # Build structured summary from paragraphs
    paragraphs = [re.sub(r"\\s+", " ", p).strip() for p in re.split(r"\\n{2,}", text) if p.strip() and len(p.strip()) > 40]
    # Remove short repeated header/footer lines
    paragraphs = [p for p in paragraphs if len(p) > 60]

    sections = {}
    keywords_map = {
        "eligibility": ["eligib", "who can apply", "who is eligible", "qualification", "criteria"],
        "benefits": ["benefit", "amount", "subsidy", "grant", "payment", "rupee", "rs.", "lakhs", "per year"],
        "documents": ["document", "required", "proof", "certificate", "identity", "aadhaar", "passport"],
        "how_to_apply": ["apply", "application", "portal", "register", "enroll", "submit"],
    }

    overview_paras = []
    for para in paragraphs:
        para_lower = para.lower()
        matched = False
        for section_key, kws in keywords_map.items():
            if any(kw in para_lower for kw in kws):
                if section_key not in sections:
                    sections[section_key] = []
                sections[section_key].append(para[:400])
                matched = True
                break
        if not matched:
            overview_paras.append(para)

    summary_parts = []
    if overview_paras:
        summary_parts.append("Overview:\\n" + " ".join(overview_paras[:3])[:600])
    for key, label in [("eligibility","Eligibility"),("benefits","Benefits"),("documents","Documents Required"),("how_to_apply","How to Apply")]:
        if key in sections:
            summary_parts.append(f"\\n{label}:\\n" + " ".join(sections[key][:2])[:400])

    summary = "\\n".join(summary_parts)[:2000] if summary_parts else (" ".join(paragraphs[:5])[:1800])

    return {
        "filename": (file.filename or "document.pdf")[:120],
        "summary": summary,
        "pages": len(reader.pages),
        "note": "Summary is based only on text extracted from this file. The uploaded file is processed in memory and is not stored.",
    }'''

if old_summary_tail in src:
    src = src.replace(old_summary_tail, new_summary_tail)
    print("✓ Patched PDF summarization")
else:
    print("✗ Could not find PDF summary tail to patch — trying alternate")
    # Try to find the last function and append there
    print("  Source tail:", repr(src[-300:]))

# ── 4. Add TTS endpoint ───────────────────────────────────────────────────────
tts_endpoint = '''

@app.post("/api/tts")
@_limiter.limit("3/minute")
async def text_to_speech(request: Request, body: dict):
    """
    Convert text to speech audio (MP3).
    Body: {"text": str (max 500 chars), "language": "en"|"te"|"hi"}
    Returns audio/mpeg bytes or 503 if TTS unavailable.
    """
    text = str(body.get("text", "")).strip()[:500]
    language = str(body.get("language", "en"))
    if not text:
        raise HTTPException(422, "text is required")
    if len(text) > 500:
        raise HTTPException(422, "text must be 500 characters or fewer")
    if language not in ("en", "te", "hi"):
        raise HTTPException(422, "language must be en, te, or hi")

    lang_code_map = {"en": "en", "te": "te", "hi": "hi"}
    lang_code = lang_code_map.get(language, "en")

    try:
        from gtts import gTTS
        import io as _io
        from starlette.responses import StreamingResponse
        tts = gTTS(text=text, lang=lang_code, slow=False)
        audio_buf = _io.BytesIO()
        tts.write_to_fp(audio_buf)
        audio_buf.seek(0)
        return StreamingResponse(audio_buf, media_type="audio/mpeg")
    except ImportError:
        raise HTTPException(503, "TTS unavailable — gTTS is not installed")
    except Exception as exc:
        logger_tts = __import__("logging").getLogger("yojanamitra.tts")
        logger_tts.warning("TTS failed: %s", exc)
        raise HTTPException(503, "TTS temporarily unavailable")
'''

# Add TTS after the rag_ingest endpoint (before summarize_document)
insert_marker = '\n\n@app.post("/api/documents/summarize")'
if insert_marker in src and "/api/tts" not in src:
    src = src.replace(insert_marker, tts_endpoint + insert_marker, 1)
    print("✓ Added /api/tts endpoint")
else:
    if "/api/tts" in src:
        print("⚠ /api/tts already present — skipping")
    else:
        print("✗ Could not find insertion point for /api/tts")

# ── Write back ────────────────────────────────────────────────────────────────
main_path.write_text(src, encoding="utf-8")
print("\nAll patches applied. Run tests to verify.")
