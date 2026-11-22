import json
import io
import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from pypdf import PdfReader

# RAG module — degrades gracefully if sentence-transformers is unavailable
from app import rag as _rag
# Auth module — user registration, login, JWT, saved schemes, history
from app.auth import (
    RegisterRequest as _RegisterRequest,
    LoginRequest as _LoginRequest,
    create_user as _create_user,
    get_user_by_email as _get_user_by_email,
    verify_password as _verify_password,
    create_access_token as _create_access_token,
    get_current_user as _get_current_user,
    get_optional_user as _get_optional_user,
    get_saved_schemes as _get_saved_schemes,
    save_scheme as _save_scheme,
    unsave_scheme as _unsave_scheme,
    get_conversation_history as _get_conv_history,
    save_conversation_turn as _save_conv_turn,
    clear_conversation_history as _clear_conv_history,
)


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
with (ROOT / "data" / "schemes.json").open(encoding="utf-8") as f:
    SCHEMES = json.load(f)

app = FastAPI(title="YojanaMitra API", version="1.0.0")
_cors_env = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
_limiter = Limiter(key_func=get_remote_address, default_limits=[])
app.state.limiter = _limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class EligibilityInput(BaseModel):
    occupation: Literal["student", "farmer", "woman", "small_business", "general", "other"]
    phase: Literal["questions", "assess"] = "questions"
    step: int = Field(default=1, ge=1, le=3)
    answers: dict[str, str] = Field(default_factory=dict)


class ConversationTurn(BaseModel):
    role: Literal["user", "model"]
    text: str = Field(max_length=3000)


from pydantic import field_validator as _field_validator

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
        return v


def _normalize_search_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).strip()


def _search_fields(scheme: dict) -> dict[str, str]:
    return {
        "name": scheme.get("name", ""),
        "aliases": " ".join(scheme.get("aliases", [])),
        "keywords": " ".join(scheme.get("keywords", [])),
        "category": scheme.get("category", ""),
        "details": " ".join([
            scheme.get("description", ""), scheme.get("beneficiaries", ""),
            *scheme.get("eligibility", []), *scheme.get("benefits", []), *scheme.get("application", []),
        ]),
    }


def _token_matches(query_token: str, candidate_tokens: set[str]) -> bool:
    if query_token in candidate_tokens:
        return True
    if len(query_token) >= 3 and any(token.startswith(query_token) or query_token.startswith(token) for token in candidate_tokens):
        return True
    # Permit one-character edits for longer words, while avoiding fuzzy matches
    # on short/common terms such as "pm" or "sc".
    return len(query_token) >= 4 and any(
        abs(len(token) - len(query_token)) <= 2 and SequenceMatcher(None, query_token, token).ratio() >= 0.78
        for token in candidate_tokens
    )


def _search_score(scheme: dict, query: str) -> int | None:
    normalized_query = _normalize_search_text(query)
    query_tokens = normalized_query.split()
    if not query_tokens:
        return 0
    fields = {key: _normalize_search_text(value) for key, value in _search_fields(scheme).items()}
    if len(normalized_query) >= 3 and any(normalized_query in value for value in fields.values()):
        # Exact phrase matches should rank above token/fuzzy matches.
        return 100 + (40 if normalized_query in fields["name"] else 25 if normalized_query in fields["aliases"] else 0)

    weights = {"name": 8, "aliases": 7, "keywords": 5, "category": 4, "details": 2}
    score = 0
    for token in query_tokens:
        matched_fields = [
            key for key, value in fields.items()
            if _token_matches(token, set(value.split()))
        ]
        if not matched_fields:
            return None
        score += max(weights[key] for key in matched_fields)
    return score


def _matches(scheme: dict, query: str) -> bool:
    return _search_score(scheme, query) is not None


@app.get("/api/health")
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
    }


@app.get("/api/schemes")
def list_schemes(q: str = "", category: str = ""):
    if len(q) > 120 or len(category) > 80:
        raise HTTPException(422, "Search text is too long.")
    result = [s for s in SCHEMES if (not q or _matches(s, q)) and (not category or s["category"].casefold() == category.casefold())]
    if q:
        result.sort(key=lambda scheme: _search_score(scheme, q) or 0, reverse=True)
    return {"items": result, "count": len(result)}


@app.get("/api/schemes/{scheme_id}")
def get_scheme(scheme_id: str):
    scheme = next((s for s in SCHEMES if s["id"] == scheme_id), None)
    if not scheme:
        raise HTTPException(404, "Scheme not found. Browse all schemes and try again.")
    return scheme


ELIGIBILITY_AUDIENCES = {
    "student": "Students", "farmer": "Farmers", "woman": "Women",
    "small_business": "Small Business Owners", "general": "General Public",
}

CHOICES = {
    "gender": [("female", "Female"), ("male", "Male"), ("another", "Another identity"), ("unknown", "Not sure / prefer not to say")],
    "income_band": [("under_1l", "Below ₹1 lakh"), ("1_3l", "₹1–3 lakh"), ("3_6l", "₹3–6 lakh"), ("6_8l", "₹6–8 lakh"), ("8_9l", "Above ₹8–9 lakh"), ("over_9l", "Above ₹9 lakh"), ("unknown", "Not sure / prefer not to say")],
    "age_band": [("under_18", "Under 18"), ("18_40", "18–40"), ("41_55", "41–55"), ("over_55", "Over 55"), ("unknown", "Not sure / prefer not to say")],
    "women_age": [("under_18", "Under 18"), ("18_to_18y6m", "18 to 18 years 6 months"), ("18y7m_to_55", "18 years 7 months to 55 years"), ("over_55", "Over 55"), ("unknown", "Not sure / prefer not to say")],
    "yes_no": [("yes", "Yes"), ("no", "No"), ("unknown", "Not sure / prefer not to say")],
    "unknown": [("yes", "Yes"), ("no", "No"), ("unknown", "Not sure / skip")],
}

def _q(field: str, label: str, choices: str = "yes_no") -> dict:
    return {"id": field, "label": label, "type": "select", "options": [{"value": v, "label": text} for v, text in CHOICES[choices]], "optional": True}

# Choices are shared across questions so answer validation is strict and reusable.
CHOICES.update({
    "study_track": [("technical_degree", "Technical degree"), ("technical_diploma", "Technical diploma"), ("school", "School"), ("college_other", "Other college/university course"), ("other", "Other"), ("unknown", "Not sure / skip")],
    "study_year": [("first_year", "First year"), ("second_lateral", "Second year via lateral entry"), ("other_year", "Another year"), ("class_8", "Class VIII"), ("class_9_10", "Class IX or X"), ("unknown", "Not sure / skip")],
    "category": [("yes", "Yes"), ("no", "No"), ("unknown", "Not sure / prefer not to say")],
    "maternity": [("pregnant", "Pregnant"), ("recent_child", "Child recently born"), ("no", "No"), ("unknown", "Prefer not to say")],
    "woman_interest": [("maternity", "Maternity support"), ("lpg", "LPG connection"), ("savings", "Savings for a girl child"), ("livelihood", "Rural livelihood group"), ("all", "All areas"), ("unknown", "Not sure / skip")],
    "enterprise_stage": [("planning", "Planning a business"), ("operating", "Operating a business"), ("street_vendor", "Street vendor"), ("traditional_artisan", "Traditional artisan/craftsperson"), ("unknown", "Not sure / skip")],
    "enterprise_type": [("yes", "Yes"), ("no", "No"), ("unknown", "Not sure / skip")],
})

ELIGIBILITY_QUESTIONS = {
    "student": [
        _q("gender", "What is your gender?", "gender"),
        _q("study_track", "What are you currently studying?", "study_track"),
        _q("study_year", "Which study year or stage applies?", "study_year"),
        _q("income_band", "What is your family’s approximate annual income?", "income_band"),
        _q("institution_approved", "Is your technical institution AICTE-approved?"),
        _q("income_certificate", "Can you provide the required family income certificate?"),
        _q("girls_limit", "Would this applicant exceed the scheme’s limit of two girl students per family?"),
        _q("social_category", "Do you belong to a category specified by the scholarship you are considering?", "category"),
        _q("school_stage", "Are you currently studying in Class IX or X?", "yes_no"),
        _q("scholarship_selected", "Have you been selected under the relevant merit/selection process?", "yes_no"),
    ],
    "farmer": [
        _q("cultivable_land", "Does your farmer family own cultivable agricultural land?"),
        _q("land_recorded", "Is that land recorded with the State/UT?"),
        _q("pm_kisan_excluded", "Do any of the PM-KISAN exclusion categories apply to your family?"),
        _q("notified_crop_area", "Is your crop and area notified for the current insurance season?"),
        _q("insurable_interest", "Do you have an insurable interest in the notified crop?"),
        _q("kcc_activity", "Are you seeking credit for crop or eligible allied agricultural activity?"),
        _q("micro_irrigation", "Are you seeking an approved drip or sprinkler micro-irrigation system?"),
        _q("state_agri_approval", "Has your State/UT agriculture department confirmed this activity under its current plan?"),
    ],
    "woman": [
        _q("women_age", "Which age range are you in?", "women_age"),
        _q("maternity_stage", "Are you pregnant or caring for a recently born child?", "maternity"),
        _q("pmmvy_category", "Do you belong to a beneficiary category listed for PMMVY?"),
        _q("pmmvy_exclusion", "Are you a regular government/PSU employee or receiving similar maternity benefit under another law?"),
        _q("lpg_connection", "Does anyone in your household already have an LPG connection?"),
        _q("girl_child_under10", "Are you a parent/guardian of a girl child under 10?"),
        _q("rural_shg", "Are you part of a rural women-led self-help group?"),
        _q("woman_interest", "Which support area are you exploring?", "woman_interest"),
    ],
    "small_business": [
        _q("enterprise_stage", "Which best describes your business?", "enterprise_stage"),
        _q("enterprise_type", "Is this an income-generating micro enterprise?", "enterprise_type"),
        _q("applicant_age_18", "Are you 18 or older?"),
        _q("new_project", "Is this a new enterprise/project?"),
        _q("vendor_identified", "Are you identified or certified as a street vendor by your local body?"),
        _q("notified_artisan_trade", "Do you work in one of PM Vishwakarma’s 18 notified traditional trades?"),
    ],
    "general": [
        _q("age_band", "Which age range are you in?", "age_band"),
        _q("urban_resident", "Do you currently live in an urban area?"),
        _q("pucca_house", "Does your family own a pucca house anywhere in India?"),
        _q("income_band", "What is your household’s approximate annual income?", "income_band"),
        _q("pmjay_database", "Has the official PM-JAY lookup identified your family as a beneficiary?", "yes_no"),
        _q("indian_citizen", "Are you an Indian citizen?"),
        _q("savings_account", "Do you have a savings bank or post-office account?"),
        _q("housing_prior_benefit", "Has your family received a government housing benefit in the specified prior period?"),
    ],
}
SCHEME_RULES = {
    "pm-kisan": {"checks": [("cultivable_land", {"yes"}, "Family owns cultivable land"), ("land_recorded", {"yes"}, "Land is recorded with the State/UT"), ("pm_kisan_excluded", {"no"}, "No stated exclusion category applies") ]},
    "pmfby": {"checks": [("notified_crop_area", {"yes"}, "Crop and area are notified for the season"), ("insurable_interest", {"yes"}, "Applicant has an insurable interest")], "unknown": ["Season-specific State/UT notifications and documentation still require official confirmation."]},
    "kisan-credit-card": {"checks": [("kcc_activity", {"yes"}, "Activity is within eligible agricultural/allied credit purposes")], "unknown": ["The participating lender must assess eligibility and credit limit."]},
    "pmksy-per-drop-more-crop": {"checks": [("micro_irrigation", {"yes"}, "Applicant seeks an eligible micro-irrigation system"), ("state_agri_approval", {"yes"}, "State/UT confirms eligibility under its current plan")]},
    "nsp-scholarships": {"unknown": ["NSP is a portal; eligibility depends on the individual scholarship and academic year."]},
    "pm-usp-csss": {"checks": [("study_track", {"college_other", "technical_degree", "technical_diploma"}, "Pursuing a higher education course"), ("scholarship_selected", {"yes"}, "Meets the current merit/selection criteria")], "unknown": ["Current income ceiling, board merit position, course and other annual rules need scheme-specific verification."]},
    "nmmss": {"checks": [("study_year", {"class_8"}, "At the relevant Class VIII selection stage"), ("scholarship_selected", {"yes"}, "Selected under the State/UT process")], "unknown": ["Current income, school-type and examination rules must be checked in State/UT guidelines."]},
    "pm-yasasvi": {"checks": [("social_category", {"yes"}, "Belongs to a category covered by the selected sub-scheme")], "unknown": ["PM-YASASVI sub-scheme, class/course, institution, income and year-specific conditions require confirmation."]},
    "national-overseas-scholarship": {"checks": [("social_category", {"yes"}, "Belongs to a category covered by the current call")], "unknown": ["Current course, income, admission and annual call conditions require official verification."]},
    "pre-matric-sc-scholarship": {"checks": [("social_category", {"yes"}, "Belongs to a category covered by the selected component"), ("school_stage", {"yes"}, "Studying in Class IX or X")], "unknown": ["Income ceiling and component-specific rules must be checked in current guidelines."]},
    "aicte-pragati-degree": {"checks": [("gender", {"female"}, "Applicant is a girl student"), ("study_track", {"technical_degree"}, "Pursuing a technical degree"), ("study_year", {"first_year", "second_lateral"}, "In first year or second year through lateral entry"), ("income_band", {"under_1l", "1_3l", "3_6l", "6_8l"}, "Family income is not above ₹8 lakh"), ("institution_approved", {"yes"}, "Institution is AICTE-approved"), ("income_certificate", {"yes"}, "Required State/UT income certificate is available"), ("girls_limit", {"no"}, "Family limit of two girl students is not exceeded")]},
    "aicte-pragati-diploma": {"checks": [("gender", {"female"}, "Applicant is a girl student"), ("study_track", {"technical_diploma"}, "Pursuing a technical diploma"), ("study_year", {"first_year", "second_lateral"}, "In first year or second year through lateral entry"), ("income_band", {"under_1l", "1_3l", "3_6l", "6_8l"}, "Family income is not above ₹8 lakh"), ("institution_approved", {"yes"}, "Institution is AICTE-approved"), ("income_certificate", {"yes"}, "Required State/UT income certificate is available"), ("girls_limit", {"no"}, "Family limit of two girl students is not exceeded")]},
    "pmmvy": {"checks": [("women_age", {"18y7m_to_55"}, "Applicant is within PMMVY's published age range"), ("maternity_stage", {"pregnant", "recent_child"}, "Pregnancy/eligible child context applies"), ("pmmvy_category", {"yes"}, "Belongs to a listed PMMVY beneficiary category"), ("pmmvy_exclusion", {"no"}, "No listed employment/similar-benefit exclusion applies")], "unknown": ["Installment-specific registration, antenatal check-up, birth and immunization conditions must be confirmed from the official guidance."]},
    "sukanya-samriddhi": {"checks": [("girl_child_under10", {"yes"}, "Girl child is under 10")], "unknown": ["Account opening and family/account limits must be verified under current rules."]},
    "pm-ujjwala": {"checks": [("gender", {"female"}, "Applicant is a woman"), ("women_age", {"18_to_18y6m", "18y7m_to_55", "over_55"}, "Applicant is at least 18"), ("lpg_connection", {"no"}, "Household has no existing LPG connection")], "unknown": ["Current household deprivation/eligibility criteria and required documents need official confirmation."]},
    "day-nrlm": {"checks": [("rural_shg", {"yes"}, "Member of a rural women-led self-help group")], "unknown": ["State Rural Livelihood Mission and group-specific criteria must be confirmed."]},
    "pm-mudra": {"checks": [("enterprise_stage", {"planning", "operating", "street_vendor", "traditional_artisan"}, "Income-generating business is proposed/operating"), ("enterprise_type", {"yes"}, "Business is an income-generating micro enterprise")], "unknown": ["The lending institution decides credit eligibility, terms and appraisal; Tarun Plus has additional prior-loan conditions."]},
    "pmegp": {"checks": [("applicant_age_18", {"yes"}, "Applicant is over 18"), ("new_project", {"yes"}, "Project is a new enterprise")], "unknown": ["Project cost/category education thresholds and negative-list rules need current guideline verification."]},
    "pm-svanidhi": {"checks": [("enterprise_stage", {"street_vendor"}, "Applicant is a street vendor"), ("vendor_identified", {"yes"}, "Vendor identification/ULB requirements are met")], "unknown": ["Current vendor certificate/letter-of-recommendation and lender criteria require confirmation."]},
    "pm-vishwakarma": {"checks": [("applicant_age_18", {"yes"}, "Applicant meets the adult age condition"), ("notified_artisan_trade", {"yes"}, "Work is in a notified traditional trade")], "unknown": ["Family, self-employment, prior-benefit and verification rules require official confirmation."]},
    "pm-jay": {"checks": [("pmjay_database", {"yes"}, "Official beneficiary lookup lists the family")], "unknown": ["Final beneficiary status and any State/UT-expanded criteria must be confirmed in the official database."]},
    "pmay-urban-2": {"checks": [("urban_resident", {"yes"}, "Household is in an urban area"), ("pucca_house", {"no"}, "Family does not own a pucca house"), ("housing_prior_benefit", {"no"}, "No disqualifying prior housing benefit"), ("income_band", {"under_1l", "1_3l", "3_6l", "6_8l", "8_9l"}, "Household income is within the published PMAY-U 2.0 bands")], "unknown": ["Component-specific and State/UT validation still require confirmation."]},
    "atal-pension-yojana": {"checks": [("indian_citizen", {"yes"}, "Applicant is an Indian citizen"), ("age_band", {"18_40"}, "Applicant is aged 18 to 40"), ("savings_account", {"yes"}, "Applicant has an eligible savings account")], "unknown": ["Current joining exclusions and contribution choice must be checked with the participating bank/post office."]},
}

INTEREST_SCHEMES = {
    "woman": {"maternity": {"pmmvy"}, "lpg": {"pm-ujjwala"}, "savings": {"sukanya-samriddhi"}, "livelihood": {"day-nrlm"}},
}


def _eligibility_schemes(occupation: str, answers: dict[str, str] | None = None) -> list[dict]:
    category = ELIGIBILITY_AUDIENCES.get(occupation)
    if not category:
        return []
    selected = [scheme for scheme in SCHEMES if scheme["category"] == category]
    interest = (answers or {}).get("woman_interest", "")
    if occupation == "woman" and interest in INTEREST_SCHEMES["woman"]:
        selected = [scheme for scheme in selected if scheme["id"] in INTEREST_SCHEMES["woman"][interest]]
    return selected


def _assess_scheme(scheme: dict, answers: dict[str, str]) -> dict:
    rule = SCHEME_RULES.get(scheme["id"], {})
    satisfied, unmet, unknown = [], [], list(rule.get("unknown", []))
    effective_answers = dict(answers)
    # Selecting Woman is itself the user's profile declaration; do not ask
    # them to repeat gender just to assess a women-focused scheme.
    if scheme["category"] == "Women":
        effective_answers.setdefault("gender", "female")
    for field, expected, label in rule.get("checks", []):
        value = effective_answers.get(field, "")
        if not value or value == "unknown":
            unknown.append(f"{label} has not been confirmed.")
        elif value in expected:
            satisfied.append(label)
        else:
            unmet.append(label)
    status = "unlikely" if unmet else "needs_more_information" if unknown else "likely"
    why = {
        "likely": "Your answers match the listed core conditions; final eligibility is decided by the scheme authority.",
        "needs_more_information": "Some eligibility details are missing or need confirmation from the official scheme authority.",
        "unlikely": "At least one answer conflicts with a listed core condition. Check the official rules for details.",
    }[status]
    return {**scheme, "assessment": {
        "status": status, "rationale": why,
        "eligibility_summary": scheme.get("eligibility", [])[:2],
        "benefit_summary": (scheme.get("benefits") or ["See the official source for benefit details."])[0],
        "satisfied_conditions": satisfied[:3], "unmet_conditions": unmet[:2],
        "unknown_conditions": unknown[:2],
    }}


def _valid_answer_values() -> dict[str, set[str]]:
    return {question["id"]: {option["value"] for option in question["options"]}
            for questions in ELIGIBILITY_QUESTIONS.values() for question in questions}


@app.post("/api/eligibility")
def eligibility(data: EligibilityInput):
    if any(len(key) > 100 or len(value) > 40 for key, value in data.answers.items()):
        raise HTTPException(422, "Eligibility answers are too long.")
    allowed_answers = _valid_answer_values()
    if any(key not in allowed_answers or value not in allowed_answers[key] for key, value in data.answers.items()):
        raise HTTPException(422, "Invalid eligibility answer.")

    if data.phase == "questions":
        questions = ELIGIBILITY_QUESTIONS.get(data.occupation, []) if data.step == 2 else []
        return {"step": data.step, "total_steps": 3, "questions": questions}

    schemes = _eligibility_schemes(data.occupation, data.answers)
    results = [_assess_scheme(scheme, data.answers) for scheme in schemes]
    groups = {
        "likely_matches": [scheme for scheme in results if scheme["assessment"]["status"] == "likely"],
        "needs_more_information": [scheme for scheme in results if scheme["assessment"]["status"] == "needs_more_information"],
        "unlikely_matches": [scheme for scheme in results if scheme["assessment"]["status"] == "unlikely"],
    }
    return {"step": 3, "total_steps": 3, "groups": groups, "counts": {key: len(items) for key, items in groups.items()},
        "message": "This is preliminary guidance, not an official eligibility decision. Verify every requirement with the scheme authority."}

def _language_disclaimer(language: str) -> str:
    return {
        "en": "I can only answer from the official scheme information shown below. If a detail is not listed, please verify it on the official source.",
        "te": "క్రింద చూపిన అధికారిక పథకం సమాచారాన్ని మాత్రమే ఆధారంగా సమాధానం ఇస్తాను. వివరాలు లేకపోతే అధికారిక మూలంలో నిర్ధారించండి.",
        "hi": "मैं नीचे दी गई आधिकारिक योजना जानकारी के आधार पर ही जवाब देता हूँ। कोई जानकारी उपलब्ध न हो तो आधिकारिक स्रोत पर जाँचें।",
    }[language]



_LANG_NAME: dict[str, str] = {"en": "English", "te": "Telugu", "hi": "Hindi"}


async def _call_gemini(
    question: str, context: str, intent: str, language: str, history: list
) -> str:
    """Call the Gemini API and return the answer, or '' on failure/no key."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return ""
    system = (
        f"You are YojanaMitra, a helpful AI assistant for Indian government welfare schemes. "
        f"Answer using ONLY the official scheme information in the Context section below. "
        f"Do not invent benefits, eligibility rules, deadlines, or URLs. "
        f"If a detail is not in the context, say so and direct the user to the official source. "
        f"Respond in {_LANG_NAME[language]}. Keep the answer under 150 words. "
        f"Preserve government scheme names and official amounts exactly as given.\n\n"
        f"Context:\n{context}"
    )
    contents = []
    for turn in history[-6:]:  # last 3 exchanges = 6 messages
        contents.append({"role": turn.role, "parts": [{"text": turn.text}]})
    contents.append({"role": "user", "parts": [{"text": question}]})
    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{model}:generateContent?key={key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 350},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return ""


async def _call_openai(
    question: str, context: str, intent: str, language: str, history: list
) -> str:
    """Call the OpenAI API and return the answer, or '' on failure/no key."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return ""
    messages = [{"role": "system", "content": (
        f"Answer the user's exact question in {_LANG_NAME[language]}. "
        f"Use only the retrieved relevant {intent} information below. "
        f"Do not summarize unrelated schemes or add facts. "
        f"If the requested detail is missing, say you cannot verify it from the retrieved source. "
        f"Do not infer eligibility or deadlines. Keep the answer under 100 words.\n\n{context}"
    )}]
    for turn in history[-6:]:
        messages.append({
            "role": turn.role if turn.role == "user" else "assistant",
            "content": turn.text,
        })
    messages.append({"role": "user", "content": question})
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "temperature": 0,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return ""

STOPWORDS = {
    "what", "who", "when", "where", "why", "how", "does", "do", "is", "are", "the", "a", "an", "for", "of", "to", "in", "on", "and", "or", "with", "about", "tell", "me", "please", "can", "could", "would", "i", "you", "my", "your", "provide", "available", "scheme", "schemes", "government", "भारत", "में", "क्या", "कौन", "और", "के", "की", "है", "हैं", "को", "लिए", "बताएं", "తెలుగు", "లో", "ఏమి", "ఎవరు", "మరియు", "గురించి", "చెప్పండి",
}

SCHEME_ALIASES = {
    "pm-kisan": ("pm-kisan", "pm kisan", "pmkisan", "pradhan mantri kisan samman nidhi", "పీఎం కిసాన్", "పిఎం కిసాన్", "पीएम किसान"),
    "nsp-scholarships": ("national scholarship portal", "nsp"),
    "pmfby": ("pmfby", "fasal bima", "crop insurance"),
    "kisan-credit-card": ("kcc", "kisan credit card"),
    "pmksy-per-drop-more-crop": ("pmksy", "per drop more crop", "micro irrigation"),
    "pm-usp-csss": ("pm-usp", "pm usp", "csss", "central sector scholarship for college"),
    "nmmss": ("nmmss", "nmms", "means-cum-merit scholarship"),
    "pm-yasasvi": ("pm-yasasvi", "pm yasasvi", "yasasvi"),
    "national-overseas-scholarship": ("national overseas scholarship", "overseas scholarship", "national overseas"),
    "pre-matric-sc-scholarship": ("pre-matric sc scholarship", "pre matric scholarship for scheduled castes"),
    "pmmvy": ("pmmvy", "matru vandana", "maternity benefit scheme"),
    "sukanya-samriddhi": ("sukanya samriddhi", "ssa"),
    "pm-ujjwala": ("pmuy", "ujjwala", "pradhan mantri ujjwala"),
    "day-nrlm": ("day-nrlm", "day nrlm", "national rural livelihoods mission", "nrlm"),
    "pm-mudra": ("pmmy", "mudra", "pradhan mantri mudra"),
    "pmegp": ("pmegp", "employment generation programme"),
    "pm-svanidhi": ("pm svanidhi", "pmsvanidhi", "svanidhi", "street vendor nidhi"),
    "pm-vishwakarma": ("pm vishwakarma", "pm-vishwakarma", "vishwakarma"),
    "pm-jay": ("pm-jay", "pm jay", "pmjay", "ayushman bharat", "jan arogya"),
    "pmay-urban-2": ("pmay-u", "pmay urban", "pmay-u 2.0", "awas yojana urban"),
    "atal-pension-yojana": ("atal pension", "atal pension yojana", "apy"),
}

LOCALIZED_ANSWERS = {
    "pm-kisan": {
        "te": {
            "overview": "PM-KISAN సాగుభూమి కలిగిన అర్హ రైతు కుటుంబాలకు ఆదాయ సహాయం అందించే పథకం.",
            "benefits": "అర్హత కలిగిన ప్రతి రైతు కుటుంబానికి సంవత్సరానికి ₹6,000 మూడు సమాన వాయిదాలుగా నేరుగా బ్యాంకు ఖాతాకు జమ అవుతుంది.",
            "eligibility": "సాగుభూమి కలిగిన రైతు కుటుంబాలు అర్హత పొందవచ్చు. సంస్థాగత భూస్వాములు మరియు కొన్ని అధిక ఆర్థిక స్థితి వర్గాలు మినహాయించబడ్డాయి. పూర్తి అర్హతను అధికారిక నియమాల్లో నిర్ధారించండి.",
            "application": "అధికారిక PM-KISAN పోర్టల్‌లో అర్హత, లబ్ధిదారుడి స్థితిని తనిఖీ చేసి, పోర్టల్ మరియు రాష్ట్ర ధృవీకరణ సూచనలను అనుసరించండి.",
            "deadline": "ప్రస్తుత దరఖాస్తు గడువు ఈ సమాచారంలో లేదు. తాజా తేదీల కోసం అధికారిక మూలాన్ని చూడండి.",
        },
        "hi": {
            "overview": "PM-KISAN खेती योग्य भूमि वाले पात्र किसान परिवारों को आय सहायता देने वाली योजना है।",
            "benefits": "हर पात्र किसान परिवार को सालाना ₹6,000 तीन बराबर किस्तों में सीधे बैंक खाते में मिलते हैं।",
            "eligibility": "खेती योग्य भूमि वाले किसान परिवार पात्र हो सकते हैं। संस्थागत भूमि धारक और कुछ उच्च आर्थिक स्थिति वाली श्रेणियाँ बाहर हैं। पूरी पात्रता आधिकारिक नियमों में जाँचें।",
            "application": "आधिकारिक PM-KISAN पोर्टल पर पात्रता और लाभार्थी की स्थिति जाँचें, फिर पोर्टल और राज्य की सत्यापन प्रक्रिया का पालन करें।",
            "deadline": "मौजूदा आवेदन की अंतिम तारीख यहाँ उपलब्ध नहीं है। नवीनतम तारीखों के लिए आधिकारिक स्रोत देखें।",
        },
    },
    "nsp-scholarships": {
        "te": {
            "overview": "నేషనల్ స్కాలర్‌షిప్ పోర్టల్‌లో కేంద్ర, రాష్ట్ర స్కాలర్‌షిప్‌లు ఉన్నాయి. అర్హత మరియు ప్రయోజనాలు ప్రతి పథకం, విద్యా సంవత్సరం ఆధారంగా మారుతాయి. ప్రస్తుత వివరాల కోసం అధికారిక పథకాల జాబితా, అర్హత తనిఖీ సాధనాన్ని చూడండి.",
            "benefits": "స్కాలర్‌షిప్ ప్రయోజనాలు, మొత్తాలు పథకం ఆధారంగా మారుతాయి. నిర్దిష్ట పథకం మొత్తాన్ని అధికారిక వివరాల్లో చూడండి.",
            "eligibility": "అర్హత ప్రతి స్కాలర్‌షిప్, విద్యా సంవత్సరం, నివాసం, కోర్సు మరియు ఇతర నియమాలపై ఆధారపడి ఉంటుంది. అధికారిక అర్హత తనిఖీ సాధనాన్ని ఉపయోగించండి.",
            "application": "అధికారిక పోర్టల్‌లో అర్హత తనిఖీ చేసి, ప్రస్తుత స్కాలర్‌షిప్ మార్గదర్శకాలను అనుసరించండి.",
            "deadline": "దరఖాస్తు చివరి తేదీలు పథకం, విద్యా సంవత్సరం ఆధారంగా మారుతాయి. ప్రస్తుత తేదీని అధికారిక పోర్టల్‌లో చూడండి.",
        },
        "hi": {
            "overview": "राष्ट्रीय छात्रवृत्ति पोर्टल पर केंद्र और राज्य की छात्रवृत्तियाँ उपलब्ध हैं। पात्रता और लाभ हर योजना तथा शैक्षणिक वर्ष के अनुसार अलग होते हैं। मौजूदा जानकारी के लिए आधिकारिक योजना सूची और पात्रता जाँच देखें।",
            "benefits": "छात्रवृत्ति के लाभ और राशि योजना के अनुसार अलग होते हैं। किसी खास योजना की राशि उसके आधिकारिक विवरण में देखें।",
            "eligibility": "पात्रता छात्रवृत्ति, शैक्षणिक वर्ष, निवास, पाठ्यक्रम और अन्य नियमों के अनुसार अलग होती है। आधिकारिक पात्रता जाँच का उपयोग करें।",
            "application": "आधिकारिक पोर्टल पर पात्रता जाँचें और मौजूदा छात्रवृत्ति के दिशानिर्देशों का पालन करें।",
            "deadline": "आवेदन की अंतिम तारीख योजना और शैक्षणिक वर्ष के अनुसार अलग होती है। मौजूदा तारीख आधिकारिक पोर्टल पर देखें।",
        },
    },
}


def _compact(text: str) -> str:
    return re.sub(r"[^\w]+", "", text.casefold(), flags=re.UNICODE)


def _tokens(text: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE):
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("s") and not token.endswith("ss") and len(token) > 3:
            token = token[:-1]
        if token not in STOPWORDS and len(token) > 1:
            tokens.add(token)
    return tokens


def _mentioned_schemes(question: str) -> list[dict]:
    normalized = _compact(question)
    matched_ids = {
        scheme_id for scheme_id, aliases in SCHEME_ALIASES.items()
        if any(_compact(alias) in normalized for alias in (*aliases, next((s["name"] for s in SCHEMES if s["id"] == scheme_id), "")))
    }
    if len(matched_ids) < 2 and re.search(r"\b(compare|versus|vs)\b", question.casefold()):
        query_terms = _tokens(question)
        if "student" in query_terms or "scholarship" in query_terms:
            matched_ids.update(s["id"] for s in SCHEMES if s["category"] == "Students")
        if "farmer" in query_terms:
            matched_ids.update(s["id"] for s in SCHEMES if s["category"] == "Farmers")
    return [scheme for scheme in SCHEMES if scheme["id"] in matched_ids]


def _question_intent(question: str) -> str:
    text = question.casefold()
    if re.search(r"\b(deadline|last date|closing date|due date|application date)\b|अंतिम तिथि|చివరి తేదీ", text):
        return "deadline"
    if re.search(r"\b(benefit|benefits|amount|provide|gives?)\b|लाभ|फायदा|ప్రయోజన|లభిస్త", text):
        return "benefits"
    if re.search(r"\b(eligib|eligible|qualif|who can apply)\w*\b|पात्र|योग्य|అర్హత|అర్హులు", text):
        return "eligibility"
    if re.search(r"\b(apply|application|process|how to get)\w*\b|आवेदन|आवेदन|దరఖాస్తు", text):
        return "application"
    return "overview"


def _retrieve_schemes(question: str) -> list[dict]:
    named = _mentioned_schemes(question)
    if named:
        return named[:3]

    query_terms = _tokens(question) - {
        "benefit", "benefits", "amount", "provide", "provides", "eligible", "eligibility", "qualify", "qualified",
        "apply", "application", "process", "support", "available", "information", "details",
    }
    if not query_terms:
        return SCHEMES[:3]
    ranked = []
    for scheme in SCHEMES:
        fields = " ".join([
            scheme["name"], scheme["category"], scheme["description"], scheme["beneficiaries"],
            *scheme["eligibility"], *scheme["benefits"], *scheme["application"],
        ])
        overlap = query_terms & _tokens(fields)
        if overlap:
            ranked.append((len(overlap), scheme))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [scheme for _, scheme in ranked[:8]]


def _scheme_evidence(scheme: dict, intent: str, language: str) -> str:
    localized = LOCALIZED_ANSWERS.get(scheme["id"], {}).get(language, {}).get(intent)
    if localized:
        return localized
    if intent == "benefits":
        return " ".join(scheme["benefits"]) or "Benefit details are not available in the retrieved scheme record."
    if intent == "eligibility":
        return " ".join([scheme["beneficiaries"], *scheme["eligibility"]])
    if intent == "application":
        return " ".join(scheme["application"]) or "Application instructions are not available in the retrieved scheme record."
    if intent == "deadline":
        return "Deadline information is not available in the retrieved scheme record. Check the official source for current dates."
    return " ".join([scheme["description"], scheme["beneficiaries"]])


@app.post("/api/assistant")
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
    scheme_context = "\n\n".join(
        f"Scheme: {s['name']}\nCategory: {s['category']}\n"
        f"Relevant {intent} information: {_scheme_evidence(s, intent, 'en')}\n"
        f"Official source: {s['official_url']}"
        for s in relevant
    )
    context = scheme_context
    if rag_context:
        context = f"{scheme_context}\n\n--- Additional retrieved context ---\n{rag_context}"

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
            answer = "\n".join(f"{scheme['name']}: {fact}" for scheme, fact in zip(relevant, evidence))

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
    }


@app.get("/api/rag/status")
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


@app.post("/api/tts")
@_limiter.limit("3/minute")
async def text_to_speech(request: Request, body: dict):
    """
    Convert text to speech audio (MP3).
    Body: {"text": str (max 500 chars), "language": "en"|"te"|"hi"}
    Returns audio/mpeg bytes or 503 if TTS unavailable.
    """
    raw_text = str(body.get("text", "")).strip()
    language = str(body.get("language", "en"))
    if not raw_text:
        raise HTTPException(422, "text is required")
    if len(raw_text) > 500:
        raise HTTPException(422, "text must be 500 characters or fewer")
    text = raw_text
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


@app.post("/api/documents/summarize")
@_limiter.limit("10/minute")
async def summarize_document(request: Request, file: UploadFile = File(...)):
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Please upload a PDF file.")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "This PDF is over the 10 MB limit. Choose a smaller file.")
    if not content.startswith(b"%PDF"):
        raise HTTPException(400, "This file does not appear to be a valid PDF. Please choose another file.")
    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception:
        raise HTTPException(400, "We could not read this PDF. Try a valid, unprotected PDF.")
    if len(text) < 80:
        raise HTTPException(422, "This PDF has no readable text. Scanned PDFs need OCR, which is not available yet.")
    # Build structured summary from paragraphs
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n{2,}", text) if p.strip() and len(p.strip()) > 40]
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
        summary_parts.append("Overview:\n" + " ".join(overview_paras[:3])[:600])
    for key, label in [("eligibility","Eligibility"),("benefits","Benefits"),("documents","Documents Required"),("how_to_apply","How to Apply")]:
        if key in sections:
            summary_parts.append(f"\n{label}:\n" + " ".join(sections[key][:2])[:400])

    summary = "\n".join(summary_parts)[:2000] if summary_parts else (" ".join(paragraphs[:5])[:1800])

    return {
        "filename": (file.filename or "document.pdf")[:120],
        "summary": summary,
        "pages": len(reader.pages),
        "note": "Summary is based only on text extracted from this file. The uploaded file is processed in memory and is not stored.",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Authentication endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/register", status_code=201)
def register(data: _RegisterRequest):
    """Register a new user. Returns 409 if email already taken."""
    if len(data.name.strip()) < 2:
        raise HTTPException(422, "Name must be at least 2 characters.")
    if _get_user_by_email(data.email):
        raise HTTPException(409, "An account with this email already exists. Please sign in.")
    user = _create_user(data.name.strip(), data.email, data.password)
    token = _create_access_token(user["id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
    }


@app.post("/api/auth/login")
def login(data: _LoginRequest):
    """Authenticate user. Returns JWT access token."""
    row = _get_user_by_email(data.email)
    if not row or not _verify_password(data.password, row["hashed_pw"]):
        raise HTTPException(401, "Incorrect email or password.")
    token = _create_access_token(row["id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": row["id"], "name": row["name"], "email": row["email"]},
    }


@app.get("/api/auth/me")
def me(user=Depends(_get_current_user)):
    """Return current authenticated user info."""
    return {"id": user["id"], "name": user["name"], "email": user["email"]}


# ── Saved schemes ─────────────────────────────────────────────────────────────

@app.get("/api/user/saved-schemes")
def list_saved_schemes(user=Depends(_get_current_user)):
    """Return list of scheme IDs saved by the authenticated user."""
    return {"saved": _get_saved_schemes(user["id"])}


@app.post("/api/user/saved-schemes/{scheme_id}", status_code=201)
def add_saved_scheme(scheme_id: str, user=Depends(_get_current_user)):
    """Save a scheme for the authenticated user."""
    if not any(s["id"] == scheme_id for s in SCHEMES):
        raise HTTPException(404, "Scheme not found.")
    _save_scheme(user["id"], scheme_id)
    return {"saved": _get_saved_schemes(user["id"])}


@app.delete("/api/user/saved-schemes/{scheme_id}")
def remove_saved_scheme(scheme_id: str, user=Depends(_get_current_user)):
    """Remove a saved scheme for the authenticated user."""
    _unsave_scheme(user["id"], scheme_id)
    return {"saved": _get_saved_schemes(user["id"])}


# ── Conversation history ──────────────────────────────────────────────────────

@app.get("/api/user/history")
def get_history(user=Depends(_get_current_user)):
    """Return the last 20 conversation turns for the authenticated user."""
    return {"history": _get_conv_history(user["id"], limit=20)}


@app.delete("/api/user/history")
def clear_history(user=Depends(_get_current_user)):
    """Clear conversation history for the authenticated user."""
    _clear_conv_history(user["id"])
    return {"cleared": True}

