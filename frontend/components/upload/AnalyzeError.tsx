import { TriangleAlert } from "lucide-react";
import type { ApiError, ClientErrorCode } from "@/lib/api";

const TITLE: Partial<Record<ClientErrorCode, string>> = {
  NETWORK: "Backend not reachable",
  TIMEOUT: "The backend took too long",
  FILE_TOO_LARGE: "File too large",
  INVALID_UPLOAD: "We couldn't accept that upload",
  DOCUMENT_UNREADABLE: "We couldn't read that file",
  GEMINI_UNAVAILABLE: "Document reading is temporarily unavailable",
  EXTRACTION_FAILED: "We couldn't extract the bill details",
};

interface AnalyzeErrorProps {
  error: ApiError;
  isLoadingSample: boolean;
  onTrySample: () => void;
  onBack: () => void;
  onRetry?: () => void;
}

/** Honest failure: no results, no made-up findings, and a way out. */
export function AnalyzeError({ error, isLoadingSample, onTrySample, onBack, onRetry }: AnalyzeErrorProps) {
  const title = TITLE[error.code] ?? (error.status === 429 ? "Too many requests right now" : "Something went wrong");

  return (
    <div className="card error-panel" role="alert">
      <span className="icon-tile amber mb-4">
        <TriangleAlert size={19} aria-hidden="true" />
      </span>
      <h2 className="text-[26px]">{title}</h2>
      <p className="muted">{error.message}</p>
      <p className="small muted">
        No results were generated, and we won&apos;t show you made-up findings. You can retry, adjust your files, or explore
        the synthetic sample case.
      </p>
      <div className="cta-row mt-[18px]">
        <button className="btn btn-primary" type="button" onClick={onTrySample} disabled={isLoadingSample}>
          {isLoadingSample ? "Loading sample…" : "Try Sample Case"}
        </button>
        <button className="btn btn-secondary" type="button" onClick={onBack}>
          Back to upload
        </button>
        {onRetry && (
          <button className="btn btn-ghost" type="button" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
      <p className="code mt-4">
        Error code: {error.code}
        {error.status ? ` · HTTP ${error.status}` : ""}
      </p>
    </div>
  );
}
