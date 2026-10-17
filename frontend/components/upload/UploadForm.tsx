"use client";

import { ArrowLeft, Lock, ReceiptText, TriangleAlert, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { useToast } from "@/components/layout/Toast";
import { useTrySample } from "@/components/layout/useTrySample";
import { analyzeDocuments, ApiError, isAbortError } from "@/lib/api";
import { useAppState } from "@/lib/state";
import { KIND_LABEL, type DocumentKind } from "@/lib/types";
import { AnalyzeError } from "./AnalyzeError";
import { AnalyzeProgress } from "./AnalyzeProgress";
import { DocumentUploadCard, type DropHandlers } from "./DocumentUploadCard";
import { fileExtension, UPLOAD_ACCEPT, validateUpload } from "./validateUpload";

const KINDS: DocumentKind[] = ["bill", "eob", "estimate"];
type PerKind<T> = Record<DocumentKind, T>;
type DropZone = DocumentKind | "big";

/** Stage labels advance on a timer; they describe the work, they don't measure it. */
const STAGE_DELAYS_MS = [2500, 6000];

export function UploadForm() {
  const router = useRouter();
  const toast = useToast();
  const { setAnalysis } = useAppState();
  const { trySample, isLoading: isLoadingSample } = useTrySample();

  const [files, setFiles] = useState<PerKind<File | null>>({ bill: null, eob: null, estimate: null });
  const [fileErrors, setFileErrors] = useState<PerKind<string | null>>({ bill: null, eob: null, estimate: null });
  const [over, setOver] = useState<DropZone | null>(null);
  const [stage, setStage] = useState<number | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const inputs = useRef<PerKind<HTMLInputElement | null>>({ bill: null, eob: null, estimate: null });
  const controller = useRef<AbortController | null>(null);
  const cancelledByUser = useRef(false);

  // Leaving the page cancels an in-flight analysis. A file dropped beside a drop
  // zone should not make the browser navigate away and lose the form.
  useEffect(() => {
    const swallow = (event: globalThis.DragEvent) => event.preventDefault();
    window.addEventListener("dragover", swallow);
    window.addEventListener("drop", swallow);
    return () => {
      window.removeEventListener("dragover", swallow);
      window.removeEventListener("drop", swallow);
      controller.current?.abort();
    };
  }, []);

  const setFile = async (kind: DocumentKind, file: File) => {
    const problem = await validateUpload(file);
    setFileErrors((errors) => ({ ...errors, [kind]: problem }));
    setFiles((current) => ({ ...current, [kind]: problem ? null : file }));
    if (!problem) toast(`${KIND_LABEL[kind]} added: ${file.name}`);
  };

  const removeFile = (kind: DocumentKind) => {
    setFiles((current) => ({ ...current, [kind]: null }));
    setFileErrors((errors) => ({ ...errors, [kind]: null }));
  };

  const pick = (kind: DocumentKind) => inputs.current[kind]?.click();

  const dropHandlers = (zone: DropZone, kind: DocumentKind): DropHandlers => ({
    onDragOver: (event: DragEvent<HTMLElement>) => {
      event.preventDefault();
      setOver(zone);
    },
    onDragLeave: (event: DragEvent<HTMLElement>) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOver(null);
    },
    onDrop: (event: DragEvent<HTMLElement>) => {
      event.preventDefault();
      setOver(null);
      const file = event.dataTransfer.files[0];
      if (file) void setFile(kind, file);
    },
  });

  const runAnalyze = async () => {
    const bill = files.bill;
    if (!bill) return;
    const request = new AbortController();
    controller.current = request;
    cancelledByUser.current = false;
    setError(null);
    setStage(0);
    const timers = STAGE_DELAYS_MS.map((delay, i) => setTimeout(() => setStage((s) => (s === null ? s : i + 1)), delay));
    try {
      const analysis = await analyzeDocuments(bill, files.eob, { estimateFile: files.estimate, signal: request.signal });
      setAnalysis(analysis, "upload");
      router.push("/results");
    } catch (caught) {
      setStage(null);
      if (isAbortError(caught)) {
        if (cancelledByUser.current) toast("Analysis cancelled");
        return;
      }
      setError(
        caught instanceof ApiError
          ? caught
          : new ApiError("INTERNAL_ERROR", "Something went wrong. Please try again, or use the sample case.", true, 0),
      );
    } finally {
      timers.forEach(clearTimeout);
      if (controller.current === request) controller.current = null;
    }
  };

  const cancel = () => {
    cancelledByUser.current = true;
    controller.current?.abort();
  };

  if (stage !== null) return <AnalyzeProgress stage={stage} onCancel={cancel} />;

  if (error) {
    return (
      <AnalyzeError
        error={error}
        isLoadingSample={isLoadingSample}
        onTrySample={trySample}
        onBack={() => setError(null)}
        onRetry={error.retryable ? () => void runAnalyze() : undefined}
      />
    );
  }

  const bill = files.bill;
  const openPickerOnKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    pick("bill");
  };

  return (
    <div className="page upload-shell">
      <Link className="back" href="/">
        <ArrowLeft size={15} aria-hidden="true" /> Back
      </Link>
      <div className="page-head mb-[22px]">
        <div>
          <h2>Upload Your Documents</h2>
          <p className="muted">
            Add your medical bill and, if you have it, the matching insurance Explanation of Benefits (EOB). Include a Good
            Faith Estimate if you received one.
          </p>
        </div>
      </div>

      {bill ? (
        <div className={`bigdrop filled${over === "big" ? " over" : ""}`} {...dropHandlers("big", "bill")}>
          <span className="icon-tile">
            <ReceiptText size={20} aria-hidden="true" />
          </span>
          <div className="meta">
            <div className="tiny muted font-semibold">Medical bill</div>
            <div className="name">{bill.name}</div>
            <div className="tiny muted">
              {fileExtension(bill.name).toUpperCase()} · {(bill.size / 1024).toFixed(0)} KB
            </div>
          </div>
          <button className="btn btn-secondary btn-sm" type="button" onClick={() => pick("bill")}>
            Replace
          </button>
        </div>
      ) : (
        <div
          className={`bigdrop${over === "big" ? " over" : ""}`}
          role="button"
          tabIndex={0}
          aria-label="Upload medical bill: drop a file here or press Enter to choose"
          onClick={() => pick("bill")}
          onKeyDown={openPickerOnKey}
          {...dropHandlers("big", "bill")}
        >
          <span className="drop-ring">
            <Upload size={24} aria-hidden="true" />
          </span>
          <strong>Drop your medical bill here, or click to upload</strong>
          <span className="tiny">PDF, PNG, or JPG · up to 10 MB · up to 6 pages</span>
        </div>
      )}

      <div className="doc-cards">
        {KINDS.map((kind) => (
          <DocumentUploadCard
            key={kind}
            kind={kind}
            file={files[kind]}
            error={fileErrors[kind]}
            isOver={over === kind}
            dropHandlers={dropHandlers(kind, kind)}
            onPick={() => pick(kind)}
            onRemove={() => removeFile(kind)}
          />
        ))}
      </div>

      {KINDS.map((kind) => (
        <input
          key={kind}
          ref={(element) => {
            inputs.current[kind] = element;
          }}
          className="sr-only"
          type="file"
          accept={UPLOAD_ACCEPT}
          tabIndex={-1}
          aria-label={`Choose ${KIND_LABEL[kind]} file`}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = ""; // so choosing the same file again still fires onChange
            if (file) void setFile(kind, file);
          }}
        />
      ))}

      <div className="notice mb-[18px]">
        <TriangleAlert size={16} aria-hidden="true" />
        <span>
          <strong>Demo prototype: do not upload real medical records.</strong> Use the synthetic sample files prepared for
          this hackathon. Nothing is sent until you press Analyze.
        </span>
      </div>
      <button className="btn btn-primary btn-block" style={{ padding: 15 }} type="button" disabled={!bill} onClick={() => void runAnalyze()}>
        {bill ? "Analyze Documents" : "Add a medical bill to continue"}
      </button>
      <div className="secure-note">
        <Lock size={14} aria-hidden="true" /> Files are processed for this analysis only and are not saved by Sana.
      </div>
      <div className="or-sample">
        No documents handy?{" "}
        <button type="button" onClick={() => void trySample()} disabled={isLoadingSample}>
          {isLoadingSample ? "Loading the sample…" : "Try the sample case"}
        </button>
      </div>
    </div>
  );
}
