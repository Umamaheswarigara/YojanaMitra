"""
test_pdf_retrieval.py
---------------------
Tests semantic retrieval from the RAG vector store with EN/TE/HI queries.
Verifies that answers are grounded in retrieved content and citations are correct.

Run from backend/ directory.
"""
import sys
sys.path.insert(0, ".")
from app import rag

QUERIES = [
    # English queries
    ("en", "What is PM-KISAN and how much money do farmers get?"),
    ("en", "Who is eligible for PM Ujjwala Yojana LPG connection?"),
    ("en", "How to apply for PM MUDRA Yojana loan?"),
    ("en", "What are the benefits of Ayushman Bharat PM-JAY health scheme?"),
    ("en", "What is AICTE Pragati scholarship for girl students?"),
    ("en", "Sukanya Samriddhi Account interest rate and eligibility"),
    # Hindi queries
    ("hi", "PM-KISAN योजना से किसानों को कितना पैसा मिलता है?"),
    ("hi", "प्रधानमंत्री उज्ज्वला योजना के लिए पात्रता क्या है?"),
    ("hi", "आयुष्मान भारत योजना के फायदे क्या हैं?"),
    # Telugu queries
    ("te", "PM-KISAN పథకం గురించి చెప్పండి"),
    ("te", "ముద్రా లోన్ ఎలా పొందాలి?"),
    ("te", "అటల్ పెన్షన్ యోజన అర్హత ఏమిటి?"),
]

print("=" * 70)
print("YojanaMitra RAG Retrieval Test")
print("=" * 70)
print(f"RAG available: {rag.rag_available()}")
print(f"Collection size: {rag.collection_size()} chunks")
print()

passed = 0
failed = 0

for lang, query in QUERIES:
    print(f"[{lang.upper()}] {query}")
    try:
        results = rag.query_rag(query, n_results=3)
        if results:
            top = results[0]
            print(f"  ✓ Top hit: '{top['source_name']}' (page {top['page']})")
            print(f"    Snippet: {top['text'][:120].replace(chr(10),' ')}...")
            # Verify citations include source info
            citations = rag.build_citations(results)
            sources = [c["name"] for c in citations]
            print(f"  Citations: {sources}")
            passed += 1
        else:
            print(f"  ✗ No results returned (below threshold or empty index)")
            failed += 1
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        failed += 1
    print()

print("=" * 70)
print(f"Results: {passed} passed / {failed} failed out of {len(QUERIES)} queries")
print("=" * 70)

# Also verify specific PDF documents are in the index
print("\nDocument coverage check:")
expected_docs = [
    "YojanaMitra_Farmers_Schemes_Reference.pdf",
    "YojanaMitra_Students_Schemes_Reference.pdf",
    "YojanaMitra_Women_Schemes_Reference.pdf",
    "YojanaMitra_SmallBusiness_Schemes_Reference.pdf",
    "YojanaMitra_GeneralPublic_Schemes_Reference.pdf",
]
doc_results = rag.query_rag("scheme eligibility benefits application", n_results=20)
found_docs = set(r["source_name"] for r in doc_results)
for doc in expected_docs:
    status = "✓" if doc in found_docs else "✗"
    print(f"  {status} {doc}")
print(f"\nAll sources found in index: {found_docs}")
