"use client";

import { Check } from "lucide-react";
import { isSampleKey, SAMPLE_OPTIONS } from "@/lib/demo";
import { useAppState, type AnalysisSource } from "@/lib/state";
import type { AnalysisResponse } from "@/lib/types";

const SOURCE_NOTE: Partial<Record<AnalysisSource, string>> = {
  "api-demo": "From the backend demo endpoint.",
  "fixture-demo": "Backend not reachable, so the bundled copy is shown.",
  "bundled-sample": "Bundled fixture, no backend needed.",
};

/** "Precomputed sample" card with the sample-case picker, shown on results for demo analyses. */
export function DemoBanner({ analysis, source }: { analysis: AnalysisResponse; source: AnalysisSource | null }) {
  const { loadSample, isLoadingSample } = useAppState();
  const sampleKey = isSampleKey(analysis.case_id) ? analysis.case_id : "";

  return (
    <div className="card sample-card">
      <span className="check-circle mt-0.5 text-white">
        <Check size={12} strokeWidth={3} aria-hidden="true" />
      </span>
      <div className="flex-1">
        <div className="text-[14px] font-bold">Precomputed sample</div>
        <div className="tiny muted">
          {(source && SOURCE_NOTE[source]) ?? "Synthetic data."} No live scan was run.
        </div>
        <label className="sr-only" htmlFor="sampleSel">
          Choose sample case
        </label>
        <select
          id="sampleSel"
          value={sampleKey}
          disabled={isLoadingSample}
          onChange={(event) => {
            if (isSampleKey(event.target.value)) void loadSample(event.target.value);
          }}
        >
          {!sampleKey && <option value="">Choose a sample</option>}
          {SAMPLE_OPTIONS.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
