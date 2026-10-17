export interface FindingsDashboardProps {
  analysis: AnalysisResponse;
  selectedFindingIds: string[];
  activeFindingId: string | null;
  onToggleFinding: (findingId: string) => void;
  onInspectFinding: (findingId: string) => void;
  onProceedToLetter: () => void;
}