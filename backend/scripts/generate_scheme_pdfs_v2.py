"""
generate_scheme_pdfs_v2.py
--------------------------
Generates authoritative scheme reference PDFs using reportlab if available,
falling back to a text-file-to-PDF approach using pypdf PdfWriter.

Clearly labels all PDFs as YojanaMitra compiled references, NOT official docs.
Run from backend/ directory.
"""
import json
import textwrap
from pathlib import Path
from datetime import datetime
from collections import defaultdict

out_dir = Path("data/govt_pdfs")
out_dir.mkdir(parents=True, exist_ok=True)

data_path = Path("data/schemes.json")
with open(data_path, encoding="utf-8") as f:
    all_schemes = json.load(f)

by_category = defaultdict(list)
for s in all_schemes:
    by_category[s["category"]].append(s)

GENERATED_AT = datetime.now().strftime("%d %B %Y")

CATEGORY_FILENAMES = {
    "Farmers": "YojanaMitra_Farmers_Schemes_Reference",
    "Students": "YojanaMitra_Students_Schemes_Reference",
    "Women": "YojanaMitra_Women_Schemes_Reference",
    "Small Business Owners": "YojanaMitra_SmallBusiness_Schemes_Reference",
    "General Public": "YojanaMitra_GeneralPublic_Schemes_Reference",
}


def scheme_to_text_lines(scheme: dict) -> list[str]:
    """Convert a scheme dict to a list of plain-text lines."""
    lines = []
    name = scheme.get("name", "Unknown Scheme")
    sid = scheme.get("id", "")
    official_url = scheme.get("official_url", "N/A")
    last_verified = scheme.get("last_verified", "N/A")
    source_note = scheme.get("source_note", "")

    lines.append(f"SCHEME: {name}")
    lines.append(f"ID: {sid}")
    lines.append(f"Official Portal: {official_url}")
    lines.append(f"Last Verified: {last_verified}")
    if source_note:
        lines.append(f"Source: {source_note}")
    lines.append("")

    description = scheme.get("description", "")
    if description:
        lines.append("DESCRIPTION:")
        for para in textwrap.wrap(description, 85):
            lines.append(f"  {para}")
        lines.append("")

    beneficiaries = scheme.get("beneficiaries", "")
    if beneficiaries:
        lines.append("BENEFICIARIES:")
        for para in textwrap.wrap(str(beneficiaries), 85):
            lines.append(f"  {para}")
        lines.append("")

    eligibility = scheme.get("eligibility", {})
    if eligibility:
        lines.append("ELIGIBILITY:")
        if isinstance(eligibility, dict):
            for key, val in eligibility.items():
                if isinstance(val, list):
                    lines.append(f"  {key.upper()}:")
                    for item in val:
                        for para in textwrap.wrap(f"    - {item}", 83):
                            lines.append(para)
                elif val:
                    for para in textwrap.wrap(f"  {key}: {val}", 85):
                        lines.append(para)
        else:
            for para in textwrap.wrap(str(eligibility), 85):
                lines.append(f"  {para}")
        lines.append("")

    benefits = scheme.get("benefits", [])
    if benefits:
        lines.append("BENEFITS:")
        if isinstance(benefits, list):
            for b in benefits:
                for para in textwrap.wrap(f"  - {b}", 85):
                    lines.append(para)
        else:
            for para in textwrap.wrap(str(benefits), 85):
                lines.append(f"  {para}")
        lines.append("")

    application = scheme.get("application", {})
    if application:
        lines.append("HOW TO APPLY:")
        if isinstance(application, dict):
            for key, val in application.items():
                if isinstance(val, list):
                    lines.append(f"  {key.upper()}:")
                    for item in val:
                        for para in textwrap.wrap(f"    - {item}", 83):
                            lines.append(para)
                elif val:
                    for para in textwrap.wrap(f"  {key}: {val}", 85):
                        lines.append(para)
        else:
            for para in textwrap.wrap(str(application), 85):
                lines.append(f"  {para}")
        lines.append("")

    lines.append("-" * 88)
    lines.append("")
    return lines


def build_all_lines(category: str, schemes: list) -> list[str]:
    all_lines = []
    all_lines.append("=" * 88)
    all_lines.append(f"YOJANAMITRA SCHEME REFERENCE — {category.upper()}")
    all_lines.append(f"Compiled from official Indian Government sources | Generated: {GENERATED_AT}")
    all_lines.append(
        "NOTICE: This is a reference document compiled by YojanaMitra. "
        "It is NOT an official government publication."
    )
    all_lines.append(
        "For authoritative information, visit the official portal URLs listed for each scheme."
    )
    all_lines.append("=" * 88)
    all_lines.append("")

    for idx, scheme in enumerate(schemes, 1):
        all_lines.append(f"[{idx}]")
        all_lines.extend(scheme_to_text_lines(scheme))

    all_lines.append("")
    all_lines.append("END OF DOCUMENT")
    return all_lines


# ─── Try reportlab first (best quality) ────────────────────────────────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    REPORTLAB = True
    print("Using reportlab for PDF generation.")
except ImportError:
    REPORTLAB = False
    print("reportlab not available; using pypdf text-based PDF generation.")


def make_pdf_reportlab(out_path: Path, category: str, schemes: list):
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=14, spaceAfter=6)
    normal = ParagraphStyle("Normal2", parent=styles["Normal"], fontSize=9, leading=13)
    bold_style = ParagraphStyle("Bold2", parent=styles["Normal"], fontSize=9, leading=13, fontName="Helvetica-Bold")
    notice_style = ParagraphStyle("Notice", parent=styles["Normal"], fontSize=7.5, textColor=colors.grey)

    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    story = []

    story.append(Paragraph(f"YojanaMitra Scheme Reference — {category}", title_style))
    story.append(Paragraph(f"Generated: {GENERATED_AT}", notice_style))
    story.append(Paragraph(
        "NOTICE: This is a reference document compiled by YojanaMitra from verified official "
        "Indian government sources. It is NOT an official government publication. For "
        "authoritative information, visit the official portal URLs listed for each scheme.",
        notice_style))
    story.append(Spacer(1, 6*mm))

    for idx, scheme in enumerate(schemes, 1):
        name = scheme.get("name", "Unknown Scheme")
        sid = scheme.get("id", "")
        official_url = scheme.get("official_url", "N/A")
        last_verified = scheme.get("last_verified", "N/A")
        source_note = scheme.get("source_note", "")

        story.append(Paragraph(f"{idx}. {name}", bold_style))
        story.append(Paragraph(f"ID: {sid} | Official Portal: {official_url}", notice_style))
        story.append(Paragraph(f"Last Verified: {last_verified} | {source_note}", notice_style))
        story.append(Spacer(1, 2*mm))

        for field, label in [
            ("description", "Description"),
            ("beneficiaries", "Beneficiaries"),
        ]:
            val = scheme.get(field, "")
            if val:
                story.append(Paragraph(f"<b>{label}:</b>", normal))
                story.append(Paragraph(str(val), normal))
                story.append(Spacer(1, 1*mm))

        eligibility = scheme.get("eligibility", {})
        if eligibility:
            story.append(Paragraph("<b>Eligibility:</b>", normal))
            if isinstance(eligibility, dict):
                for key, val in eligibility.items():
                    if isinstance(val, list):
                        story.append(Paragraph(f"{key.title()}:", normal))
                        for item in val:
                            story.append(Paragraph(f"• {item}", normal))
                    elif val:
                        story.append(Paragraph(f"{key.title()}: {val}", normal))
            else:
                story.append(Paragraph(str(eligibility), normal))
            story.append(Spacer(1, 1*mm))

        benefits = scheme.get("benefits", [])
        if benefits:
            story.append(Paragraph("<b>Benefits:</b>", normal))
            if isinstance(benefits, list):
                for b in benefits:
                    story.append(Paragraph(f"• {b}", normal))
            else:
                story.append(Paragraph(str(benefits), normal))
            story.append(Spacer(1, 1*mm))

        application = scheme.get("application", {})
        if application:
            story.append(Paragraph("<b>How to Apply:</b>", normal))
            if isinstance(application, dict):
                for key, val in application.items():
                    if isinstance(val, list):
                        story.append(Paragraph(f"{key.title()}:", normal))
                        for item in val:
                            story.append(Paragraph(f"• {item}", normal))
                    elif val:
                        story.append(Paragraph(f"{key.title()}: {val}", normal))
            else:
                story.append(Paragraph(str(application), normal))
            story.append(Spacer(1, 1*mm))

        story.append(Spacer(1, 4*mm))

    doc.build(story)


# ─── Fallback: build PDF from text using pypdf PdfWriter ───────────────────
def make_pdf_pypdf_text(out_path: Path, category: str, schemes: list):
    """
    Build a valid PDF using pypdf's PdfWriter with blank pages.
    We embed text via PDF content streams written as raw page dictionaries.
    This avoids the /Length duplicate-key bug by constructing the stream dict properly.
    """
    from pypdf import PdfWriter
    from pypdf.generic import (
        ArrayObject, DictionaryObject, DecodedStreamObject,
        NameObject, NumberObject, ArrayObject, RectangleObject,
        StreamObject,
    )

    all_lines = build_all_lines(category, schemes)

    # Split into pages (50 lines per page)
    LINES_PER_PAGE = 52
    pages_lines = []
    for i in range(0, len(all_lines), LINES_PER_PAGE):
        pages_lines.append(all_lines[i:i + LINES_PER_PAGE])

    writer = PdfWriter()

    def escape_ps(text: str) -> str:
        """Escape text for PDF string literal, ASCII only."""
        result = []
        for ch in text:
            if ch == '\\':
                result.append('\\\\')
            elif ch == '(':
                result.append('\\(')
            elif ch == ')':
                result.append('\\)')
            elif ord(ch) > 126 or ord(ch) < 32:
                result.append(' ')
            else:
                result.append(ch)
        return ''.join(result)

    for page_lines in pages_lines:
        # Build content stream
        FONT_SIZE = 9
        LINE_HEIGHT = 12
        START_Y = 780
        LEFT_X = 40

        ops = ["BT", f"/F1 {FONT_SIZE} Tf", f"{LEFT_X} {START_Y} Td", f"{LINE_HEIGHT} TL"]
        for line in page_lines:
            safe = escape_ps(line)
            ops.append(f"({safe}) Tj T*")
        ops.append("ET")

        content_bytes = "\n".join(ops).encode("latin-1")

        page = writer.add_blank_page(width=612, height=842)

        # Build stream object for content
        stream_obj = DecodedStreamObject()
        stream_obj.set_data(content_bytes)

        # Font resource
        font_dict = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Courier"),
        })
        font_ref = writer._add_object(font_dict)

        resources = DictionaryObject({
            NameObject("/Font"): DictionaryObject({
                NameObject("/F1"): font_ref,
            })
        })

        content_ref = writer._add_object(stream_obj)
        page_obj = page.get_object()
        page_obj[NameObject("/Contents")] = content_ref
        page_obj[NameObject("/Resources")] = resources

    with open(out_path, "wb") as f:
        writer.write(f)


# ─── Generate PDFs ──────────────────────────────────────────────────────────
generated = []
for category, schemes in by_category.items():
    fname = CATEGORY_FILENAMES.get(category, f"YojanaMitra_{category.replace(' ','_')}_Reference")
    out_path = out_dir / f"{fname}.pdf"

    try:
        if REPORTLAB:
            make_pdf_reportlab(out_path, category, schemes)
        else:
            make_pdf_pypdf_text(out_path, category, schemes)

        size_kb = out_path.stat().st_size // 1024
        print(f"  Generated: {out_path.name}  ({size_kb} KB, {len(schemes)} schemes)")
        generated.append((fname, category, out_path, schemes))
    except Exception as e:
        print(f"  ERROR generating {fname}: {e}")
        import traceback; traceback.print_exc()

# Write updated manifest
manifest = out_dir / "manifest.txt"
with open(manifest, "w", encoding="utf-8") as f:
    for fname, category, out_path, schemes in generated:
        f.write(
            f"{out_path.name}|compiled from official sources|"
            f"https://www.india.gov.in|YojanaMitra Reference ({category})\n"
        )

print(f"\nGenerated {len(generated)} PDFs in {out_dir}/")
print(f"Manifest updated: {manifest}")
