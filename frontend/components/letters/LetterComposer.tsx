"use client";

import { Copy, Download, LoaderCircle, PenLine, Sparkles, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CategoryTile } from "@/components/findings/FindingBadges";
import { useToast } from "@/components/layout/Toast";
import { formatCents, type LetterComposerProps, type LetterIntent, type LetterResponse } from "@/lib/types";

export type { LetterComposerProps } from "@/lib/types";

// Drafts open with "Dear <recipient>," where the recipient is a [bracketed] placeholder.
const GREETING = /^Dear (.+?),[ \t]*$/m;
const DEFAULT_PLACEHOLDER = "[Provider Billing Department]";

const greetingName = (body: string | undefined) => (body ? GREETING.exec(body)?.[1] ?? null : null);
const isPlaceholder = (name: string) => /^\[.*\]$/.test(name);
const withGreeting = (body: string, name: string) => body.replace(GREETING, () => `Dear ${name},`);

function recipientIn(body: string | undefined): string {
  const name = greetingName(body);
  return name && !isPlaceholder(name) ? name : "";
}

const INTENTS: { value: LetterIntent; title: string; detail: string }[] = [
  { value: "clarification", title: "Ask for clarification", detail: "Neutral questions asking the office to explain the figures." },
  { value: "dispute", title: "Question a suspected discrepancy", detail: "Firmer tone; asks that the balance be noted as under review." },
];

/** Pick findings' intent, generate a grounded draft, edit it, then copy or download it. Nothing is ever sent. */
export function LetterComposer({
  analysis,
  selectedFindings,
  initialIntent,
  draft,
  isGenerating,
  error,
  onGenerateDraft,
  onBackToResults,
  onDraftChange,
}: LetterComposerProps) {
  const toast = useToast();
  const [intent, setIntent] = useState<LetterIntent>(initialIntent);
  const [subject, setSubject] = useState(draft?.subject ?? "");
  const [body, setBody] = useState(draft?.body ?? "");
  const [recipient, setRecipient] = useState(() => recipientIn(draft?.body));
  const seenDraft = useRef(draft);
  const emitted = useRef<LetterResponse | null>(null);
  const placeholder = useRef(greetingName(draft?.body) ?? DEFAULT_PLACEHOLDER);

  const emit = (next: LetterResponse) => {
    emitted.current = next;
    onDraftChange?.(next);
  };

  // A new draft from outside (a fresh generation): show it, with the "Send to" name filled in.
  useEffect(() => {
    if (draft === seenDraft.current) return;
    seenDraft.current = draft;
    if (!draft) {
      setSubject("");
      setBody("");
      return;
    }
    if (draft === emitted.current) return; // our own edit, echoed back by the parent
    const found = greetingName(draft.body);
    if (found && isPlaceholder(found)) placeholder.current = found;
    const name = recipient.trim();
    const next = name && found && found !== name ? { ...draft, body: withGreeting(draft.body, name) } : draft;
    setSubject(next.subject);
    setBody(next.body);
    if (next !== draft) emit(next);
    // `recipient` is read only when a new draft arrives; typing in it is handled by onRecipientChange.
  }, [draft]);

  const onSubjectChange = (value: string) => {
    setSubject(value);
    if (draft) emit({ ...draft, subject: value, body });
  };

  const onBodyChange = (value: string) => {
    setBody(value);
    if (draft) emit({ ...draft, subject, body: value });
  };

  const onRecipientChange = (value: string) => {
    setRecipient(value);
    if (!draft) return;
    const nextBody = withGreeting(body, value.trim() || placeholder.current);
    if (nextBody === body) return;
    setBody(nextBody);
    emit({ ...draft, subject, body: nextBody });
  };

  const letterText = () => `Subject: ${subject}\n\n${body}`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(letterText());
      toast("Copied. Remember to review before sending.");
    } catch {
      // Clipboard API unavailable (e.g. insecure context): fall back to a hidden textarea.
      const area = document.createElement("textarea");
      area.value = letterText();
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      const copied = document.execCommand("copy");
      area.remove();
      toast(copied ? "Copied. Remember to review before sending." : "Copy failed. Select the text and copy it manually.");
    }
  };

  const download = () => {
    const blob = new Blob([`${letterText()}\n`], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `sana-request-${analysis.case_id}.txt`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Downloaded TXT file.");
  };

  return (
    <div className="letter-grid">
      <div className="card side">
        <div>
          <span className="lbl-cap">Selected findings ({selectedFindings.length})</span>
          <div className="grid gap-2">
            {selectedFindings.map((finding) => (
              <div key={finding.id} className="sel-item">
                <span className="flex items-center gap-2.5">
                  <CategoryTile category={finding.category} size={30} />
                  {finding.title}
                </span>
                {finding.difference_cents != null && <strong>{formatCents(finding.difference_cents)}</strong>}
              </div>
            ))}
          </div>
        </div>

        <fieldset className="m-0 p-0" style={{ border: 0 }}>
          <legend className="lbl-cap">What do you want to do?</legend>
          <div className="grid gap-2">
            {INTENTS.map((option) => (
              <label key={option.value} className="radio-card">
                <input
                  type="radio"
                  name="intent"
                  value={option.value}
                  checked={intent === option.value}
                  onChange={() => setIntent(option.value)}
                />
                <span>
                  <strong>{option.title}</strong>
                  <div className="d">{option.detail}</div>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <div>
          <label className="lbl" htmlFor="letter-recipient">
            Send to
          </label>
          <input
            className="input"
            id="letter-recipient"
            value={recipient}
            placeholder="Provider billing department"
            onChange={(event) => onRecipientChange(event.target.value)}
          />
          <p className="tiny muted mb-0 mt-[7px]">
            Sana doesn&apos;t look up contact details. Use the address or phone number printed on your statement.
          </p>
        </div>

        <button
          className="btn btn-primary"
          type="button"
          disabled={isGenerating || selectedFindings.length === 0}
          onClick={() => void onGenerateDraft(intent)}
        >
          {isGenerating ? (
            <LoaderCircle size={17} className="animate-spin" aria-hidden="true" />
          ) : (
            <Sparkles size={17} aria-hidden="true" />
          )}
          {isGenerating ? "Drafting…" : draft ? "Regenerate Draft" : "Generate Draft"}
        </button>
      </div>

      <div className="card editor">
        {error && (
          <div className="notice error mx-5 my-4" role="alert">
            <TriangleAlert size={16} aria-hidden="true" />
            <span>
              <strong>We couldn&apos;t draft the letter.</strong> {error}
            </span>
          </div>
        )}
        {draft ? (
          <>
            <div className="bar">
              <h3>Your draft</h3>
              {draft.is_fallback ? (
                <span className="tag" title="Built from a fixed template using only the selected findings' values">
                  Template draft
                </span>
              ) : (
                <span className="tag req">AI draft · grounded</span>
              )}
            </div>
            <div className="notice mx-5 my-4">
              <TriangleAlert size={16} aria-hidden="true" />
              <span>
                <strong>{draft.safety_note}</strong> Replace the [bracketed] placeholders with your own information.
              </span>
            </div>
            <div className="letter-stage">
              <div className="sheet">
                <div className="subject">
                  <label htmlFor="letter-subject" className="tiny muted font-semibold">
                    Subject
                  </label>
                  <input id="letter-subject" value={subject} onChange={(event) => onSubjectChange(event.target.value)} />
                </div>
                <label className="sr-only" htmlFor="letter-body">
                  Letter body
                </label>
                <textarea id="letter-body" spellCheck value={body} onChange={(event) => onBodyChange(event.target.value)} />
              </div>
            </div>
            <div className="actions">
              <button className="btn btn-primary btn-sm" type="button" onClick={copy}>
                <Copy size={15} aria-hidden="true" /> Copy to clipboard
              </button>
              <button className="btn btn-secondary btn-sm" type="button" onClick={download}>
                <Download size={15} aria-hidden="true" /> Download TXT
              </button>
              <span className="flex-1" />
              <button className="btn btn-ghost btn-sm" type="button" onClick={onBackToResults}>
                Back to results
              </button>
            </div>
          </>
        ) : (
          <div className="empty" style={{ padding: "72px 24px" }}>
            <span className="icon-tile">
              <PenLine size={24} aria-hidden="true" />
            </span>
            <h3>{isGenerating ? "Drafting your letter…" : "No draft yet"}</h3>
            <p className="muted small">
              Pick an intent and press <strong>Generate Draft</strong>. The letter will only mention the amounts, dates and
              items from your selected findings.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
