export interface LetterComposerProps {
  analysis: AnalysisResponse;
  selectedFindings: Finding[];
  initialIntent: LetterIntent;
  draft: LetterResponse | null;
  isGenerating: boolean;
  error: string | null;
  onGenerateDraft: (intent: LetterIntent) => Promise<void>;
  onBackToResults: () => void;
}