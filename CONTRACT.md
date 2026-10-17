# CLEARBILL AI — MULTI-AGENT COLLABORATION & OWNERSHIP CONTRACT

> **Authority:** This file (`CONTRACT.md`) and `api_contract.yaml` are the single source of truth for ClearBill AI. Any legacy `contract.md` or `project_spec.md` is superseded and deprecated.

## 1. Exclusive Directory & File Ownership

Every agent works in its own local clone and dedicated Git branch. **No agent may create, modify, or delete files outside its assigned paths.**

| Role / Machine | Branch Name | Exclusively Owned Paths | Prohibited Paths |
| :--- | :--- | :--- | :--- |
| **BE-A (Opus 5.5 #1)** | `feat/be-extraction` | `backend/requirements.txt`<br>`backend/.env.example`<br>`backend/app/__init__.py`<br>`backend/app/schemas.py`<br>`backend/app/services/__init__.py`<br>`backend/app/services/gemini_api.py`<br>`backend/app/services/extraction.py`<br>`backend/app/services/prompts.py`<br>`backend/tests/extraction/**` | `backend/app/main.py`, `backend/app/routes/**`, `backend/app/services/audit.py`, `frontend/**`, root docs |
| **BE-B (Opus 5.5 #2)** | `feat/be-audit-api` | `api_contract.yaml`<br>`fixtures/**`<br>`backend/app/main.py`<br>`backend/app/routes/**`<br>`backend/app/services/audit.py`<br>`backend/app/services/letters.py`<br>`backend/app/services/case_store.py`<br>`backend/tests/audit_api/**` | `backend/app/schemas.py`, `backend/requirements.txt`, `backend/app/services/extraction.py`, `frontend/**` |
| **FE-A (Codex #1)** | `feat/fe-shell-upload` | `frontend/package.json`<br>`frontend/tsconfig.json`<br>`frontend/next.config.*`<br>`frontend/tailwind.config.*`<br>`frontend/.env.example`<br>`frontend/public/**`<br>`frontend/app/**`<br>`frontend/components/layout/**`<br>`frontend/components/upload/**`<br>`frontend/lib/api.ts`<br>`frontend/lib/types.ts`<br>`frontend/lib/state.tsx`<br>`frontend/tests/shell_upload.test.*` | `frontend/components/findings/**`, `frontend/components/evidence/**`, `frontend/components/letters/**`, `backend/**` |
| **FE-B (Codex #2)** | `feat/fe-results-letters` | `frontend/components/findings/**`<br>`frontend/components/evidence/**`<br>`frontend/components/letters/**`<br>`frontend/tests/results_letters.test.*` | `frontend/app/**`, `frontend/lib/**`, `frontend/package.json`, `backend/**` |
| **Human Lead** | `main` (via PRs) | `CONTRACT.md`, `IMPLEMENTATION_PLAN.md`, `AGENT_TASKS.md`, `DEMO_AND_TEST_PLAN.md`, `README.md`, `.gitignore` | Merges PRs after smoke check |

---

## 2. Frozen Inter-Agent Code Interfaces

### 2.1 Backend Handoff (`BE-A` -> `BE-B`)
* `BE-A` defines all canonical Pydantic v2 models in `backend/app/schemas.py` matching `api_contract.yaml` (`DocumentKind`, `ExtractionQuality`, `FindingStatus`, `FindingSeverity`, `FindingCategory`, `LetterIntent`, `LineItem`, `DocumentSummary`, `EvidenceRef`, `Finding`, `AnalysisResponse`, `LetterRequest`, `LetterResponse`, `ErrorDetail`, `ErrorResponse`, and internal `ExtractedDocument`).
* `BE-A` exports the following async-compatible function in `backend/app/services/extraction.py`:
  ```python
  async def extract_document(
      content: bytes,
      content_type: str,
      filename: str,
      kind: DocumentKind,
  ) -> DocumentSummary:
      """
      Validates file signature/size/pages, calls Gemini multimodal structured output,
      normalizes currency to integer cents and dates to YYYY-MM-DD (or None),
      and returns a validated DocumentSummary. Raises ExtractionError (with ErrorCode) on failure.
      """