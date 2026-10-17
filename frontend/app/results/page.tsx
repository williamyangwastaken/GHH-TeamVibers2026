import type { Metadata } from "next";
import { Suspense } from "react";
import { ResultsView } from "./ResultsView";

export const metadata: Metadata = { title: "Results" };

export default function ResultsPage() {
  return (
    <div className="wrap">
      {/* ResultsView reads ?finding=<id>, which is only known in the browser. */}
      <Suspense fallback={<div className="min-h-[60vh]" />}>
        <ResultsView />
      </Suspense>
    </div>
  );
}
