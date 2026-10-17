"use client";

import { Info } from "lucide-react";
import { useId } from "react";
import { formatCents, formatDate, KIND_LABEL, type AnalysisResponse, type DocumentSummary, type Finding } from "@/lib/types";

type MoneyField =
  | "total_charges_cents"
  | "adjustments_cents"
  | "insurance_paid_cents"
  | "patient_responsibility_cents"
  | "amount_due_cents"
  | "expected_total_cents";

const EOB_TOTALS: [MoneyField, string][] = [
  ["total_charges_cents", "Total billed"],
  ["adjustments_cents", "Plan adjustments"],
  ["insurance_paid_cents", "Plan paid"],
  ["patient_responsibility_cents", "Total patient responsibility"],
];

const BILL_TOTALS: [MoneyField, string][] = [
  ["total_charges_cents", "Total charges"],
  ["insurance_paid_cents", "Insurance payments"],
  ["adjustments_cents", "Adjustments"],
  ["amount_due_cents", "Current account balance due"],
  ["expected_total_cents", "Estimated total"],
];

const PAPER_TITLE: Record<DocumentSummary["kind"], string> = {
  bill: "Hospital Bill",
  eob: "Explanation of Benefits",
  estimate: "Good Faith Estimate",
};

interface DocumentPreviewProps {
  analysis: AnalysisResponse;
  finding: Finding;
  activeDocumentId: string | null;
  onSelectDocument: (documentId: string) => void;
  patientName?: string | null;
}

/**
 * A page rebuilt from the values extracted from one document, with the rows this
 * finding cites highlighted. It is not an image of the original file.
 */
export function DocumentPreview({ analysis, finding, activeDocumentId, onSelectDocument, patientName }: DocumentPreviewProps) {
  const baseId = useId();
  const doc = analysis.documents.find((d) => d.id === activeDocumentId) ?? analysis.documents[0];
  if (!doc) return null;

  const cited = finding.evidence.filter((ref) => ref.document_id === doc.id);
  const citedLines = new Set(cited.map((ref) => ref.line_item_id).filter(Boolean));
  const citedFields = new Set(cited.filter((ref) => !ref.line_item_id).map((ref) => ref.field));
  const isEob = doc.kind === "eob";
  const totals = (isEob ? EOB_TOTALS : BILL_TOTALS).filter(([field]) => doc[field] != null);
  const panelId = `${baseId}-panel`;

  return (
    <>
      <div className="vh">
        <h3>Documents</h3>
        <div className="seg" role="tablist" aria-label="Documents">
          {analysis.documents.map((d) => (
            <button
              key={d.id}
              type="button"
              role="tab"
              aria-selected={d.id === doc.id}
              aria-controls={panelId}
              onClick={() => onSelectDocument(d.id)}
            >
              {KIND_LABEL[d.kind]}
              {finding.evidence.some((ref) => ref.document_id === d.id) ? " •" : ""}
            </button>
          ))}
        </div>
      </div>
      <div className="stage-bg">
        <div className="paper" role="tabpanel" id={panelId} aria-label={`${doc.filename} preview`}>
          <div className="ph">
            <div>
              <strong>{PAPER_TITLE[doc.kind]}</strong>
              <div className="mt-0.5 text-[#6b736f]">
                {isEob ? doc.insurer_name || "Insurer" : doc.provider_name || "Provider"}
                {isEob ? " · This is not a bill" : ""}
              </div>
            </div>
            <div className="text-right text-[11px] text-[#6b736f]">
              <span className="synthetic">{analysis.is_demo ? "SYNTHETIC SAMPLE" : "REBUILT PREVIEW"}</span>
              <div>{doc.claim_number ? `Claim ${doc.claim_number}` : ""}</div>
              <div>{doc.document_date ? `Issued ${formatDate(doc.document_date)}` : ""}</div>
              {doc.eob_status && <div>Status: {doc.eob_status}</div>}
            </div>
          </div>
          <div className="meta-line">
            {patientName ? `Patient: ${patientName} (fictional) · ` : ""}Provider: {doc.provider_name || "-"} · Date of service:{" "}
            {formatDate(doc.service_date) || "-"}
          </div>
          <div className="filler" style={{ width: "62%" }} />
          <div className="filler" style={{ width: "44%", marginBottom: 12 }} />
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Code</th>
                <th>Description</th>
                <th className="r">Qty</th>
                <th className="r">Amount</th>
              </tr>
            </thead>
            <tbody>
              {doc.line_items.map((li) => (
                <tr key={li.id} className={citedLines.has(li.id) ? "hl" : undefined}>
                  <td>{formatDate(li.service_date) || "-"}</td>
                  <td>{li.code || "-"}</td>
                  <td>{li.description}</td>
                  <td className="r">{li.quantity ?? "-"}</td>
                  <td className="r">{li.line_total_cents != null ? formatCents(li.line_total_cents) : <span className="null">-</span>}</td>
                </tr>
              ))}
              {totals.map(([field, label]) => {
                const classes = [
                  citedFields.has(field) ? "hl" : "",
                  field === "amount_due_cents" || field === "patient_responsibility_cents" ? "total" : "",
                ].filter(Boolean);
                return (
                  <tr key={field} className={classes.join(" ") || undefined}>
                    <td colSpan={4}>{label}</td>
                    <td className="r">{formatCents(doc[field])}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="filler" style={{ width: "80%", marginTop: 14 }} />
          <div className="filler" style={{ width: "52%" }} />
          <div className="pg">
            {doc.filename} · page 1 of {doc.pages}
          </div>
        </div>
      </div>
      <div className="vf">
        <Info size={14} aria-hidden="true" className="shrink-0" />
        <span>
          Preview rebuilt from the values read from this document; highlighted rows are cited by this finding. Always check
          the original file.
        </span>
      </div>
    </>
  );
}
