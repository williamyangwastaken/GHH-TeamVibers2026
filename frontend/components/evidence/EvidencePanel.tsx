"use client";

import { ArrowLeft, FileText, MessageCircle, PenLine } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { SeverityTag, StatusPill } from "@/components/findings/FindingBadges";
import {
  CATEGORY_LABEL,
  fieldLabel,
  formatCents,
  isSelectableStatus,
  KIND_LABEL,
  type EvidencePanelProps,
} from "@/lib/types";
import { DocumentPreview } from "./DocumentPreview";

export type { EvidencePanelProps } from "@/lib/types";

/**
 * Evidence for one finding: what was compared (amounts with document, page and the
 * extracted source text), what is missing, innocent explanations, and what to ask,
 * next to a preview of the cited document.
 */
export function EvidencePanel({
  analysis,
  finding,
  isSelected,
  patientName,
  onToggleFinding,
  onAskAboutFinding,
  onClose,
}: EvidencePanelProps) {
  const documents = useMemo(() => new Map(analysis.documents.map((doc) => [doc.id, doc])), [analysis.documents]);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(
    finding.evidence[0]?.document_id ?? analysis.documents[0]?.id ?? null,
  );
  const viewerRef = useRef<HTMLDivElement>(null);

  const selectable = isSelectableStatus(finding.status);
  const amounts = finding.evidence.filter((ref) => ref.amount_cents != null);
  const position = analysis.findings.findIndex((f) => f.id === finding.id) + 1;
  let stepNumber = 0;
  const step = () => <span className="tl-num">{++stepNumber}</span>;

  const showSource = (documentId: string) => {
    setActiveDocumentId(documentId);
    if (window.matchMedia("(max-width: 980px)").matches) viewerRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="page">
      <button type="button" className="back" onClick={onClose}>
        <ArrowLeft size={15} aria-hidden="true" /> Back to results
      </button>
      <div className="page-head">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={finding.status} />
            <SeverityTag severity={finding.severity} />
            <span className="tiny muted">{CATEGORY_LABEL[finding.category]}</span>
          </div>
          <h2 className="mt-3">{finding.title}</h2>
          <p className="muted">
            {finding.difference_cents != null && (
              <>
                A <strong className="text-ink">{formatCents(finding.difference_cents)}</strong> difference between the figures
                below is worth verifying.{" "}
              </>
            )}
            Here&apos;s what we compared and where it came from.
          </p>
        </div>
        <div className="tiny muted self-end">
          Finding {position} of {analysis.findings.length}
        </div>
      </div>

      <div className="detail-layout">
        <div className="card">
          <div className="timeline">
            <div className="tl-step">
              {step()}
              <div>
                <h3>What we found</h3>
                <p>{finding.explanation}</p>
                {amounts.length > 0 && (
                  <div className="compare">
                    {amounts.map((ref, i) => {
                      const doc = documents.get(ref.document_id);
                      const lineIndex = ref.line_item_id && doc ? doc.line_items.findIndex((li) => li.id === ref.line_item_id) : -1;
                      const label = ref.line_item_id ? `Line item ${lineIndex + 1}` : fieldLabel(ref.field);
                      return (
                        <div className="box" key={`${ref.document_id}-${ref.field}-${i}`}>
                          <div className="lab">
                            {doc ? KIND_LABEL[doc.kind] : ref.document_id} · {label}
                          </div>
                          <div className="amt">{formatCents(ref.amount_cents)}</div>
                          <button
                            type="button"
                            className="src-chip"
                            title={doc?.filename ?? ref.document_id}
                            onClick={() => showSource(ref.document_id)}
                          >
                            <FileText size={13} aria-hidden="true" className="shrink-0" />
                            <span>
                              {doc?.filename ?? ref.document_id} · p. {ref.page ?? "?"}
                            </span>
                          </button>
                          {ref.source_text && <div className="quote">“{ref.source_text}”</div>}
                        </div>
                      );
                    })}
                  </div>
                )}
                {finding.difference_cents != null && (
                  <div className="diff-line">
                    <strong>{formatCents(finding.difference_cents)}</strong> difference to verify. This is not a determination
                    that you were overcharged.
                  </div>
                )}
              </div>
            </div>
            {finding.missing_information.length > 0 && (
              <div className="tl-step">
                {step()}
                <div>
                  <h3>What&apos;s missing</h3>
                  <ul>
                    {finding.missing_information.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
            <div className="tl-step">
              {step()}
              <div>
                <h3>Why it might be legitimate</h3>
                <ul>
                  {finding.alternative_explanations.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="tl-step">
              {step()}
              <div>
                <h3>Suggested next step</h3>
                <div className="question-box">
                  <div className="ql">
                    <MessageCircle size={14} aria-hidden="true" /> What to ask
                  </div>
                  {finding.next_step}
                </div>
              </div>
            </div>
          </div>
          <div className="detail-actions">
            {selectable ? (
              <>
                <button className="btn btn-primary" type="button" onClick={() => onAskAboutFinding(finding.id)}>
                  <PenLine size={17} aria-hidden="true" /> Ask about this {finding.category === "possible_duplicate" ? "charge" : "difference"}
                </button>
                <button className="btn btn-secondary" type="button" onClick={() => onToggleFinding(finding.id)}>
                  {isSelected ? "Remove from request" : "Add to request"}
                </button>
              </>
            ) : (
              <span className="small muted">Informational finding. It can&apos;t be included in a request letter.</span>
            )}
          </div>
        </div>

        <div className="card viewer" ref={viewerRef}>
          <DocumentPreview
            analysis={analysis}
            finding={finding}
            activeDocumentId={activeDocumentId}
            onSelectDocument={setActiveDocumentId}
            patientName={patientName}
          />
        </div>
      </div>
    </div>
  );
}
