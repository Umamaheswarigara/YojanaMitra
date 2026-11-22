"""
patch_backend_v3.py — fixes injection validator and TTS length check.
Run from backend/ directory.
"""
from pathlib import Path

main_path = Path("app/main.py")
src = main_path.read_text(encoding="utf-8")

# ── Fix 1: Pydantic v2 @field_validator for injection defence ─────────────────
old_question_model = '''_INJECTION_PATTERNS = re.compile(
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

new_question_model = '''from pydantic import field_validator as _field_validator

_INJECTION_PATTERNS = re.compile(
    r"ignore previous instructions?|you are now|disregard|jailbreak|system prompt",
    re.IGNORECASE,
)

class QuestionInput(BaseModel):
    question: str = Field(min_length=3, max_length=1500)
    language: Literal["en", "te", "hi"] = "en"
    history: list[ConversationTurn] = Field(default_factory=list)

    @_field_validator("question")
    @classmethod
    def _check_injection(cls, v: str) -> str:
        v = v.strip()
        if _INJECTION_PATTERNS.search(v):
            raise ValueError("Invalid question content")
        return v'''

if old_question_model in src:
    src = src.replace(old_question_model, new_question_model)
    print("✓ Fixed QuestionInput field_validator (Pydantic v2)")
else:
    print("✗ QuestionInput block not found — checking alternate")
    if "_field_validator" in src:
        print("  Already patched.")
    else:
        print("  ERROR: Need manual fix.")

# ── Fix 2: TTS — reject text > 500 chars before truncating ───────────────────
old_tts_text = '''    text = str(body.get("text", "")).strip()[:500]
    language = str(body.get("language", "en"))
    if not text:
        raise HTTPException(422, "text is required")
    if len(text) > 500:
        raise HTTPException(422, "text must be 500 characters or fewer")'''

new_tts_text = '''    raw_text = str(body.get("text", "")).strip()
    language = str(body.get("language", "en"))
    if not raw_text:
        raise HTTPException(422, "text is required")
    if len(raw_text) > 500:
        raise HTTPException(422, "text must be 500 characters or fewer")
    text = raw_text'''

if old_tts_text in src:
    src = src.replace(old_tts_text, new_tts_text)
    print("✓ Fixed TTS length check (now rejects before truncating)")
else:
    print("✗ TTS text block not found")

main_path.write_text(src, encoding="utf-8")
print("\nPatches applied.")
