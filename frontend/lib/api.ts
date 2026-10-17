/**
 * Typed client for the FastAPI backend (api_contract.yaml, /api/v1).
 * Errors are thrown as ApiError carrying the contract's {code, message, retryable}.
 */

import syntheticCase from "../../fixtures/synthetic_case.json";
import type {
  AnalysisResponse,
  ErrorCode,
  ErrorResponse,
  HealthResponse,
  LetterRequest,
  LetterResponse,
} from "./types";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");
const API_PREFIX = "/api/v1";

const DEMO_TIMEOUT_MS = 4_000;
const HEALTH_TIMEOUT_MS = 2_500;
// The backend gives Gemini 30s to draft a letter before using its own template.
const LETTER_TIMEOUT_MS = 45_000;

/** Contract error codes, plus client-side failures that never reached the backend. */
export type ClientErrorCode = ErrorCode | "NETWORK" | "TIMEOUT";

export class ApiError extends Error {
  readonly code: ClientErrorCode;
  readonly retryable: boolean;
  /** HTTP status, or 0 when the request never got a response. */
  readonly status: number;

  constructor(code: ClientErrorCode, message: string, retryable: boolean, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.retryable = retryable;
    this.status = status;
  }

  /** The backend could not be reached at all (as opposed to answering with an error). */
  get isNetworkError(): boolean {
    return this.code === "NETWORK" || this.code === "TIMEOUT";
  }
}

export function isAbortError(error: unknown): boolean {
  return (error as { name?: unknown } | null)?.name === "AbortError";
}

interface RequestOptions extends Omit<RequestInit, "signal"> {
  signal?: AbortSignal;
  timeoutMs?: number;
}

async function request<T>(path: string, { signal, timeoutMs, ...init }: RequestOptions = {}): Promise<T> {
  // One controller fed by both the caller's signal (user cancel) and our timeout.
  const controller = new AbortController();
  let timedOut = false;
  const timer = timeoutMs
    ? setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs)
    : undefined;
  const forwardAbort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener("abort", forwardAbort, { once: true });

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
      ...init,
      cache: "no-store",
      credentials: "omit",
      signal: controller.signal,
    });
  } catch (error) {
    if (timedOut) {
      throw new ApiError("TIMEOUT", "The Sana backend took too long to respond. Please try again, or use the sample case.", true, 0);
    }
    if (isAbortError(error)) throw error;
    throw new ApiError(
      "NETWORK",
      "We couldn't reach the Sana backend. Make sure it's running, or try the sample case.",
      true,
      0,
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const detail = (body as Partial<ErrorResponse> | null)?.error;
    throw new ApiError(
      detail?.code ?? "INTERNAL_ERROR",
      detail?.message ?? `Request failed (${response.status}).`,
      detail?.retryable ?? response.status >= 500,
      response.status,
    );
  }
  return body as T;
}

function isAnalysisResponse(value: unknown): value is AnalysisResponse {
  const v = value as Partial<AnalysisResponse> | null;
  return (
    !!v &&
    typeof v.case_id === "string" &&
    Array.isArray(v.documents) &&
    Array.isArray(v.findings) &&
    Array.isArray(v.limitations)
  );
}

/** A fresh copy of fixtures/synthetic_case.json, so callers can't mutate the bundled module. */
export function demoFixture(): AnalysisResponse {
  return structuredClone(syntheticCase as AnalysisResponse);
}

/**
 * GET /demo: the synthetic Jordan Rivera / Sample Valley Clinic case ($640.00 vs $390.00).
 * If the backend is unreachable, slow, or answers with anything other than an
 * AnalysisResponse, returns the bundled fixtures/synthetic_case.json instead (and
 * calls `onFallback`), so the sample case always loads.
 */
export async function fetchDemoAnalysis(options: { onFallback?: (error: unknown) => void } = {}): Promise<AnalysisResponse> {
  try {
    const analysis = await request<unknown>("/demo", { timeoutMs: DEMO_TIMEOUT_MS });
    if (isAnalysisResponse(analysis)) return analysis;
    throw new ApiError("INTERNAL_ERROR", "GET /demo returned an unexpected response.", true, 200);
  } catch (error) {
    options.onFallback?.(error);
    return demoFixture();
  }
}

/**
 * POST /analyze with multipart/form-data. Field names follow api_contract.yaml and
 * the FastAPI route: `bill` (required), `eob` and `estimate` (optional).
 */
export async function analyzeDocuments(
  billFile: File,
  eobFile?: File | null,
  options: { estimateFile?: File | null; signal?: AbortSignal } = {},
): Promise<AnalysisResponse> {
  const form = new FormData();
  form.append("bill", billFile, billFile.name);
  if (eobFile) form.append("eob", eobFile, eobFile.name);
  if (options.estimateFile) form.append("estimate", options.estimateFile, options.estimateFile.name);

  const analysis = await request<unknown>("/analyze", { method: "POST", body: form, signal: options.signal });
  if (!isAnalysisResponse(analysis)) {
    throw new ApiError("INTERNAL_ERROR", "The backend returned an unexpected response. Please try again.", true, 200);
  }
  return analysis;
}

/** POST /letters: an editable draft built from findings the server already holds for `case_id`. */
export async function generateLetter(req: LetterRequest, options: { signal?: AbortSignal } = {}): Promise<LetterResponse> {
  return request<LetterResponse>("/letters", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal: options.signal,
    timeoutMs: LETTER_TIMEOUT_MS,
  });
}

/** GET /health, or null when the backend is unreachable. */
export async function checkHealth(): Promise<HealthResponse | null> {
  try {
    return await request<HealthResponse>("/health", { timeoutMs: HEALTH_TIMEOUT_MS });
  } catch {
    return null;
  }
}
