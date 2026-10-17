"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { EvidencePanel } from "@/components/evidence/EvidencePanel";
import { FindingsDashboard } from "@/components/findings/FindingsDashboard";
import { DemoBanner } from "@/components/layout/DemoBanner";
import { NoAnalysis } from "@/components/layout/EmptyStates";
import { useToast } from "@/components/layout/Toast";
import { samplePatientName } from "@/lib/demo";
import { useAppState } from "@/lib/state";
import { isSelectableStatus } from "@/lib/types";

/** /results lists the findings; /results?finding=<id> shows one finding's evidence. */
export function ResultsView() {
  const router = useRouter();
  const toast = useToast();
  const findingId = useSearchParams().get("finding");
  const { analysis, analysisSource, selectedFindingIds, activeFindingId, toggleFinding, selectFinding, setActiveFinding } =
    useAppState();

  const finding = findingId ? analysis?.findings.find((f) => f.id === findingId) : undefined;
  const staleLink = !!analysis && !!findingId && !finding;

  // A ?finding= link from another case (e.g. after switching samples) falls back to the list.
  useEffect(() => {
    if (staleLink) router.replace("/results");
  }, [staleLink, router]);

  if (!analysis) return <NoAnalysis />;

  if (finding) {
    return (
      <EvidencePanel
        key={finding.id}
        analysis={analysis}
        finding={finding}
        isSelected={selectedFindingIds.includes(finding.id)}
        patientName={samplePatientName(analysis.case_id)}
        onToggleFinding={(id) => {
          const adding = !selectedFindingIds.includes(id);
          toggleFinding(id);
          toast(adding ? "Added to your request" : "Removed from your request");
        }}
        onAskAboutFinding={(id) => {
          selectFinding(id);
          router.push("/letter");
        }}
        onClose={() => router.push("/results")}
      />
    );
  }

  const askable = analysis.findings.filter((f) => isSelectableStatus(f.status)).length;

  return (
    <div className="page">
      <Link className="back" href="/analyze">
        <ArrowLeft size={15} aria-hidden="true" /> {analysis.is_demo ? "Upload your own documents" : "Back to upload"}
      </Link>
      <div className="page-head">
        <div>
          <div className="eyebrow">{analysis.is_demo ? "Sample case · synthetic data" : "Analysis complete"}</div>
          <h2 className="mt-2.5">{analysis.findings.length ? "Here's what we found" : "No discrepancies identified"}</h2>
          <p className="muted">
            We compared your documents and found{" "}
            {askable ? (
              <>
                <strong className="text-ink">
                  {askable} item{askable === 1 ? "" : "s"}
                </strong>{" "}
                worth asking about
              </>
            ) : (
              "nothing the supported checks could flag"
            )}
            . Review the details below and decide what to ask. <span className="null">No overpayment has been determined.</span>
          </p>
        </div>
        {analysis.is_demo && <DemoBanner analysis={analysis} source={analysisSource} />}
      </div>
      <FindingsDashboard
        key={analysis.case_id}
        analysis={analysis}
        selectedFindingIds={selectedFindingIds}
        activeFindingId={activeFindingId}
        onToggleFinding={toggleFinding}
        onInspectFinding={(id) => {
          setActiveFinding(id);
          router.push(`/results?finding=${encodeURIComponent(id)}`);
        }}
        onProceedToLetter={() => router.push("/letter")}
      />
    </div>
  );
}
