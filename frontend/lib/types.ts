/**
 * TypeScript mirror of api_contract.yaml (components.schemas), plus the shared
 * component prop interfaces and display helpers. The contract is frozen: change
 * the YAML first, then this file. Money is always integer USD cents.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type DocumentKind = "bill" | "eob" | "estimate";

export type ExtractionQuality = "complete" | "partial" | "failed";

export type FindingStatus = "verified_inconsistency" | "needs_review" | "insufficient_information";

export type FindingSeverity = "info" | "low" | "medium";

export type FindingCategory =
  | "arithmetic"
  | "insurance_comparison"
  | "possible_duplicate"
  | "estimate_comparison"
  | "price_benchmark"
  | "missing_context";

export type LetterIntent = "clarification" | "dispute";

export type ErrorCode =
  | "INVALID_UPLOAD"
  | "DOCUMENT_UNREADABLE"
  | "FILE_TOO_LARGE"
  | "EXTRACTION_FAILED"
  | "MODEL_UNAVAILABLE"
  | "MODEL_AUTH_FAILED"
  | "GEMINI_UNAVAILABLE"
  | "CASE_NOT_FOUND"
  | "BAD_SELECTION"
  | "INTERNAL_ERROR";

// ---------------------------------------------------------------------------
// Schemas (fields not in the contract's `required` list are optional)
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: "ok";
  demo_mode: boolean;
}

export interface LineItem {
  id: string;
  description: string;
  code?: string | null;
  /** YYYY-MM-DD or null */
  service_date?: string | null;
  quantity?: number | null;
  unit_amount_cents?: number | null;
  line_total_cents?: number | null;
  /** 1-based */
  page?: number | null;
  source_text?: string | null;
}

export interface DocumentSummary {
  id: string;
  kind: DocumentKind;
  filename: string;
  pages: number;
  extraction_quality: ExtractionQuality;
  provider_name?: string | null;
  insurer_name?: string | null;
  document_date?: string | null;
  service_date?: string | null;
  claim_number?: string | null;
  total_charges_cents?: number | null;
  /** Current provider statement balance. */
  amount_due_cents?: number | null;
  /** Typically from an EOB. */
  patient_responsibility_cents?: number | null;
  insurance_paid_cents?: number | null;
  adjustments_cents?: number | null;
  /** Good Faith Estimate total. */
  expected_total_cents?: number | null;
  eob_status?: string | null;
  line_items: LineItem[];
  extraction_warnings: string[];
}

export interface EvidenceRef {
  document_id: string;
  /** 1-based */
  page?: number | null;
  line_item_id?: string | null;
  field: string;
  amount_cents?: number | null;
  source_text?: string | null;
  verification_note?: string | null;
}

/** Alias for EvidenceRef (the contract's name). */
export type EvidenceItem = EvidenceRef;

export interface Finding {
  id: string;
  rule_id: string;
  category: FindingCategory;
  status: FindingStatus;
  severity: FindingSeverity;
  title: string;
  explanation: string;
  alternative_explanations: string[];
  next_step: string;
  /** A difference to verify. Never present it as proven savings. */
  difference_cents?: number | null;
  evidence: EvidenceRef[];
  missing_information: string[];
}

export interface AnalysisResponse {
  case_id: string;
  is_demo: boolean;
  documents: DocumentSummary[];
  findings: Finding[];
  limitations: string[];
  safety_disclaimer: string;
}

export interface LetterRequest {
  case_id: string;
  /** At least one id. */
  finding_ids: string[];
  intent: LetterIntent;
}

export interface LetterResponse {
  subject: string;
  body: string;
  safety_note: string;
  is_fallback: boolean;
}

export interface ErrorDetail {
  code: ErrorCode;
  message: string;
  retryable: boolean;
}

export interface ErrorResponse {
  error: ErrorDetail;
}

// ---------------------------------------------------------------------------
// Component props (frontend handoff: FE-A pages render these FE-B components)
// ---------------------------------------------------------------------------

export interface FindingsDashboardProps {
  analysis: AnalysisResponse;
  selectedFindingIds: string[];
  activeFindingId: string | null;
  onToggleFinding: (findingId: string) => void;
  onInspectFinding: (findingId: string) => void;
  onProceedToLetter: () => void;
}

export interface EvidencePanelProps {
  analysis: AnalysisResponse;
  finding: Finding;
  isSelected: boolean;
  /** Fictional patient name shown on the document preview, when known. */
  patientName?: string | null;
  onToggleFinding: (findingId: string) => void;
  /** Make sure the finding is selected, then open the letter composer. */
  onAskAboutFinding: (findingId: string) => void;
  onClose: () => void;
}

export interface LetterComposerProps {
  analysis: AnalysisResponse;
  selectedFindings: Finding[];
  initialIntent: LetterIntent;
  draft: LetterResponse | null;
  isGenerating: boolean;
  error: string | null;
  onGenerateDraft: (intent: LetterIntent) => Promise<void>;
  onBackToResults: () => void;
  /** Optional: receives the user's edits so they survive leaving the page. */
  onDraftChange?: (draft: LetterResponse) => void;
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

/** 64000 -> "$640.00"; -1050 -> "-$10.50"; null/undefined -> "-". Exact integer math, no floats. */
export function formatCents(cents: number | null | undefined): string {
  if (cents == null || !Number.isFinite(cents)) return "-";
  const whole = Math.round(cents);
  const abs = Math.abs(whole);
  const dollars = Math.floor(abs / 100).toLocaleString("en-US");
  const remainder = String(abs % 100).padStart(2, "0");
  return `${whole < 0 ? "-" : ""}$${dollars}.${remainder}`;
}

/** "2026-10-01" -> "10/01/2026"; anything else is returned as-is; null -> null. */
export function formatDate(date: string | null | undefined): string | null {
  if (!date) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  return match ? `${match[2]}/${match[3]}/${match[1]}` : date;
}

export const KIND_LABEL: Record<DocumentKind, string> = {
  bill: "Medical Bill",
  eob: "Insurance EOB",
  estimate: "Good Faith Estimate",
};

export const STATUS_LABEL: Record<FindingStatus, string> = {
  needs_review: "Needs review",
  verified_inconsistency: "Verified inconsistency",
  insufficient_information: "Not enough information",
};

export const SEVERITY_LABEL: Record<FindingSeverity, string> = {
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export const CATEGORY_LABEL: Record<FindingCategory, string> = {
  arithmetic: "Math",
  insurance_comparison: "Insurance comparison",
  possible_duplicate: "Possible repeat charge",
  estimate_comparison: "Estimate comparison",
  price_benchmark: "Price reference",
  missing_context: "Missing context",
};

const FIELD_LABEL: Record<string, string> = {
  amount_due_cents: "Current balance due",
  patient_responsibility_cents: "Patient responsibility",
  total_charges_cents: "Total charges",
  insurance_paid_cents: "Insurance paid",
  adjustments_cents: "Adjustments",
  expected_total_cents: "Estimated total",
};

/** Human label for an EvidenceRef.field path such as "amount_due_cents" or "line_items[1].line_total_cents". */
export function fieldLabel(field: string): string {
  return FIELD_LABEL[field] ?? (field.startsWith("line_items") ? "Line item" : field);
}

/** Only these statuses can be included in a request letter; the rest are informational. */
export function isSelectableStatus(status: FindingStatus): boolean {
  return status === "needs_review" || status === "verified_inconsistency";
}
