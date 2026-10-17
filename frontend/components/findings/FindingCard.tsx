import { ChevronRight, Info } from "lucide-react";
import { formatCents, isSelectableStatus, KIND_LABEL, type DocumentSummary, type Finding } from "@/lib/types";
import { CategoryTile, SeverityTag, StatusPill } from "./FindingBadges";

interface FindingCardProps {
  finding: Finding;
  documents: Map<string, DocumentSummary>;
  selected: boolean;
  active: boolean;
  onToggle: (findingId: string) => void;
  onInspect: (findingId: string) => void;
}

/** One finding row: select checkbox, category, status, cited pages, and the difference to verify. */
export function FindingCard({ finding, documents, selected, active, onToggle, onInspect }: FindingCardProps) {
  const selectable = isSelectableStatus(finding.status);
  const sources = [
    ...new Set(
      finding.evidence.map((ref) => {
        const doc = documents.get(ref.document_id);
        return `${doc ? KIND_LABEL[doc.kind] : ref.document_id} p. ${ref.page ?? "?"}`;
      }),
    ),
  ].join(" · ");

  return (
    // The whole row opens the evidence for mouse users; keyboard users get the title button.
    <div className={`frow${active ? " active" : ""}`} onClick={() => onInspect(finding.id)}>
      {selectable ? (
        <input
          type="checkbox"
          checked={selected}
          onClick={(event) => event.stopPropagation()}
          onChange={() => onToggle(finding.id)}
          aria-label={`Include “${finding.title}” in request`}
        />
      ) : (
        <span className="noselect" title="Informational; can't be included in a request">
          <Info size={16} aria-hidden="true" />
        </span>
      )}
      <CategoryTile category={finding.category} />
      <div className="min-w-0">
        <button type="button" className="ttl ttl-btn" aria-label={`${finding.title}: view evidence`}>
          {finding.title}
        </button>
        <div className="sub">{finding.explanation}</div>
        <div className="meta">
          <StatusPill status={finding.status} />
          <SeverityTag severity={finding.severity} />
          <span className="tiny muted">{sources}</span>
        </div>
      </div>
      <div className="amt">
        {finding.difference_cents != null ? (
          <>
            {formatCents(finding.difference_cents)}
            <small>to verify</small>
          </>
        ) : (
          <span className="null tiny">-</span>
        )}
      </div>
      <span className="chev" aria-hidden="true">
        <ChevronRight size={18} />
      </span>
    </div>
  );
}
