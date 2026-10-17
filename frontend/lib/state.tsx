"use client";

/**
 * App state held in React memory only: no localStorage, so a refresh starts over
 * and uploaded documents or results never persist in the browser.
 */

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiError, fetchDemoAnalysis, generateLetter } from "./api";
import { buildOfflineLetter, getBundledSample, isBundledSampleCase, type SampleKey } from "./demo";
import { isSelectableStatus, type AnalysisResponse, type LetterIntent, type LetterResponse } from "./types";

/** Where the current analysis came from; drives the "Precomputed sample" banner copy. */
export type AnalysisSource = "api-demo" | "fixture-demo" | "bundled-sample" | "upload";

export interface DemoUser {
  name: string;
  email: string;
  isDemo: boolean;
}

/** Simulated sign-in only: nothing is sent to a server or stored. */
export const DEMO_USER: DemoUser = { name: "Jordan Rivera (Demo)", email: "jordan@example.com", isDemo: true };

export interface LetterState {
  intent: LetterIntent;
  draft: LetterResponse | null;
  isGenerating: boolean;
  error: string | null;
}

/** How a draft was produced, so the UI can say so honestly. */
export type DraftOrigin = "api" | "bundled-sample" | "backend-unreachable";

const INITIAL_LETTER: LetterState = { intent: "clarification", draft: null, isGenerating: false, error: null };

interface AppStateValue {
  analysis: AnalysisResponse | null;
  analysisSource: AnalysisSource | null;
  selectedFindingIds: string[];
  activeFindingId: string | null;
  user: DemoUser | null;
  letter: LetterState;
  isLoadingSample: boolean;

  /** Replace the current analysis; resets the selection (to `selectedFindingIds`, if given) and any letter draft. */
  setAnalysis: (analysis: AnalysisResponse, source: AnalysisSource, options?: { selectedFindingIds?: string[] }) => void;
  /** Load a sample case. The default calls fetchDemoAnalysis (GET /api/v1/demo, fixture fallback). */
  loadSample: (key?: SampleKey) => Promise<AnalysisResponse>;
  toggleFinding: (findingId: string) => void;
  /** Add a finding to the selection if it is not already there. */
  selectFinding: (findingId: string) => void;
  setActiveFinding: (findingId: string | null) => void;
  signIn: (user: DemoUser) => void;
  signOut: () => void;
  /** Draft a letter for the selected findings; returns null if it failed (see letter.error). */
  generateLetterDraft: (intent: LetterIntent) => Promise<{ draft: LetterResponse; origin: DraftOrigin } | null>;
  updateLetterDraft: (draft: LetterResponse) => void;
}

const AppStateContext = createContext<AppStateValue | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [analysis, setAnalysisValue] = useState<AnalysisResponse | null>(null);
  const [analysisSource, setAnalysisSource] = useState<AnalysisSource | null>(null);
  const [selectedFindingIds, setSelectedFindingIds] = useState<string[]>([]);
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);
  const [user, setUser] = useState<DemoUser | null>(null);
  const [letter, setLetter] = useState<LetterState>(INITIAL_LETTER);
  const [isLoadingSample, setIsLoadingSample] = useState(false);

  // Bumped whenever the analysis changes, so late async results for an old case are dropped.
  const analysisVersion = useRef(0);
  const sampleRequest = useRef(0);

  const setAnalysis = useCallback(
    (next: AnalysisResponse, source: AnalysisSource, options: { selectedFindingIds?: string[] } = {}) => {
      const wanted = new Set(options.selectedFindingIds ?? []);
      analysisVersion.current += 1;
      setAnalysisValue(next);
      setAnalysisSource(source);
      setSelectedFindingIds(next.findings.filter((f) => wanted.has(f.id) && isSelectableStatus(f.status)).map((f) => f.id));
      setActiveFindingId(null);
      setLetter(INITIAL_LETTER);
    },
    [],
  );

  const loadSample = useCallback(
    async (key: SampleKey = "demo-mismatch") => {
      const request = ++sampleRequest.current;
      const bundled = getBundledSample(key);
      if (bundled) {
        setIsLoadingSample(false);
        setAnalysis(bundled, "bundled-sample");
        return bundled;
      }
      setIsLoadingSample(true);
      try {
        let fromFixture = false;
        const demo = await fetchDemoAnalysis({ onFallback: () => (fromFixture = true) });
        if (request === sampleRequest.current) setAnalysis(demo, fromFixture ? "fixture-demo" : "api-demo");
        return demo;
      } finally {
        if (request === sampleRequest.current) setIsLoadingSample(false);
      }
    },
    [setAnalysis],
  );

  const isSelectable = useCallback(
    (findingId: string) => {
      const finding = analysis?.findings.find((f) => f.id === findingId);
      return !!finding && isSelectableStatus(finding.status);
    },
    [analysis],
  );

  const toggleFinding = useCallback(
    (findingId: string) => {
      if (!isSelectable(findingId)) return;
      setSelectedFindingIds((ids) => (ids.includes(findingId) ? ids.filter((id) => id !== findingId) : [...ids, findingId]));
    },
    [isSelectable],
  );

  const selectFinding = useCallback(
    (findingId: string) => {
      if (!isSelectable(findingId)) return;
      setSelectedFindingIds((ids) => (ids.includes(findingId) ? ids : [...ids, findingId]));
    },
    [isSelectable],
  );

  const signIn = useCallback((next: DemoUser) => setUser(next), []);
  const signOut = useCallback(() => setUser(null), []);

  const generateLetterDraft = useCallback(
    async (intent: LetterIntent) => {
      if (!analysis) return null;
      const findings = analysis.findings.filter((f) => selectedFindingIds.includes(f.id) && isSelectableStatus(f.status));
      if (!findings.length) {
        setLetter((l) => ({ ...l, intent, error: "Select at least one finding to include in the letter." }));
        return null;
      }

      const version = analysisVersion.current;
      setLetter((l) => ({ ...l, intent, isGenerating: true, error: null }));
      let result: { draft: LetterResponse; origin: DraftOrigin };
      try {
        if (isBundledSampleCase(analysis.case_id)) {
          // This sample ships with the frontend; the backend has never seen its case_id.
          result = { draft: buildOfflineLetter(analysis, findings, intent), origin: "bundled-sample" };
        } else {
          try {
            const draft = await generateLetter({ case_id: analysis.case_id, finding_ids: findings.map((f) => f.id), intent });
            result = { draft, origin: "api" };
          } catch (error) {
            if (!(error instanceof ApiError) || !error.isNetworkError) throw error;
            result = { draft: buildOfflineLetter(analysis, findings, intent), origin: "backend-unreachable" };
          }
        }
      } catch (error) {
        if (version === analysisVersion.current) {
          const message =
            error instanceof ApiError ? error.message : "Something went wrong while drafting the letter. Please try again.";
          setLetter((l) => ({ ...l, isGenerating: false, error: message }));
        }
        return null;
      }

      if (version !== analysisVersion.current) return null;
      setLetter({ intent, draft: result.draft, isGenerating: false, error: null });
      return result;
    },
    [analysis, selectedFindingIds],
  );

  const updateLetterDraft = useCallback((draft: LetterResponse) => setLetter((l) => ({ ...l, draft })), []);

  const value = useMemo<AppStateValue>(
    () => ({
      analysis,
      analysisSource,
      selectedFindingIds,
      activeFindingId,
      user,
      letter,
      isLoadingSample,
      setAnalysis,
      loadSample,
      toggleFinding,
      selectFinding,
      setActiveFinding: setActiveFindingId,
      signIn,
      signOut,
      generateLetterDraft,
      updateLetterDraft,
    }),
    [
      analysis,
      analysisSource,
      selectedFindingIds,
      activeFindingId,
      user,
      letter,
      isLoadingSample,
      setAnalysis,
      loadSample,
      toggleFinding,
      selectFinding,
      signIn,
      signOut,
      generateLetterDraft,
      updateLetterDraft,
    ],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateValue {
  const value = useContext(AppStateContext);
  if (!value) throw new Error("useAppState must be used inside <AppStateProvider>.");
  return value;
}
