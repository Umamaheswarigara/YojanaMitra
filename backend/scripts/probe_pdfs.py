"""
probe_pdfs.py — Probe known government PDF URLs and download ones that are real PDFs.
Run from backend directory.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
import httpx

# Well-known, stable official government PDF URLs sourced from:
# - pib.gov.in (Press Information Bureau - India's official press releases)
# - pmkisan.gov.in
# - aicte-india.org
# - pmfby.gov.in
# These are commonly cited in research and news articles as direct PDF links.

CANDIDATES = [
    # PIB Press Releases - direct PDF links
    ("PM-KISAN_PIB_Factsheet",
     "https://pib.gov.in/Pressreleaseshare.aspx?PRID=1870355",
     "https://pib.gov.in", "Press Information Bureau, GOI"),

    # PMFBY operational guidelines hosted on pmfby.gov.in
    ("PMFBY_Operational_Guidelines",
     "https://pmfby.gov.in/pdf/operational_guidelines_PMFBY_01052016.pdf",
     "https://pmfby.gov.in", "Ministry of Agriculture & Farmers Welfare"),

    # PMFBY revised guidelines 2020
    ("PMFBY_Revised_Guidelines_2020",
     "https://pmfby.gov.in/pdf/Revised_Operational_Guidelines_PMFBY.pdf",
     "https://pmfby.gov.in", "Ministry of Agriculture & Farmers Welfare"),

    # PM Mudra Yojana - Finance Ministry
    ("PMMY_Guidelines",
     "https://financialservices.gov.in/sites/default/files/PMMY%20Circular%20DFS.pdf",
     "https://financialservices.gov.in", "Department of Financial Services, MOF"),

    # AICTE Pragati scheme
    ("AICTE_Pragati_Degree_Guidelines",
     "https://www.aicte-india.org/sites/default/files/Pragati-Guidelines-2022-23.pdf",
     "https://www.aicte-india.org", "AICTE"),

    # NSP about page / PDF
    ("NSP_Scholarship_Guidelines",
     "https://scholarships.gov.in/public/schemeGuidelines/NSP_2.0_operational_guidelines.pdf",
     "https://scholarships.gov.in", "National Scholarship Portal, MoE"),

    # Sukanya Samriddhi - Ministry of Finance
    ("Sukanya_Samriddhi_Rules",
     "https://financialservices.gov.in/sites/default/files/SSA_Rules_English.pdf",
     "https://financialservices.gov.in", "Department of Financial Services, MOF"),

    # PM Ujjwala Yojana
    ("PM_Ujjwala_Guidelines",
     "https://www.petroleum.nic.in/sites/default/files/pmuy.pdf",
     "https://www.petroleum.nic.in", "Ministry of Petroleum and Natural Gas"),

    # Atal Pension Yojana PFRDA
    ("Atal_Pension_Yojana_Circular",
     "https://www.pfrda.org.in/writereaddata/links/apy%20circular%20merged4f54e7ba-91e5-4f98-aa5a-dc72d2d55177.pdf",
     "https://www.pfrda.org.in", "PFRDA - Pension Fund Regulatory and Development Authority"),
]

headers = {
    "User-Agent": "Mozilla/5.0 (compatible; YojanaMitraBot/1.0; +https://github.com/yojanamitra)",
    "Accept": "application/pdf,*/*",
}

out_dir = Path("data/govt_pdfs")
out_dir.mkdir(parents=True, exist_ok=True)

results = []
print(f"Probing {len(CANDIDATES)} candidate URLs…\n")

for name, url, source_url, source_name in CANDIDATES:
    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
        ct = resp.headers.get("content-type", "")
        is_pdf = (resp.status_code == 200 and
                  ("application/pdf" in ct or resp.content[:4] == b"%PDF"))
        status = "✓ PDF" if is_pdf else f"✗ {resp.status_code} {ct[:40]}"
        print(f"  {status} | {name}")
        if is_pdf:
            out_path = out_dir / f"{name}.pdf"
            out_path.write_bytes(resp.content)
            results.append((name, url, source_url, source_name, out_path, len(resp.content)))
            print(f"           Saved {len(resp.content)//1024} KB → {out_path.name}")
    except Exception as e:
        print(f"  ✗ ERROR  | {name} — {str(e)[:60]}")
    time.sleep(0.5)

print(f"\n{'='*60}")
print(f"Downloaded {len(results)} real PDF(s):")
for name, url, source_url, source_name, path, size in results:
    print(f"  {path.name}  ({size//1024} KB)  source: {source_url}")

# Write manifest
manifest = out_dir / "manifest.txt"
with manifest.open("w", encoding="utf-8") as f:
    for name, url, source_url, source_name, path, size in results:
        f.write(f"{path.name}|{url}|{source_url}|{source_name}\n")

print(f"\nManifest written: {manifest}")
