"use client";

import { ArrowRight, Check, Info, PenLine, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { isSelectableStatus, KIND_LABEL, type DocumentKind, type FindingsDashboardProps } from "@/lib/types";
import { DocumentsGlance } from "./DocumentsGlance";
import { FindingCard } from "./FindingCard";
import { KindTile } from "./FindingBadges";
import { FindingFilters, type FindingFilter } from "./FindingFilters";
import { SummaryMetrics } from "./SummaryMetrics";

export type { FindingsDashboardProps } from "@/lib/types";

const OPTIONAL_KINDS: DocumentKind[] = ["eob", "estimate"];

function missingDocumentLabel(kind: DocumentKind, limitations: string[]): string {
  const label = KIND_LABEL[kind];
  const backendLabel = kind === "eob" ? "EOB" : label;
  // The API records extraction failures for optional files in limitations, but
  // leaves them out of documents. Don't misreport an uploaded file as absent.
  return limitations.some((item) => item.startsWith(`${backendLabel}:`))
    ? "Uploaded, but analysis failed"
    : "Not provided";
}

export function FindingsDashboard({
  analysis,
  selectedFindingIds,
  activeFindingId,
  onToggleFinding,
  onInspectFinding,
  onProceedToLetter,
}: FindingsDashboardProps) {
  const [filter, setFilter] = useState<FindingFilter>("all");
  const documents = useMemo(() => new Map(analysis.documents.map((doc) => [doc.id, doc])), [analysis.documents]);

  const findings = analysis.findings;
  const categories = [...new Set(findings.map((f) => f.category))];
  const visible = filter === "all" ? findings : findings.filter((f) => f.category === filter);
  const selected = new Set(selectedFindingIds);
  const selectedCount = findings.filter((f) => selected.has(f.id)).length;
  const anySelectable = findings.some((f) => isSelectableStatus(f.status));

  return (
    <>
      <div className="results-layout">
        <div>
          <SummaryMetrics findings={findings} />

          <section className="card list-card" aria-labelledby="findingsTitle">
            <div className="lc-head">
              <h3 id="findingsTitle">Top Findings</h3>
              {categories.length > 1 && (
                <FindingFilters categories={categories} total={findings.length} value={filter} onChange={setFilter} />
              )}
            </div>
            {findings.length ? (
              visible.map((finding) => (
                <FindingCard
                  key={finding.id}
                  finding={finding}
                  documents={documents}
                  selected={selected.has(finding.id)}
                  active={finding.id === activeFindingId}
                  onToggle={onToggleFinding}
                  onInspect={onInspectFinding}
                />
              ))
            ) : (
              <div className="empty" style={{ borderTop: "1px solid var(--line)" }}>
                <span className="icon-tile">
                  <ShieldCheck size={24} aria-hidden="true" />
                </span>
                <h3>Nothing flagged</h3>
                <p className="muted small">
                  The supported checks didn&apos;t find differences to question. That isn&apos;t a guarantee the bill is
                  correct. It means these specific comparisons lined up.
                </p>
              </div>
            )}
            {anySelectable && (
              <div className="tiny muted bg-surface-2 px-5 py-3" style={{ borderTop: "1px solid var(--line)" }}>
                Tick the findings you want to include in a request letter. Click a row to see its evidence.
              </div>
            )}
          </section>

          <DocumentsGlance analysis={analysis} />
        </div>

        <aside className="side-stack">
          <div className="card side-card">
            <h3>Your Documents</h3>
            {analysis.documents.map((doc) => (
              <div key={doc.id} className="doc-row">
                <KindTile kind={doc.kind} />
                <div className="meta">
                  <div className="name">{KIND_LABEL[doc.kind]}</div>
                  <div className="fn" title={doc.filename}>
                    {doc.filename} · {doc.pages} page{doc.pages === 1 ? "" : "s"}
                  </div>
                </div>
                {doc.extraction_quality === "complete" ? (
                  <span className="check-circle text-white" title="Read completely">
                    <Check size={12} strokeWidth={3} aria-hidden="true" />
                  </span>
                ) : (
                  <span className="tag medium">{doc.extraction_quality}</span>
                )}
              </div>
            ))}
            {OPTIONAL_KINDS.filter((kind) => !analysis.documents.some((doc) => doc.kind === kind)).map((kind) => (
              <div key={kind} className="doc-row">
                <KindTile kind={kind} tone="gray" />
                <div className="meta">
                  <div className="name text-ink-3">{KIND_LABEL[kind]}</div>
                  <div className="fn">{missingDocumentLabel(kind, analysis.limitations)}</div>
                </div>
                <span className="check-circle hollow" />
              </div>
            ))}
          </div>

          {anySelectable && (
            <div className="card ask-card">
              <span className="icon-tile mb-3 bg-white">
                <PenLine size={19} aria-hidden="true" />
              </span>
              <h3>Ready to ask?</h3>
              <p>
                {selectedCount
                  ? `${selectedCount} finding${selectedCount === 1 ? "" : "s"} selected. We'll turn ${selectedCount === 1 ? "it" : "them"} into an editable letter for the billing office.`
                  : "Select one or more findings, and we'll turn them into an editable letter for the billing office."}
              </p>
              <button className="btn btn-primary btn-block" type="button" disabled={!selectedCount} onClick={onProceedToLetter}>
                Prepare a Request
              </button>
            </div>
          )}

          <div className="card side-card bg-surface-2 shadow-none">
            <h3 className="flex items-center gap-2">
              <Info size={16} aria-hidden="true" /> Limitations
            </h3>
            <ul className="m-0 pl-[18px] text-[13px] text-ink-2">
              {analysis.limitations.map((limitation, i) => (
                <li key={`limitation-${i}`}>{limitation}</li>
              ))}
              {analysis.documents.flatMap((doc) =>
                doc.extraction_warnings.map((warning, i) => (
                  <li key={`${doc.id}-warning-${i}`}>
                    {KIND_LABEL[doc.kind]}: {warning}
                  </li>
                )),
              )}
            </ul>
            <p className="tiny muted mb-0 mt-2.5">{analysis.safety_disclaimer}</p>
          </div>
        </aside>
      </div>

      {anySelectable && (
        <div className="mobile-cta">
          <div className="card">
            <span className="small">
              <strong>{selectedCount}</strong> selected
            </span>
            <button className="btn btn-primary btn-sm" type="button" disabled={!selectedCount} onClick={onProceedToLetter}>
              Prepare a Request <ArrowRight size={15} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
