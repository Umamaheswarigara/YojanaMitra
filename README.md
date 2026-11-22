# YojanaMitra

**AI-Powered Multilingual Government Scheme Assistant**

YojanaMitra helps people in India discover government schemes, check preliminary eligibility, ask questions in English, Telugu, or Hindi, and understand scheme PDFs â€” all in one place.

---

## Features

| Feature | Description |
|---|---|
| ðŸ” **Scheme Discovery** | Search and filter 23 verified government schemes by name, keyword, or category |
| âœ… **Eligibility Checker** | 3-step guided assessment for Farmers, Students, Women, Small Business Owners, and General Public |
| ðŸ¤– **AI Assistant** | Multi-turn conversation using Gemini 1.5 Flash with RAG-grounded answers and source citations |
| ðŸ“„ **Document Explainer** | Upload a scheme PDF â€” get a plain-language summary and auto-index into semantic search |
| ðŸŒ **Multilingual** | English, Telugu (à°¤à±†à°²à±à°—à±), and Hindi (à¤¹à¤¿à¤¨à¥à¤¦à¥€) UI and AI responses |
| ðŸ—‚ï¸ **RAG Pipeline** | SQLite + sentence-transformers vector search over 224+ scheme chunks |
| ðŸ”’ **Privacy-first** | No user data stored; PDFs processed in memory only; API keys backend-only |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 8, plain CSS (no external UI library) |
| Backend | Python 3.12+, FastAPI, Uvicorn |
| AI | Google Gemini 1.5 Flash (free tier) |
| Embeddings | `sentence-transformers paraphrase-multilingual-MiniLM-L12-v2` (50 languages, local) |
| Vector Store | SQLite + NumPy cosine similarity (no external service) |
| PDF processing | pypdf |
| Rate limiting | slowapi |

---

## Scheme Catalogue

23 verified government schemes across 5 categories, last verified **21 November 2026**:

| Category | Schemes |
|---|---|
| ðŸŒ¾ Farmers (4) | PM-KISAN, PMFBY, Kisan Credit Card, PMKSY Micro Irrigation |
| ðŸŽ“ Students (8) | NSP, CSSS, NMMSS, PM-YASASVI, NOS, Pre-Matric SC, AICTE Pragati Ã—2 |
| ðŸ‘© Women (4) | PMMVY, Sukanya Samriddhi, PM Ujjwala, DAY-NRLM |
| ðŸª Small Business (4) | PM MUDRA, PMEGP, PM SVANidhi, PM Vishwakarma |
| ðŸ¥ General Public (3) | Ayushman Bharat PM-JAY, PMAY Urban 2.0, Atal Pension Yojana |

---

## Quick Start (Windows PowerShell)

### Prerequisites
- Python 3.12+ (the project uses 3.15.2 â€” Python 3.12+ also works)
- Node.js 20+

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs at **http://localhost:8000**. API docs at **http://localhost:8000/docs**.

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173**.

### 3. Seed the RAG database (first run only)

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/seed_rag.py
.\.venv\Scripts\python.exe scripts/generate_scheme_pdfs_v2.py
.\.venv\Scripts\python.exe scripts/ingest_govt_pdfs.py
```

This creates 224 vector chunks for semantic search.

---

## Configuration

Copy `.env.example` to `.env` in the `backend/` directory:

```powershell
copy backend\.env.example backend\.env
```

Edit `backend/.env`:

```env
# Google Gemini (free tier â€” 15 req/min, 1500/day)
# Get your key: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash

# OpenAI (optional fallback â€” leave blank if not using)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# CORS origins (comma-separated) â€” add your production URL here
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

> **Security:** Never commit `backend/.env`. It is listed in `.gitignore`. Never put API keys in `frontend/` or any client-side code.

### AI Fallback Chain

1. **Gemini** (if `GEMINI_API_KEY` is set) â€” conversational, multilingual, grounded answers
2. **OpenAI** (if `OPENAI_API_KEY` is set and Gemini fails) â€” alternative LLM
3. **Deterministic retrieval** (always works, no API key) â€” keyword-matched scheme data with official citations

The app works fully without any API key using the deterministic fallback.

---

## Get a Gemini API Key (Free)

1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click **Create API key**
4. Copy the key and paste it into `backend/.env` as `GEMINI_API_KEY=your_key_here`

> **Free tier limits:** 15 requests/minute, 1,500 requests/day â€” sufficient for development and personal use.

---

## Docker Deployment

```powershell
# Build and start both services
docker compose up --build

# Frontend: http://localhost
# Backend API: http://localhost:8000
# API docs: http://localhost:8000/docs
```

Create a `backend/.env` file before running Docker (the compose file uses `env_file`).

---

## Running Tests

```powershell
# Backend tests (56+ tests)
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Frontend tests (4 tests)
cd frontend
node --test src/eligibilityState.test.js

# Production build
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd frontend
npx vite build
```

---

## RAG Pipeline

The Retrieval-Augmented Generation (RAG) system enables semantic search over scheme data:

| Component | Implementation |
|---|---|
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` (50 languages, runs locally) |
| Vector store | SQLite + NumPy (no external service required) |
| Similarity | Cosine similarity with 0.30 threshold |
| Index size | 224 chunks (129 scheme + 56 PDF + extras) |
| Languages | English, Telugu, Hindi natively supported |

> ChromaDB and FAISS are not used because they require `onnxruntime` which has no Python 3.15 wheel. The SQLite + NumPy implementation provides equivalent functionality.

### Re-seed after scheme changes

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/seed_rag.py
```

### Ingest a new PDF via API

```powershell
curl -X POST http://localhost:8000/api/rag/ingest \
  -F "file=@your_document.pdf" \
  -F "source_url=https://official-portal.gov.in"
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check with RAG status |
| GET | `/api/schemes` | List/search schemes (params: `q`, `category`) |
| GET | `/api/schemes/{id}` | Get scheme by ID |
| POST | `/api/eligibility` | Eligibility assessment |
| POST | `/api/assistant` | AI assistant with RAG (supports conversation history) |
| POST | `/api/documents/summarize` | PDF text extraction and summarization |
| GET | `/api/rag/status` | RAG vector store status |
| POST | `/api/rag/ingest` | Upload PDF for RAG indexing |
| POST | `/api/tts` | Text-to-speech (English, Telugu, Hindi) |
| POST | `/api/auth/register` | Register new user (returns JWT) |
| POST | `/api/auth/login` | Sign in (returns JWT) |
| GET | `/api/auth/me` | Get current user (requires Bearer token) |
| GET | `/api/user/saved-schemes` | List saved scheme IDs (auth required) |
| POST | `/api/user/saved-schemes/{id}` | Save a scheme (auth required) |
| DELETE | `/api/user/saved-schemes/{id}` | Unsave a scheme (auth required) |
| GET | `/api/user/history` | Get conversation history (auth required) |
| DELETE | `/api/user/history` | Clear conversation history (auth required) |

Full interactive docs: **http://localhost:8000/docs**

---

## Project Structure

```
YojanaMitra/
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ app/
â”‚   â”‚   â”œâ”€â”€ main.py          # All FastAPI routes (~700 lines)
â”‚   â”‚   â””â”€â”€ rag.py           # SQLite vector store + RAG pipeline
â”‚   â”œâ”€â”€ data/
â”‚   â”‚   â”œâ”€â”€ schemes.json     # 23 verified schemes
â”‚   â”‚   â””â”€â”€ govt_pdfs/       # Reference PDFs (gitignored: vector_store.db)
â”‚   â”œâ”€â”€ scripts/
â”‚   â”‚   â”œâ”€â”€ seed_rag.py      # Seed all schemes into vector store
â”‚   â”‚   â”œâ”€â”€ generate_scheme_pdfs_v2.py  # Generate reference PDFs
â”‚   â”‚   â””â”€â”€ ingest_govt_pdfs.py         # Ingest PDFs into RAG
â”‚   â”œâ”€â”€ tests/
â”‚   â”‚   â”œâ”€â”€ test_main.py     # 30+ integration tests
â”‚   â”‚   â””â”€â”€ test_rag.py      # 26 RAG-specific tests
â”‚   â”œâ”€â”€ requirements.txt
â”‚   â”œâ”€â”€ .env.example
â”‚   â””â”€â”€ Dockerfile
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ src/
â”‚   â”‚   â”œâ”€â”€ main.jsx         # App shell, router, language selector
â”‚   â”‚   â”œâ”€â”€ pages.jsx        # All page components
â”‚   â”‚   â”œâ”€â”€ components.jsx   # SchemeCard, SchemeDetails, etc.
â”‚   â”‚   â”œâ”€â”€ translations.js  # EN/TE/HI copy + scheme translations
â”‚   â”‚   â”œâ”€â”€ api.js           # Fetch wrappers
â”‚   â”‚   â”œâ”€â”€ styles.css       # Full responsive CSS
â”‚   â”‚   â””â”€â”€ eligibilityState.js  # Pure reducer
â”‚   â”œâ”€â”€ Dockerfile
â”‚   â””â”€â”€ nginx.conf
â”œâ”€â”€ docker-compose.yml
â””â”€â”€ README.md
```

---

## Disclaimer

Scheme information is verified against official Indian government portals as of **21 November 2026**. Eligibility results are **preliminary guidance only** â€” not an official government determination. Rules change; always verify current terms at the official portal before applying. YojanaMitra does not store submitted profile data or uploaded PDFs.

Official reference portals:
- [myScheme.gov.in](https://www.myscheme.gov.in/) â€” official scheme discovery portal
- [india.gov.in](https://www.india.gov.in/) â€” National Portal of India

---

## License

This project is for educational and informational purposes. Scheme data is sourced from public Indian government portals.



## Authentication

YojanaMitra includes a built-in user account system (Sign Up / Sign In / Sign Out).

### How it works
- Accounts are stored in ackend/data/users.db (SQLite, gitignored)
- Passwords are hashed with **bcrypt** — never stored in plain text
- Sessions use **JWT Bearer tokens** (HS256, 60-minute expiry by default)
- Tokens are stored in localStorage on the client only — never sent to AI APIs or logged

### Setup
Add these to your ackend/.env:

```env
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
AUTH_SECRET_KEY=your_random_32_byte_hex_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### Features (when signed in)
- **Saved Schemes** — bookmark schemes for quick access
- **Conversation History** — your AI Assistant chat is persisted across sessions
- **Sign Out** — clears token from localStorage immediately

### Guest mode
All existing features (scheme search, eligibility checker, AI assistant, PDF analyzer) work without an account. Authentication is optional and additive.

