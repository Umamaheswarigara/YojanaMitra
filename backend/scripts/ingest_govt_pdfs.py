"""
ingest_govt_pdfs.py  (v2)
-------------------------
Reads PDFs from data/govt_pdfs/, extracts text with pypdf,
and ingests into the RAG vector store via rag.add_pdf_chunks().

Run from backend/ directory.
"""
import sys
from pathlib import Path

sys.path.insert(0, ".")
from app import rag

out_dir = Path("data/govt_pdfs")
manifest = out_dir / "manifest.txt"

if not manifest.exists():
    print("ERROR: manifest.txt not found. Run generate_scheme_pdfs.py first.")
    sys.exit(1)

# Read manifest  format: filename|source_url|portal_url|source_name
entries = []
for line in manifest.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    parts = line.split("|")
    if len(parts) >= 4:
        entries.append({
            "filename": parts[0],
            "source_url": parts[2],   # portal URL (e.g. https://www.india.gov.in)
            "source_name": parts[3],
        })

print(f"Found {len(entries)} entries in manifest.\n")

try:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadWarning
    import warnings
    warnings.filterwarnings("ignore", category=PdfReadWarning)
except ImportError:
    print("ERROR: pypdf not installed.")
    sys.exit(1)

if not rag.rag_available():
    print("ERROR: RAG is not available (sentence-transformers not loaded).")
    sys.exit(1)

total_chunks = 0

for entry in entries:
    pdf_path = out_dir / entry["filename"]
    if not pdf_path.exists():
        print(f"  SKIP (not found): {entry['filename']}")
        continue

    print(f"Processing: {entry['filename']}")

    try:
        reader = PdfReader(str(pdf_path), strict=False)
        num_pages = len(reader.pages)
        print(f"  Pages: {num_pages}")

        pages_text = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            pages_text.append(text)
            print(f"    Page {page_num}: {len(text)} chars extracted")

        # Use the existing add_pdf_chunks API
        chunks_added = rag.add_pdf_chunks(
            filename=entry["filename"],
            official_url=entry["source_url"],
            pages_text=pages_text,
            doc_type="pdf",
        )

        total_chunks += chunks_added
        print(f"  → Added {chunks_added} chunks\n")

    except Exception as e:
        print(f"  ERROR processing {entry['filename']}: {e}\n")

print(f"{'='*60}")
print(f"Ingestion complete. Total chunks added: {total_chunks}")

# Status via public API
size = rag.collection_size()
print(f"RAG collection size (total chunks): {size}")
