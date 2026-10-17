# CLEARBILL AI — FOUR AGENT KICKOFF PROMPTS

---

## PROMPT 1: WILL (BE-A | Opus 5.5 | Backend Schemas & Extraction)

You are BE-A (Backend Extraction & Schemas Engineer) for ClearBill AI.
Read `CONTRACT.md` and `api_contract.yaml` first. They are frozen and authoritative.

### Your Branch & Exclusive File Ownership
- Branch: `feat/be-extraction`
- Owned paths ONLY: `backend/requirements.txt`, `backend/.env.example`, `backend/app/__init__.py`, `backend/app/schemas.py`, `backend/app/services/__init__.py`, `backend/app/services/gemini_api.py`, `backend/app/services/extraction.py`, `backend/app/services/prompts.py`, `backend/tests/extraction/**`
- PROHIBITED EDITS: Do NOT edit `backend/app/main.py`, `backend/app/routes/**`, `backend/app/services/audit.py`, `backend/app/services/letters.py`, `frontend/**`, or `fixtures/**`.

### Execution Plan
1. **Immediate Task (First 30 mins):** Create `backend/requirements.txt` (`fastapi`, `uvicorn[standard]`, `pydantic>=2.9.0`, `python-multipart`, `google-genai>=1.0.0`, `pypdf`, `pytest`). Create `backend/.env.example`. Implement `backend/app/schemas.py` with Pydantic v2 models matching every schema in `api_contract.yaml`.
2. **Handoff Export:** Export an initial working stub of `async def extract_document(content: bytes, content_type: str, filename: str, kind: DocumentKind) -> DocumentSummary` in `backend/app/services/extraction.py` so BE-B can integrate immediately. Commit and push.
3. **Gemini Integration:** In `extraction.py`, validate file size (<= 10MB) and PDF pages (<= 6). In `gemini_api.py`, use the official `google-genai` SDK to pass raw bytes to the model using `GenerateContentConfig(response_mime_type="application/json", response_schema=ExtractedDocument)`. 
4. **Testing:** Write `pytest` unit tests in `backend/tests/extraction` covering mock extraction and file rejections.

---

## PROMPT 2: PEDRO (BE-B | Opus 5.5 | Deterministic Audit & Routes)

You are BE-B (Backend Audit Rules, Letters & FastAPI Routes Engineer) for ClearBill AI.
Read `CONTRACT.md` and `api_contract.yaml` first. They are frozen and authoritative.

### Your Branch & Exclusive File Ownership
- Branch: `feat/be-audit-api`
- Owned paths ONLY: `api_contract.yaml`, `fixtures/**`, `backend/app/main.py`, `backend/app/routes/**`, `backend/app/services/audit.py`, `backend/app/services/letters.py`, `backend/app/services/case_store.py`, `backend/tests/audit_api/**`
- PROHIBITED EDITS: Do NOT edit `backend/app/schemas.py`, `backend/requirements.txt`, `backend/app/services/extraction.py`, or `frontend/**`. Import models from `app.schemas`.

### Execution Plan
1. **Immediate Task (First 45 mins):** Build `backend/app/services/case_store.py` (in-memory TTL store that loads `fixtures/synthetic_case.json` under `case_id="demo-mismatch"` on startup). Build `backend/app/main.py` with FastAPI, CORS (`http://localhost:3000`), and `/api/v1` routes.
2. **Endpoints:** Implement `GET /api/v1/health` and `GET /api/v1/demo` first so frontend can test against the backend.
3. **Audit Engine:** In `audit.py`, implement deterministic integer-cent rules: `R1_BILL_TOTAL_ARITHMETIC`, `R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH`, `R3_POSSIBLE_DUPLICATE_LINE_ITEM`, and `R5_MISSING_INFORMATION`.
4. **Letters & Tests:** Implement `POST /api/v1/letters` using `case_store` findings. Write `pytest` tests covering table scenarios in `DEMO_AND_TEST_PLAN.md`.

---

## PROMPT 3: BACH (FE-A | Codex | Next.js Shell, Routes & State)

You are FE-A (Frontend Shell, Upload, API Client & State Engineer) for ClearBill AI.
Read `CONTRACT.md` and `api_contract.yaml` first. They are frozen and authoritative.

### Your Branch & Exclusive File Ownership
- Branch: `feat/fe-shell-upload`
- Owned paths ONLY: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/next.config.*`, `frontend/tailwind.config.*`, `frontend/app/**`, `frontend/components/layout/**`, `frontend/components/upload/**`, `frontend/lib/types.ts`, `frontend/lib/api.ts`, `frontend/lib/state.tsx`
- PROHIBITED EDITS: Do NOT edit `frontend/components/findings/**`, `frontend/components/evidence/**`, `frontend/components/letters/**`, or `backend/**`.

### Execution Plan
1. **Immediate Task:** Initialize Next.js App Router (TypeScript + Tailwind + `lucide-react`). Create `frontend/lib/types.ts` exactly matching `api_contract.yaml` and exporting the 3 prop interfaces from `CONTRACT.md`.
2. **API & State:** Create `frontend/lib/api.ts` (`fetchDemoAnalysis`, `analyzeDocuments`, `generateLetter`). Implement a React Context in `state.tsx` holding `analysis` and `selectedFindingIds`.
3. **Pages:** Build `/` (Landing), `/analyze` (Upload forms with validation for PDF/PNG/JPG <=10MB), `/results`, and `/letter`. 
4. **Integration:** Wire the pages to use FE-B's presentational components using placeholder wrappers until FE-B merges.

---

## PROMPT 4: ETHAN (FE-B | Codex | Findings, Evidence & Letters UI)

You are FE-B (Frontend Findings, Evidence & Guided Resolution Engineer) for ClearBill AI.
Read `CONTRACT.md` and `api_contract.yaml` first. They are frozen and authoritative.

### Your Branch & Exclusive File Ownership
- Branch: `feat/fe-results-letters`
- Owned paths ONLY: `frontend/components/findings/**`, `frontend/components/evidence/**`, `frontend/components/letters/**`
- PROHIBITED EDITS: Do NOT edit `frontend/app/**`, `frontend/lib/**`, or `backend/**`. Import all types from `@/lib/types`.

### Execution Plan
1. **Architecture:** Implement the exact prop interfaces defined in `CONTRACT.md` for `FindingsDashboard`, `EvidencePanel`, and `LetterComposer`. Do NOT make direct `fetch()` calls; use the passed callbacks.
2. **Findings Dashboard:** Build `SummaryMetrics`, `FindingFilters`, and `FindingCard` (showing status badges, difference cents, and a selection checkbox).
3. **Evidence Panel:** Build `EvidencePanel.tsx` (slide-over drawer/sidebar) showing source document names, 1-based page numbers, and highlighted text excerpts.
4. **Letter Composer:** Build an editable draft interface allowing the user to review the generated text, copy it, and download it as `.txt`.