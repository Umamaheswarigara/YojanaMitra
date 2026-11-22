# YojanaMitra — Project Specification

**Tagline:** Government Schemes, Made Simple  
**Product:** AI-powered web application  
**Primary users:** Students, farmers, women, and small business owners

## 1. Purpose

Help people discover government schemes, understand them in simple language, and check whether they may be eligible.

## 2. Core features

1. **Find schemes:** Browse and search government schemes.
2. **Check eligibility:** Enter basic details to find potentially suitable schemes.
3. **AI assistant:** Ask questions and receive simple explanations about schemes.
4. **Understand documents:** Upload scheme-related PDFs and receive easy-to-understand summaries.
5. **Choose a language:** Use the app in English, Telugu, or Hindi.

## 3. Main user journey

1. Choose a preferred language.
2. Search or browse schemes, or enter details in the eligibility checker.
3. Review scheme benefits, eligibility, and application instructions.
4. Ask follow-up questions or upload a PDF for explanation.

## 4. Information shown for each scheme

- Scheme name and short description
- Intended beneficiaries and eligibility criteria
- Benefits and application process
- Official source link and last-verified date, when available

## 5. Proposed technology stack

- **Frontend:** React, HTML, CSS, and JavaScript
- **Backend:** Python and FastAPI
- **AI integration:** Large language model API
- **PDF processing:** PyPDF; OCR may be needed for scanned documents
- **Initial data storage:** JSON; a database can be added later
- **Development tools:** VS Code, Git, and GitHub

## 6. Data sources

Use verified government information, prioritizing official sources such as:

- [myScheme](https://www.myscheme.gov.in/) 
- [National Scholarship Portal](https://scholarships.gov.in/) 
- [India Portal](https://www.india.gov.in/) 
- [PM-KISAN](https://pmkisan.gov.in/) 

Show the source for scheme information and its last-verified date whenever available.

## 7. Scheme data structure

Each scheme record should contain:

- Scheme ID
- Scheme name
- Category
- Description
- Eligibility criteria
- Benefits
- Application process
- Official URL
- Last verified date

## 8. Functional requirements

- Search schemes by name or category and browse available schemes.
- View each scheme's summary, benefits, eligibility, application process, and source.
- Enter basic details to receive preliminary eligibility guidance.
- Ask questions about schemes through the AI assistant.
- Upload a PDF and request a plain-language explanation.
- Change the application language between English, Telugu, and Hindi.
- Show useful messages when a search, AI request, or document upload fails.

## 9. Eligibility checker inputs

Ask only for details needed to match schemes. Initial fields may include:

- Age
- State or region
- Occupation or student status
- Household income range
- Relevant category, such as farmer, student, or small business owner

Explain why each detail is requested. Do not request identity numbers or other sensitive details unless a verified feature requires them.

## 10. AI response requirements

- Answer using retrieved, verified government scheme information.
- Include official source links with scheme-related answers.
- Do not invent benefits, eligibility rules, or deadlines.
- Clearly say when information is unavailable or uncertain.

## 11. Non-functional requirements

- Work on mobile phones, tablets, and desktop screens.
- Use clear language and straightforward navigation.
- Provide accessible text, controls, and form labels.
- Validate inputs and show clear, helpful error messages.
- Keep common actions and responses reasonably fast.

## 12. Privacy and security

- Collect only the information needed for the requested feature.
- Do not expose AI or other secret API keys in frontend code.
- Validate uploaded files and set a file size limit.
- Avoid storing personal details or uploaded documents unless needed and disclosed.
- Explain how user information and documents are handled.

## 13. Error handling

- If a service is unavailable, explain the issue and offer a retry where appropriate.
- If a PDF is too large, invalid, or unreadable, explain what the user can try next.
- If no schemes match, let users adjust their search or eligibility details.
- If the AI cannot verify an answer, direct users to the scheme's official source.

## 14. Limitations

- Eligibility results are preliminary guidance, not official approval.
- Scheme information depends on the availability and freshness of reliable sources.
- AI explanations can be wrong and should be checked against official information.
- Scanned PDFs may need OCR and may not be readable in the first version.
- The app does not submit government applications on users' behalf.

## 15. Future enhancements

- Voice-based assistance
- Support for more Indian languages
- Automatic updates from official sources
- User accounts and saved schemes
- Notifications about scheme updates and deadlines

## 16. Initial project scope

The first version is a responsive web app for scheme discovery, preliminary eligibility guidance, multilingual assistance, and PDF explanations. Scheme data, AI responses, and document processing require suitable backend services and verified government sources.

## 17. Acceptance criteria

The MVP is complete when:

- Users can search for schemes and view their details and official sources.
- The eligibility checker displays matching or potentially matching schemes based on the user's inputs.
- The AI assistant answers scheme-related questions with official sources and communicates uncertainty.
- Users can upload a readable PDF and receive an understandable summary, or a clear error if it cannot be processed.
- Users can select English, Telugu, or Hindi and use the core interface in that language.
- The application works on mobile and desktop screens.
