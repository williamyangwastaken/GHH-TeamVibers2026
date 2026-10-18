/**
 * Offline demo support, ported from the original single-file prototype:
 *  - two extra synthetic sample cases that exist only in the frontend, and
 *  - a deterministic template letter used when the backend cannot draft one.
 * The headline "demo-mismatch" case comes from GET /api/v1/demo (see lib/api.ts).
 */

import {
  formatCents,
  type AnalysisResponse,
  type DocumentSummary,
  type EvidenceRef,
  type Finding,
  type LetterIntent,
  type LetterResponse,
} from "./types";

// ---------------------------------------------------------------------------
// Sample cases
// ---------------------------------------------------------------------------

export type SampleKey = "demo-mismatch" | "demo-sarah" | "demo-bill-only";

export const SAMPLE_OPTIONS: { key: SampleKey; label: string }[] = [
  { key: "demo-mismatch", label: "Bill + EOB mismatch" },
  { key: "demo-sarah", label: "Itemized bill (Sarah)" },
  { key: "demo-bill-only", label: "Bill only (no EOB)" },
];

const PATIENTS: Record<SampleKey, string> = {
  "demo-mismatch": "Jordan Rivera",
  "demo-bill-only": "Jordan Rivera",
  "demo-sarah": "Sarah Johnson",
};

const SAFETY_DISCLAIMER =
  "Educational prototype; review the original documents and consult the provider or insurer. Not legal, medical, or insurance advice.";

/** The itemized bill shown on the homepage (bill only, no EOB). */
export const SARAH_ROWS = [
  { id: "li_s1", code: "99214", desc: "Office Visit (Level 4)", charge: 24000, ins: 19200, pt: 4800 },
  { id: "li_s2", code: "36415", desc: "Blood Draw", charge: 4500, ins: 3600, pt: 900 },
  { id: "li_s3", code: "80053", desc: "Metabolic Panel", charge: 11000, ins: 8800, pt: 2200 },
  { id: "li_s4", code: "80004", desc: "Complete Blood Count", charge: 6500, ins: 5200, pt: 1300 },
  { id: "li_s5", code: "80004", desc: "Chest X-Ray (2 Views)", charge: 18000, ins: 14400, pt: 3600 },
] as const;

/** Column totals of SARAH_ROWS, in cents: charges 64000, insurance 51200, patient 12800. */
export const SARAH_TOTALS = SARAH_ROWS.reduce(
  (sum, row) => ({ charge: sum.charge + row.charge, ins: sum.ins + row.ins, pt: sum.pt + row.pt }),
  { charge: 0, ins: 0, pt: 0 },
);

const DEMO_SARAH: AnalysisResponse = {
  case_id: "demo-sarah",
  is_demo: true,
  documents: [
    {
      id: "doc_bill", kind: "bill", filename: "itemized-bill.pdf", pages: 1, extraction_quality: "complete",
      provider_name: null, insurer_name: null, document_date: "2026-10-12", service_date: "2026-09-14", claim_number: null,
      total_charges_cents: 64000, amount_due_cents: 12800, patient_responsibility_cents: null, insurance_paid_cents: 51200,
      adjustments_cents: null, expected_total_cents: null, eob_status: null,
      line_items: SARAH_ROWS.map((r) => ({
        id: r.id, description: r.desc, code: r.code, service_date: "2026-09-14", quantity: 1,
        unit_amount_cents: r.charge, line_total_cents: r.charge, page: 1,
        source_text: `09/14/2026 | ${r.code} | ${r.desc} | ${formatCents(r.charge)}`,
      })),
      extraction_warnings: ["Provider name was not visible on the bill."],
    },
  ],
  findings: [
    {
      id: "f-code-1", rule_id: "R3_POSSIBLE_DUPLICATE_LINE_ITEM", category: "possible_duplicate", status: "needs_review", severity: "low",
      title: "Same code listed for two different services",
      explanation:
        "Code 80004 appears twice on 09/14/2026: once for Complete Blood Count ($65.00) and once for Chest X-Ray (2 Views) ($180.00). Two different services rarely share one procedure code, so this is worth confirming.",
      alternative_explanations: [
        "One line may simply have a typo in the code while the charge itself is correct.",
        "The provider may print internal codes that differ from standard billing codes.",
      ],
      next_step:
        "Ask the billing office to confirm the correct procedure code for the Chest X-Ray (2 Views) line, and for a corrected itemized bill if it changes.",
      difference_cents: null,
      evidence: [
        { document_id: "doc_bill", page: 1, line_item_id: "li_s4", field: "line_items[3].code", amount_cents: 6500, source_text: "09/14/2026 | 80004 | Complete Blood Count | $65.00", verification_note: "itemized-bill.pdf, page 1" },
        { document_id: "doc_bill", page: 1, line_item_id: "li_s5", field: "line_items[4].code", amount_cents: 18000, source_text: "09/14/2026 | 80004 | Chest X-Ray (2 Views) | $180.00", verification_note: "itemized-bill.pdf, page 1" },
      ],
      missing_information: [],
    },
    {
      id: "f-eob-missing", rule_id: "R5_MISSING_INFORMATION", category: "missing_context", status: "insufficient_information", severity: "info",
      title: "Insurance comparison could not run",
      explanation:
        "The bill shows $512.00 in insurance payments, but no Explanation of Benefits (EOB) was provided, so we couldn't confirm the $128.00 amount due against what your insurer says you owe.",
      alternative_explanations: [
        "The claim may still be processing with your insurer.",
        "Your insurer may have mailed or posted the EOB separately.",
      ],
      next_step: "Add the EOB for your 09/14/2026 visit to compare the $128.00 amount due with your insurer's patient responsibility.",
      difference_cents: null,
      evidence: [
        { document_id: "doc_bill", page: 1, line_item_id: null, field: "insurance_paid_cents", amount_cents: 51200, source_text: "Insurance Payments -$512.00", verification_note: "itemized-bill.pdf, page 1" },
        { document_id: "doc_bill", page: 1, line_item_id: null, field: "amount_due_cents", amount_cents: 12800, source_text: "Amount Due $128.00", verification_note: "itemized-bill.pdf, page 1" },
      ],
      missing_information: ["Insurance EOB for service date 2026-09-14"],
    },
  ],
  limitations: [
    "Synthetic demonstration case (Sarah Johnson). The bill's math checks out: $640.00 in charges minus $512.00 in insurance payments equals the $128.00 amount due.",
  ],
  safety_disclaimer: SAFETY_DISCLAIMER,
};

const DEMO_BILL_ONLY: AnalysisResponse = {
  case_id: "demo-bill-only",
  is_demo: true,
  documents: [
    {
      id: "doc_bill", kind: "bill", filename: "sample-bill-only.pdf", pages: 1, extraction_quality: "complete",
      provider_name: "Sample Valley Clinic", insurer_name: null, document_date: "2026-10-08", service_date: "2026-10-01",
      claim_number: null, total_charges_cents: 45000, amount_due_cents: 45000, patient_responsibility_cents: null,
      insurance_paid_cents: null, adjustments_cents: null, expected_total_cents: null, eob_status: null,
      line_items: [
        { id: "li_b1", description: "Outpatient Visit - Level 3 (Established)", code: "99213", service_date: "2026-10-01", quantity: 1, unit_amount_cents: 32000, line_total_cents: 32000, page: 1, source_text: "10/01/2026 | 99213 Outpatient Visit L3 | Qty 1 | $320.00" },
        { id: "li_b2", description: "Rapid Strep Test", code: "87880", service_date: "2026-10-01", quantity: 1, unit_amount_cents: 13000, line_total_cents: 13000, page: 1, source_text: "10/01/2026 | 87880 Rapid Strep Test | Qty 1 | $130.00" },
      ],
      extraction_warnings: [],
    },
  ],
  findings: [
    {
      id: "f-missing-1", rule_id: "R5_MISSING_INFORMATION", category: "missing_context", status: "insufficient_information", severity: "info",
      title: "Insurance comparison could not run",
      explanation:
        "No Explanation of Benefits (EOB) was provided, so the statement balance could not be compared with what an insurer says you owe. Bill-only checks (line-item arithmetic and repeat charges) found nothing to flag.",
      alternative_explanations: [
        "The claim may still be processing with your insurer.",
        "You may be self-pay for this visit, in which case no EOB exists.",
      ],
      next_step: "If you have insurance, wait for or request the EOB for this visit, then run the comparison again.",
      difference_cents: null,
      evidence: [
        { document_id: "doc_bill", page: 1, line_item_id: null, field: "amount_due_cents", amount_cents: 45000, source_text: "Amount Due: $450.00", verification_note: "Verify against sample-bill-only.pdf, page 1" },
      ],
      missing_information: ["Insurance EOB for service date 2026-10-01", "Claim number"],
    },
  ],
  limitations: [
    "Synthetic demonstration case. Only bill-only checks were possible; no insurance comparison was performed.",
  ],
  safety_disclaimer: SAFETY_DISCLAIMER,
};

const BUNDLED: Partial<Record<SampleKey, AnalysisResponse>> = {
  "demo-sarah": DEMO_SARAH,
  "demo-bill-only": DEMO_BILL_ONLY,
};

export function isSampleKey(value: string | null | undefined): value is SampleKey {
  return SAMPLE_OPTIONS.some((option) => option.key === value);
}

/** A fresh copy of a sample that ships with the frontend, or null for the backend-served demo. */
export function getBundledSample(key: SampleKey): AnalysisResponse | null {
  const sample = BUNDLED[key];
  return sample ? structuredClone(sample) : null;
}

/** True for samples the backend has never seen, so POST /letters would 404 for them. */
export function isBundledSampleCase(caseId: string): boolean {
  return isSampleKey(caseId) && caseId in BUNDLED;
}

/** The fictional patient on a sample case, for document previews. */
export function samplePatientName(caseId: string): string | null {
  return isSampleKey(caseId) ? PATIENTS[caseId] : null;
}

// ---------------------------------------------------------------------------
// Offline template letter (mirrors backend/app/services/letters.py render_template)
// ---------------------------------------------------------------------------

const SAFETY_NOTE =
  "Review and verify all details against your original documents before sending. This draft has not been sent automatically.";
const PROVIDER_RECIPIENT = "[Provider Billing Department]";
const INSURER_RECIPIENT = "[Insurance Member Services]";
const NAME_PLACEHOLDER = "[Your Name]";
const ACCOUNT_PLACEHOLDER = "[Account/Claim Number]";
const TIMES: Record<number, string> = { 2: "twice", 3: "three times" };

interface LetterItem {
  issue: string;
  question: string;
}

const pageNote = (ref: EvidenceRef) => (ref.page ? ` (page ${ref.page})` : "");
const amountRef = (finding: Finding, field: string) =>
  finding.evidence.find((ref) => ref.field === field && ref.amount_cents != null);

function itemFor(finding: Finding, docs: Map<string, DocumentSummary>): LetterItem {
  if (finding.category === "insurance_comparison" && finding.status !== "insufficient_information") {
    const due = amountRef(finding, "amount_due_cents");
    const owed = amountRef(finding, "patient_responsibility_cents");
    if (due && owed && finding.difference_cents != null) {
      const bill = docs.get(due.document_id);
      const eob = docs.get(owed.document_id);
      return {
        issue:
          `My provider statement${bill?.document_date ? ` dated ${bill.document_date}` : ""} shows a current balance due of ` +
          `${formatCents(due.amount_cents)}${pageNote(due)}, whereas my${eob?.eob_status ? ` ${eob.eob_status}` : ""} Explanation of ` +
          `Benefits${eob?.insurer_name ? ` from ${eob.insurer_name}` : ""}${eob?.document_date ? ` dated ${eob.document_date}` : ""} ` +
          `lists a patient responsibility of ${formatCents(owed.amount_cents)}${pageNote(owed)}, a difference of ` +
          `${formatCents(finding.difference_cents)}.`,
        question:
          "Could you please provide an updated itemized statement showing whether all insurance payments and contractual adjustments have been applied?",
      };
    }
  }

  if (finding.category === "possible_duplicate" && finding.evidence.length) {
    const lines = finding.evidence
      .map((ref) => (ref.line_item_id ? docs.get(ref.document_id)?.line_items.find((li) => li.id === ref.line_item_id) : undefined))
      .filter((li): li is NonNullable<typeof li> => !!li);
    const first = lines[0];
    if (first && new Set(lines.map((li) => li.description)).size > 1) {
      return {
        issue:
          `My itemized bill lists code ${first.code ?? "(not shown)"} for ${lines.length} different services` +
          `${first.service_date ? ` on ${first.service_date}` : ""}: ` +
          `${lines.map((li) => `${li.description} (${formatCents(li.line_total_cents)})`).join(" and ")}${pageNote(finding.evidence[0])}.`,
        question:
          "Could you please confirm the correct procedure code for each of these services, and send me a corrected itemized bill if anything changes?",
      };
    }
    const ref = finding.evidence[0];
    if (first && ref.amount_cents != null) {
      const count = finding.evidence.length;
      return {
        issue:
          `My statement lists "${first.description}"${first.code ? ` (code ${first.code})` : ""} ${TIMES[count] ?? `${count} times`}` +
          `${first.service_date ? ` on ${first.service_date}` : ""}, at ${formatCents(ref.amount_cents)} each${pageNote(ref)}.`,
        question:
          "Could you please confirm whether these were separate services, or whether one of the entries is a duplicate that should be removed?",
      };
    }
  }

  if (finding.category === "arithmetic") {
    const total = amountRef(finding, "total_charges_cents");
    const lines = finding.evidence.filter((ref) => ref.line_item_id && ref.amount_cents != null);
    if (total && lines.length) {
      const sum = lines.reduce((acc, ref) => acc + (ref.amount_cents ?? 0), 0);
      return {
        issue: `The charge lines on my statement add up to ${formatCents(sum)}, but the statement lists total charges of ${formatCents(total.amount_cents)}${pageNote(total)}.`,
        question: "Could you please send me a complete itemized statement showing how the total charges were calculated?",
      };
    }
  }

  return {
    issue: `I have a question about the following: ${finding.title.replace(/\.$/, "")}. ${finding.explanation}`,
    question:
      finding.category === "missing_context"
        ? "Could you please confirm whether this visit was billed to my insurance, and send me an itemized statement for my records?"
        : "Could you please help me understand these amounts?",
  };
}

/** A conservative letter built only from the selected findings' own values. Never sent anywhere. */
export function buildOfflineLetter(analysis: AnalysisResponse, findings: Finding[], intent: LetterIntent): LetterResponse {
  const docs = new Map(analysis.documents.map((doc) => [doc.id, doc]));
  const bill = analysis.documents.find((doc) => doc.kind === "bill");
  const eob = analysis.documents.find((doc) => doc.kind === "eob");
  const provider = bill?.provider_name || eob?.provider_name || null;
  const claim = bill?.claim_number || eob?.claim_number || null;
  const serviceDate = bill?.service_date || eob?.service_date || null;

  const citedKinds = new Set(findings.flatMap((f) => f.evidence.map((ref) => docs.get(ref.document_id)?.kind)));
  const recipient = citedKinds.size === 1 && citedKinds.has("eob") ? INSURER_RECIPIENT : PROVIDER_RECIPIENT;

  const onlyEobMismatch = findings.every((f) => f.rule_id === "R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH");
  const topic = onlyEobMismatch ? "Account Statement vs. EOB" : provider ? `Statement from ${provider}` : "My Medical Bill";
  const prefix = intent === "clarification" ? "Clarification Request" : "Request for Billing Review";
  const subject = `${prefix}: ${topic}${claim ? ` (Claim ${claim})` : ""}`;

  let about = `my statement from ${provider || "your office"}`;
  if (serviceDate) about += ` for service date ${serviceDate}`;
  if (claim) about += ` (Claim ${claim})`;
  const opening =
    intent === "clarification"
      ? `I am writing to request clarification regarding ${about}.`
      : `I am writing to formally question the following items on ${about} and to request a review of my account.`;
  const closing =
    intent === "clarification"
      ? "Thank you for your help. Please let me know if you need any additional information from me."
      : "Please review these items and send me a written response along with an updated itemized statement. I am happy to provide any additional information you need.";

  const items = findings.map((f) => itemFor(f, docs));
  const sections =
    items.length === 1 ? [items[0].issue, items[0].question] : items.map((item, n) => `${n + 1}. ${item.issue} ${item.question}`);

  const body = [`Dear ${recipient},`, opening, ...sections, closing, `Sincerely,\n${NAME_PLACEHOLDER}\n${ACCOUNT_PLACEHOLDER}`].join("\n\n");
  return { subject, body, safety_note: SAFETY_NOTE, is_fallback: true };
}
