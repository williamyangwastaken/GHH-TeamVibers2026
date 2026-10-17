"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { useAppState } from "@/lib/state";

/** "Try Sample Case": load the Sample Valley Clinic demo (fetchDemoAnalysis) and open the results. */
export function useTrySample() {
  const { loadSample, isLoadingSample } = useAppState();
  const router = useRouter();

  const trySample = useCallback(async () => {
    await loadSample("demo-mismatch");
    router.push("/results");
  }, [loadSample, router]);

  return { trySample, isLoading: isLoadingSample };
}
