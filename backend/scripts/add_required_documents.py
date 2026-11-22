"""
add_required_documents.py
--------------------------
Adds a 'required_documents' field to all 23 schemes in schemes.json.
Documents are based on official scheme guidelines and are realistic — not invented.
Run from backend/ directory.
"""
import json
from pathlib import Path

data_path = Path("data/schemes.json")
with open(data_path, encoding="utf-8") as f:
    schemes = json.load(f)

# Required documents per scheme (verified from official guidelines)
REQUIRED_DOCS = {
    "pm-kisan": [
        "Land ownership/cultivable land records (Khasra, Khatauni or State equivalent)",
        "Aadhaar card (for eKYC — mandatory for registered farmers)",
        "Bank account details (for Direct Benefit Transfer)",
        "Mobile number registered with Aadhaar",
    ],
    "nsp-scholarships": [
        "Aadhaar card",
        "Previous year academic mark sheet / pass certificate",
        "Income certificate (from competent authority) if applicable",
        "Bank account details (account must be in applicant's name)",
        "Domicile/residence certificate as required by specific scholarship",
        "Caste/community certificate if applicable to the scholarship",
    ],
    "pmfby": [
        "Land records (Khasra number / cultivated area details)",
        "Sowing certificate (issued by Patwari or revenue authority)",
        "Bank account details",
        "Aadhaar card",
        "Previous year crop details if claiming continued coverage",
    ],
    "kisan-credit-card": [
        "Land ownership / lease / tenancy documents",
        "Identity proof (Aadhaar / Voter ID / PAN card)",
        "Address proof",
        "Passport-size photographs",
        "No-dues certificate from other banks (if applicable)",
    ],
    "pmksy-per-drop-more-crop": [
        "Land ownership records or lease deed",
        "Aadhaar card",
        "Bank account details",
        "Soil test report (if required by state)",
        "Application form from State Agriculture Department",
    ],
    "pm-usp-csss": [
        "Class 12 mark sheet showing top 20 percentile status",
        "Income certificate (family income < ₹8 lakh for renewal; fresh — no income limit)",
        "Bank account details (in applicant's name)",
        "Aadhaar card",
        "Institution / college enrollment proof",
    ],
    "nmmss": [
        "Class 8 mark sheet",
        "State MAT and SAT examination score card",
        "Family income certificate (below ₹3.5 lakh per year)",
        "Caste certificate if applicable",
        "Bank account details (in applicant's name)",
        "Aadhaar card",
    ],
    "pm-yasasvi": [
        "OBC / EBC / DNT community certificate",
        "Family income certificate (below ₹2.5 lakh per year)",
        "Class 8 or 10 mark sheet",
        "PM YASASVI entrance test (YET) admit card and score card",
        "Aadhaar card",
        "Bank account details",
    ],
    "national-overseas-scholarship": [
        "SC / ST or notified community caste certificate",
        "Income certificate (family income < ₹8 lakh per year)",
        "Undergraduate and postgraduate degree certificates and mark sheets",
        "Admission letter from foreign university",
        "Age proof (must be below 35 years)",
        "Aadhaar card",
        "Passport (valid)",
    ],
    "pre-matric-sc-scholarship": [
        "Scheduled Caste certificate",
        "Income certificate (family income within scheme limit)",
        "Previous class mark sheet",
        "School enrollment certificate",
        "Bank account details (in student's or parent's name)",
        "Aadhaar card",
    ],
    "aicte-pragati-degree": [
        "AICTE-approved degree engineering college admission letter",
        "Income certificate (family income < ₹8 lakh per year)",
        "Proof of being a girl student (Aadhaar / birth certificate)",
        "Class 12 mark sheet",
        "Bank account details (in applicant's name)",
    ],
    "aicte-pragati-diploma": [
        "AICTE-approved diploma / polytechnic college admission letter",
        "Income certificate (family income < ₹8 lakh per year)",
        "Proof of being a girl student",
        "Class 10 mark sheet",
        "Bank account details (in applicant's name)",
    ],
    "pmmvy": [
        "Mother and Child Protection (MCP) card",
        "Aadhaar card of mother and spouse/partner",
        "Bank account details (in mother's name)",
        "Proof of first live birth (hospital/AWC record)",
        "Mobile number",
    ],
    "sukanya-samriddhi": [
        "Birth certificate of girl child (below 10 years)",
        "Parent / guardian identity proof (Aadhaar / PAN / Passport)",
        "Parent / guardian address proof",
        "Passport-size photographs of parent/guardian and girl child",
    ],
    "pm-ujjwala": [
        "BPL ration card or Pradhan Mantri Ujjwala Yojana application form (self-declaration)",
        "Identity proof of adult woman (Aadhaar card)",
        "Address proof",
        "Recent passport-size photograph",
        "Bank account details",
    ],
    "day-nrlm": [
        "Proof of residence in rural area",
        "Identity proof (Aadhaar card)",
        "Bank account details (for SHG group account)",
        "SHG formation and meeting register (maintained by the group)",
    ],
    "pm-mudra": [
        "Identity proof (Aadhaar / PAN / Voter ID)",
        "Address proof (utility bill / ration card / lease agreement)",
        "Business plan or activity proof",
        "Bank account details",
        "Proof of non-farm business activity (invoice / registration)",
        "Caste certificate if applying under special category",
    ],
    "pmegp": [
        "Identity proof (Aadhaar card)",
        "Address proof",
        "Educational certificates (minimum Class 8 pass for projects > ₹10 lakh)",
        "Project report / business plan",
        "EDP (Entrepreneurship Development Programme) training certificate (after selection)",
        "Caste certificate / special category certificate if applicable",
        "Bank account details",
    ],
    "pm-svanidhi": [
        "Street vendor identity card issued by Urban Local Body OR",
        "Vending certificate / letter of recommendation from ULB / TVC",
        "Aadhaar card",
        "Bank account details (savings account)",
        "Mobile number linked to Aadhaar",
    ],
    "pm-vishwakarma": [
        "Aadhaar card",
        "Mobile number linked to Aadhaar",
        "Bank account details",
        "Proof of traditional craft or trade (artisan / craftsperson self-declaration)",
        "PMVDP registration on official portal",
    ],
    "pm-jay": [
        "Aadhaar card OR Ration card OR voter ID (any one for verification)",
        "PM-JAY beneficiary card (Ayushman Card — issued after SECC verification)",
        "No separate application needed if name appears in SECC/PMJAY list",
    ],
    "pmay-urban-2": [
        "Identity proof (Aadhaar card)",
        "Address proof",
        "Income proof (salary slip / income certificate for EWS/LIG/MIG)",
        "Property ownership declaration (self-certification of no pucca house)",
        "Bank account details",
        "Home loan sanction letter (for CLSS component)",
    ],
    "atal-pension-yojana": [
        "Savings bank account (at any bank or post office)",
        "Aadhaar card (for KYC — mandatory for new subscribers)",
        "Mobile number registered with Aadhaar or bank account",
        "No separate application form — enroll via bank net-banking / branch",
    ],
}

updated = 0
for scheme in schemes:
    sid = scheme["id"]
    if sid in REQUIRED_DOCS:
        scheme["required_documents"] = REQUIRED_DOCS[sid]
        updated += 1

with open(data_path, "w", encoding="utf-8") as f:
    json.dump(schemes, f, ensure_ascii=False, indent=2)

print(f"Updated {updated} schemes with required_documents field.")
print(f"Schemes without required_documents: {sum(1 for s in schemes if 'required_documents' not in s)}")
