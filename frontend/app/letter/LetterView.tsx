"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SelectFindingsFirst } from "@/components/layout/EmptyStates";
import { useToast } from "@/components/layout/Toast";
import { LetterComposer } from "@/components/letters/LetterComposer";
import { useAppState } from "@/lib/state";
import { isSelectableStatus, type LetterIntent } from "@/lib/types";

export function LetterView() {
  const router = useRouter();
  const toast = useToast();
  const { analysis, selectedFindingIds, letter, generateLetterDraft, updateLetterDraft } = useAppState();

  const selectedFindings =
    analysis?.findings.filter((f) => selectedFindingIds.includes(f.id) && isSelectableStatus(f.status)) ?? [];
  if (!analysis || selectedFindings.length === 0) return <SelectFindingsFirst hasAnalysis={!!analysis} />;

  const onGenerateDraft = async (intent: LetterIntent) => {
    const result = await generateLetterDraft(intent);
    if (!result) return;
    toast(
      result.origin === "backend-unreachable"
        ? "Backend not reachable. Using a safe template instead."
        : "Draft ready. Review and edit it before sending.",
    );
  };

  return (
    <div className="page">
      <Link className="back" href="/results">
        <ArrowLeft size={15} aria-hidden="true" /> Back to results
      </Link>
      <div className="page-head">
        <div>
          <div className="eyebrow">Guided resolution</div>
          <h2 className="mt-2.5">Prepare your request</h2>
          <p className="muted">
            Generate a draft that references only the findings you selected. Edit it freely, then send it yourself.
          </p>
        </div>
      </div>
      <LetterComposer
        key={analysis.case_id}
        analysis={analysis}
        selectedFindings={selectedFindings}
        initialIntent={letter.intent}
        draft={letter.draft}
        isGenerating={letter.isGenerating}
        error={letter.error}
        onGenerateDraft={onGenerateDraft}
        onBackToResults={() => router.push("/results")}
        onDraftChange={updateLetterDraft}
      />
    </div>
  );
}
