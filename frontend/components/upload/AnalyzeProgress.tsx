import { Check, Search } from "lucide-react";

export const ANALYZE_STAGES = ["Reading your documents", "Checking the numbers", "Preparing your results"];

/** Descriptive stages only: they advance on a timer, never a fake percentage. */
export function AnalyzeProgress({ stage, onCancel }: { stage: number; onCancel: () => void }) {
  return (
    <div className="card progress-card" role="status" aria-live="polite">
      <span className="icon-tile mb-4">
        <Search size={19} aria-hidden="true" />
      </span>
      <h2 className="text-[26px]">Analyzing your documents</h2>
      <p className="muted small mb-[18px] mt-2">
        This usually takes under a minute. We don&apos;t show a percentage because we can&apos;t measure it honestly.
      </p>
      {ANALYZE_STAGES.map((label, i) => (
        <div key={label} className={`stage${i < stage ? " done" : i === stage ? " active" : ""}`}>
          <span className="ic text-white">{i < stage && <Check size={13} strokeWidth={3} aria-hidden="true" />}</span>
          {label}
        </div>
      ))}
      <div className="mt-5">
        <button className="btn btn-secondary btn-sm" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
