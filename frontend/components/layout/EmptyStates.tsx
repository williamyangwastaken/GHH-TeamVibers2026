"use client";

import { FileText, PenLine } from "lucide-react";
import Link from "next/link";
import { useTrySample } from "./useTrySample";

function TrySampleButton() {
  const { trySample, isLoading } = useTrySample();
  return (
    <button className="btn btn-primary" type="button" onClick={trySample} disabled={isLoading}>
      {isLoading ? "Loading sample…" : "Try Sample Case"}
    </button>
  );
}

/** Results live only in memory, so a refresh (or a direct link) lands here. */
export function NoAnalysis() {
  return (
    <div className="card empty mt-12">
      <span className="icon-tile">
        <FileText size={24} aria-hidden="true" />
      </span>
      <h2 className="text-[26px]">No analysis loaded</h2>
      <p className="muted">
        Results live only in this browser tab and reset on refresh. Start with the sample case or upload documents.
      </p>
      <div className="cta-row mt-[18px] justify-center">
        <TrySampleButton />
        <Link className="btn btn-secondary" href="/analyze">
          Upload Documents
        </Link>
      </div>
    </div>
  );
}

export function SelectFindingsFirst({ hasAnalysis }: { hasAnalysis: boolean }) {
  return (
    <div className="card empty mt-12">
      <span className="icon-tile">
        <PenLine size={24} aria-hidden="true" />
      </span>
      <h2 className="text-[26px]">Select findings first</h2>
      <p className="muted">Choose one or more findings on the results page to build a request letter around.</p>
      <div className="cta-row mt-[18px] justify-center">
        {hasAnalysis ? (
          <Link className="btn btn-primary" href="/results">
            Back to Results
          </Link>
        ) : (
          <TrySampleButton />
        )}
      </div>
    </div>
  );
}
