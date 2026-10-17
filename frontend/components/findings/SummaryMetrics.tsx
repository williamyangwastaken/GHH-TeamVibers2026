import type { Finding } from "@/lib/types";

export function SummaryMetrics({ findings }: { findings: Finding[] }) {
  const count = (status: Finding["status"]) => findings.filter((f) => f.status === status).length;
  return (
    <div className="stats">
      <div className="card stat amber">
        <span className="v">{count("needs_review")}</span>
        <span className="l">To review</span>
        <span className="s">Worth a question</span>
      </div>
      <div className="card stat teal">
        <span className="v">{count("verified_inconsistency")}</span>
        <span className="l">Verified</span>
        <span className="s">Document-level inconsistency</span>
      </div>
      <div className="card stat gray">
        <span className="v">{count("insufficient_information")}</span>
        <span className="l">Need more info</span>
        <span className="s">Checks that couldn&apos;t run</span>
      </div>
    </div>
  );
}
