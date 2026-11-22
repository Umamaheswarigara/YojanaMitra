"""
seed_rag.py — Seed the YojanaMitra RAG vector store from the verified scheme catalogue.

Usage (from the backend directory):
    .\.venv\Scripts\python.exe scripts/seed_rag.py

Each of the 23 schemes is converted into multiple text chunks (overview, benefits,
eligibility, application process) and stored with its official URL as the citation source.
This guarantees all retrieval is grounded in verified government information.
"""

import json
import sys
from pathlib import Path

# Allow importing from backend/app
_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app.rag import add_scheme_chunks, collection_size, rag_available


def seed_from_schemes(schemes_path: Path) -> None:
    if not rag_available():
        print("RAG is not available (sentence-transformers not installed). Skipping seed.")
        return

    with schemes_path.open(encoding="utf-8") as f:
        schemes = json.load(f)

    total_chunks = 0
    for scheme in schemes:
        sections: dict[str, str] = {
            "Scheme name": scheme["name"],
            "Category": scheme["category"],
            "Overview": scheme.get("description", ""),
            "Who it helps": scheme.get("beneficiaries", ""),
            "Eligibility": " ".join(scheme.get("eligibility", [])),
            "Benefits": " ".join(scheme.get("benefits", [])),
            "How to apply": " ".join(scheme.get("application", [])),
        }
        # Remove empty sections
        sections = {k: v for k, v in sections.items() if v.strip()}

        added = add_scheme_chunks(
            scheme_id=scheme["id"],
            scheme_name=scheme["name"],
            official_url=scheme.get("official_url", ""),
            text_sections=sections,
        )
        print(f"  ✓ {scheme['name'][:55]:<55} → {added} chunks")
        total_chunks += added

    print(f"\nSeeding complete. Total chunks in store: {collection_size()}")
    print(f"Chunks added/updated this run: {total_chunks}")


if __name__ == "__main__":
    schemes_file = _BACKEND / "data" / "schemes.json"
    if not schemes_file.exists():
        print(f"ERROR: schemes.json not found at {schemes_file}")
        sys.exit(1)
    print(f"Seeding RAG vector store from {schemes_file} …\n")
    seed_from_schemes(schemes_file)
