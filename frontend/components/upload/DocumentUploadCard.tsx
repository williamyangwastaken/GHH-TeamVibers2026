import { Check, TriangleAlert, X } from "lucide-react";
import type { DragEventHandler } from "react";
import { KindTile } from "@/components/findings/FindingBadges";
import { KIND_LABEL, type DocumentKind } from "@/lib/types";

const DESCRIPTION: Record<DocumentKind, string> = {
  bill: "The statement from your doctor or hospital showing what's due.",
  eob: "Your insurer's Explanation of Benefits for the same visit.",
  estimate: "The Good Faith Estimate you got before treatment, if any.",
};

export interface DropHandlers {
  onDragOver: DragEventHandler<HTMLElement>;
  onDragLeave: DragEventHandler<HTMLElement>;
  onDrop: DragEventHandler<HTMLElement>;
}

interface DocumentUploadCardProps {
  kind: DocumentKind;
  file: File | null;
  error: string | null;
  isOver: boolean;
  dropHandlers: DropHandlers;
  onPick: () => void;
  onRemove: () => void;
}

export function DocumentUploadCard({ kind, file, error, isOver, dropHandlers, onPick, onRemove }: DocumentUploadCardProps) {
  const required = kind === "bill";
  const label = KIND_LABEL[kind];

  return (
    <div className={`card doc-card${isOver ? " over" : ""}`} {...dropHandlers}>
      <div className="head">
        <KindTile kind={kind} size={40} iconSize={19} radius={12} />
        <span className={`tag${required ? " req" : ""}`}>{required ? "Required" : "Optional"}</span>
      </div>
      <h3>{label}</h3>
      <p>{DESCRIPTION[kind]}</p>
      {error && (
        <div className="field-error" role="alert">
          <TriangleAlert size={14} aria-hidden="true" className="shrink-0" />
          <span>{error}</span>
        </div>
      )}
      <div className="state">
        {file ? (
          <>
            <span className="check-circle text-white">
              <Check size={12} strokeWidth={3} aria-hidden="true" />
            </span>
            <span className="fname" title={file.name}>
              {file.name}
            </span>
            <button className="btn btn-ghost btn-sm" type="button" onClick={onPick} aria-label={`Replace ${label}`}>
              Replace
            </button>
            <button className="btn btn-ghost btn-sm" type="button" onClick={onRemove} aria-label={`Remove ${label}`} style={{ padding: 6 }}>
              <X size={15} aria-hidden="true" />
            </button>
          </>
        ) : (
          <>
            <span className="check-circle hollow" />
            <span className="fname muted font-medium">Not added</span>
            <button className="btn btn-soft btn-sm" type="button" onClick={onPick} aria-label={`Add ${label} file`}>
              Add file
            </button>
          </>
        )}
      </div>
    </div>
  );
}
