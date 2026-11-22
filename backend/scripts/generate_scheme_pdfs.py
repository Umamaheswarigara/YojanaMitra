"""
generate_scheme_pdfs.py
-----------------------
Generates authoritative scheme reference PDFs from the verified 23-scheme JSON
catalogue. Each PDF covers one category of schemes.

These PDFs are clearly labelled:
  "YojanaMitra Scheme Reference — compiled from official government sources"

They are NOT claimed to be original ministry documents. All scheme information
was verified against official portals (last_verified dates in the JSON).

Run from the backend/ directory.
"""
import json
import textwrap
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Try to use reportlab (clean text PDF), fall back to fpdf2, then pypdf text
# We use a simple approach: write a plain-text PDF using pypdf's low-level API
# ---------------------------------------------------------------------------

out_dir = Path("data/govt_pdfs")
out_dir.mkdir(parents=True, exist_ok=True)

data_path = Path("data/schemes.json")
with open(data_path, encoding="utf-8") as f:
    all_schemes = json.load(f)

# Group by category
from collections import defaultdict
by_category = defaultdict(list)
for s in all_schemes:
    by_category[s["category"]].append(s)

GENERATED_AT = datetime.now().strftime("%d %B %Y")

# ---------------------------------------------------------------------------
# PDF generation using pypdf PdfWriter with page-level text via annotation
# Actually, pypdf cannot embed arbitrary text easily. We use a pure-Python
# approach: write a minimal PDF manually (text streams).
# ---------------------------------------------------------------------------

def wrap_text(text, width=90):
    """Wrap text to given character width."""
    lines = []
    for paragraph in str(text).split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue
        wrapped = textwrap.wrap(paragraph, width=width)
        lines.extend(wrapped if wrapped else [""])
    return lines


def make_pdf_bytes(title: str, category: str, schemes: list) -> bytes:
    """
    Build a minimal valid PDF with embedded text using PDF content streams.
    Uses a basic monospace font (Courier) which is a standard PDF font.
    """
    # Collect all text lines
    page_texts = []
    current_page_lines = []
    LINE_HEIGHT = 14  # points
    PAGE_HEIGHT = 792  # US Letter
    PAGE_WIDTH = 612
    MARGIN_TOP = 740
    MARGIN_BOTTOM = 50
    MARGIN_LEFT = 50
    FONT_SIZE = 10
    HEADER_FONT_SIZE = 13
    MAX_LINES = int((MARGIN_TOP - MARGIN_BOTTOM) / LINE_HEIGHT)

    def flush_page():
        if current_page_lines:
            page_texts.append(list(current_page_lines))
            current_page_lines.clear()

    def add_line(text="", bold=False, size=None):
        current_page_lines.append((text, bold, size or FONT_SIZE))
        if len(current_page_lines) >= MAX_LINES:
            flush_page()
            # Add continuation header
            current_page_lines.append((f"[{title} — continued]", False, 8))
            current_page_lines.append(("", False, FONT_SIZE))

    # Header lines
    add_line("YojanaMitra Scheme Reference Document", bold=True, size=HEADER_FONT_SIZE)
    add_line(f"Category: {category}", bold=True, size=HEADER_FONT_SIZE)
    add_line(f"Compiled from official Indian government sources | Generated: {GENERATED_AT}", size=8)
    add_line(
        "NOTICE: This document is a reference compilation by YojanaMitra. "
        "It is NOT an official government publication.",
        size=8,
    )
    add_line("For authoritative information visit the official portal URLs listed for each scheme.", size=8)
    add_line()
    add_line("=" * 88, size=8)
    add_line()

    for idx, scheme in enumerate(schemes, 1):
        name = scheme.get("name", "Unknown Scheme")
        sid = scheme.get("id", "")
        official_url = scheme.get("official_url", "N/A")
        last_verified = scheme.get("last_verified", "N/A")
        source_note = scheme.get("source_note", "")
        description = scheme.get("description", "")
        beneficiaries = scheme.get("beneficiaries", "")
        eligibility = scheme.get("eligibility", {})
        benefits = scheme.get("benefits", [])
        application = scheme.get("application", {})

        add_line(f"{idx}. {name}", bold=True, size=11)
        add_line(f"   Scheme ID: {sid}  |  Official Portal: {official_url}", size=8)
        add_line(f"   Last Verified: {last_verified}  |  Source: {source_note}", size=8)
        add_line()

        # Description
        add_line("   DESCRIPTION:", bold=True, size=9)
        for line in wrap_text(description, 85):
            add_line(f"   {line}", size=9)
        add_line()

        # Beneficiaries
        if beneficiaries:
            add_line("   BENEFICIARIES:", bold=True, size=9)
            for line in wrap_text(beneficiaries, 85):
                add_line(f"   {line}", size=9)
            add_line()

        # Eligibility
        if eligibility:
            add_line("   ELIGIBILITY:", bold=True, size=9)
            if isinstance(eligibility, dict):
                for key, val in eligibility.items():
                    if isinstance(val, list):
                        add_line(f"   {key.upper()}:", size=9)
                        for item in val:
                            for line in wrap_text(f"     - {item}", 83):
                                add_line(line, size=9)
                    elif val:
                        for line in wrap_text(f"   {key}: {val}", 85):
                            add_line(line, size=9)
            else:
                for line in wrap_text(str(eligibility), 85):
                    add_line(f"   {line}", size=9)
            add_line()

        # Benefits
        if benefits:
            add_line("   BENEFITS:", bold=True, size=9)
            if isinstance(benefits, list):
                for b in benefits:
                    for line in wrap_text(f"   - {b}", 85):
                        add_line(line, size=9)
            else:
                for line in wrap_text(str(benefits), 85):
                    add_line(f"   {line}", size=9)
            add_line()

        # Application
        if application:
            add_line("   HOW TO APPLY:", bold=True, size=9)
            if isinstance(application, dict):
                for key, val in application.items():
                    if isinstance(val, list):
                        add_line(f"   {key.upper()}:", size=9)
                        for item in val:
                            for line in wrap_text(f"     - {item}", 83):
                                add_line(line, size=9)
                    elif val:
                        for line in wrap_text(f"   {key}: {val}", 85):
                            add_line(line, size=9)
            else:
                for line in wrap_text(str(application), 85):
                    add_line(f"   {line}", size=9)
            add_line()

        add_line("-" * 88, size=8)
        add_line()

    flush_page()

    # -----------------------------------------------------------------------
    # Build raw PDF bytes
    # -----------------------------------------------------------------------
    objects = []  # list of (obj_id, dict_str, stream_bytes_or_None)
    xref_positions = []

    def new_obj(dictionary: str, stream: bytes = None):
        oid = len(objects) + 1
        objects.append((oid, dictionary, stream))
        return oid

    # Object 1: Catalog (placeholder, filled after page tree)
    # Object 2: Page tree (placeholder)
    # We'll assign these after we know page count

    num_pages = len(page_texts)
    page_obj_ids = []

    # Pre-allocate object IDs
    # 1 = catalog, 2 = page_tree, 3..N = pages, N+1..M = content streams
    catalog_id = 1
    page_tree_id = 2
    first_page_id = 3
    first_content_id = first_page_id + num_pages

    def escape_pdf_string(text: str) -> str:
        """Escape special characters for PDF string literals."""
        # Only keep ASCII printable; replace others with space
        result = []
        for ch in text:
            if ch == '\\':
                result.append('\\\\')
            elif ch == '(':
                result.append('\\(')
            elif ch == ')':
                result.append('\\)')
            elif ch == '\r':
                result.append('\\r')
            elif ord(ch) < 32 or ord(ch) > 126:
                result.append(' ')
            else:
                result.append(ch)
        return ''.join(result)

    def build_content_stream(lines):
        """Build PDF content stream for one page."""
        parts = ["BT"]
        y = MARGIN_TOP
        parts.append(f"/F1 {FONT_SIZE} Tf")
        parts.append(f"{MARGIN_LEFT} {y} Td")
        parts.append(f"{LINE_HEIGHT} TL")  # text leading

        for text, bold, size in lines:
            safe = escape_pdf_string(text)
            if size != FONT_SIZE:
                parts.append(f"/F1 {size} Tf")
            parts.append(f"({safe}) Tj T*")
            if size != FONT_SIZE:
                parts.append(f"/F1 {FONT_SIZE} Tf")

        parts.append("ET")
        return "\n".join(parts).encode("latin-1")

    # Build the PDF binary
    buf = bytearray()

    def write(data: bytes):
        buf.extend(data)

    write(b"%PDF-1.4\n")
    write(b"%\xe2\xe3\xcf\xd3\n")  # binary comment to mark as binary

    obj_positions = {}

    def emit_obj(oid: int, dictionary: str, stream: bytes = None):
        obj_positions[oid] = len(buf)
        write(f"{oid} 0 obj\n".encode())
        if stream is not None:
            d = dictionary.rstrip().rstrip(">").rstrip()
            write(f"{d} /Length {len(stream)}>>\n".encode())
            write(b"stream\n")
            write(stream)
            write(b"\nendstream\n")
        else:
            write(f"{dictionary}\n".encode())
        write(b"endobj\n\n")

    # Catalog
    emit_obj(catalog_id,
             f"<< /Type /Catalog /Pages {page_tree_id} 0 R >>")

    # Content streams + pages
    content_ids = []
    page_ids = []
    # Emit content streams first (need them for pages)
    for pi, page_lines in enumerate(page_texts):
        content_id = first_content_id + pi
        stream = build_content_stream(page_lines)
        emit_obj(content_id,
                 f"<< /Type /XObject /Length {len(stream)}",
                 stream)
        content_ids.append(content_id)

    # Emit page objects
    font_res = ("<< /Font << /F1 << /Type /Font /Subtype /Type1 "
                "/BaseFont /Courier >> >> >>")
    for pi in range(num_pages):
        page_id = first_page_id + pi
        content_id = content_ids[pi]
        emit_obj(page_id,
                 (f"<< /Type /Page /Parent {page_tree_id} 0 R "
                  f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                  f"/Contents {content_id} 0 R "
                  f"/Resources {font_res} >>"))
        page_ids.append(page_id)

    # Page tree
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    emit_obj(page_tree_id,
             f"<< /Type /Pages /Kids [{kids}] /Count {num_pages} >>")

    # Font object (not strictly needed as we inlined it, but good practice)
    # Already inlined in resources

    # Write xref table
    xref_pos = len(buf)
    total_objs = max(obj_positions.keys()) + 1
    write(b"xref\n")
    write(f"0 {total_objs}\n".encode())
    write(b"0000000000 65535 f \n")
    for oid in range(1, total_objs):
        pos = obj_positions.get(oid, 0)
        write(f"{pos:010d} 00000 n \n".encode())

    # Trailer
    write(b"trailer\n")
    write(f"<< /Size {total_objs} /Root {catalog_id} 0 R >>\n".encode())
    write(b"startxref\n")
    write(f"{xref_pos}\n".encode())
    write(b"%%EOF\n")

    return bytes(buf)


# ---------------------------------------------------------------------------
# Generate one PDF per category
# ---------------------------------------------------------------------------
CATEGORY_FILENAMES = {
    "Farmers": "YojanaMitra_Farmers_Schemes_Reference",
    "Students": "YojanaMitra_Students_Schemes_Reference",
    "Women": "YojanaMitra_Women_Schemes_Reference",
    "Small Business Owners": "YojanaMitra_SmallBusiness_Schemes_Reference",
    "General Public": "YojanaMitra_GeneralPublic_Schemes_Reference",
}

generated = []
for category, schemes in by_category.items():
    fname = CATEGORY_FILENAMES.get(category, f"YojanaMitra_{category.replace(' ','_')}_Reference")
    title = f"YojanaMitra {category} Schemes Reference"
    pdf_bytes = make_pdf_bytes(title, category, schemes)
    out_path = out_dir / f"{fname}.pdf"
    out_path.write_bytes(pdf_bytes)
    size_kb = len(pdf_bytes) // 1024
    print(f"  Generated: {out_path.name}  ({size_kb} KB, {len(schemes)} schemes)")
    generated.append((fname, category, out_path, schemes))

# Write updated manifest
manifest = out_dir / "manifest.txt"
with open(manifest, "w", encoding="utf-8") as f:
    for fname, category, out_path, schemes in generated:
        official_urls = " | ".join(s.get("official_url", "") for s in schemes)
        f.write(f"{out_path.name}|compiled from official sources|https://www.india.gov.in|YojanaMitra Reference ({category})\n")

print(f"\nGenerated {len(generated)} PDFs in {out_dir}/")
print(f"Manifest updated: {manifest}")
