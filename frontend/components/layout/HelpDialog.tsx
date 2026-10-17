"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL, checkHealth } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";
import { ModalDialog } from "./ModalDialog";

type Health = "checking" | HealthResponse | null;

function statusText(health: Health): string {
  if (health === "checking") return "Checking the backend…";
  if (!health) return "Backend not connected. The sample case still works.";
  return health.demo_mode
    ? "Backend connected in demo mode. The sample case is the recommended path."
    : "Backend connected. Live uploads are available.";
}

export function HelpDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [health, setHealth] = useState<Health>("checking");

  const recheck = useCallback(async () => {
    setHealth("checking");
    setHealth(await checkHealth());
  }, []);

  useEffect(() => {
    if (open) void recheck();
  }, [open, recheck]);

  const online = health !== "checking" && health !== null;

  return (
    <ModalDialog open={open} onClose={onClose} aria-labelledby="helpTitle">
      <h3 id="helpTitle">Help</h3>
      <p className="small muted">
        Sana compares your medical bill with your insurance EOB (and Good Faith Estimate, if you have one) and flags
        differences worth asking about. It is a hackathon prototype: use synthetic documents only. It is not medical,
        insurance, or legal advice.
      </p>
      <p className="small muted">
        No documents handy? Open <strong>Upload</strong> and choose <em>Try the sample case</em>.
      </p>
      <label className="lbl mt-[14px]" htmlFor="apiBase">
        Backend API URL
      </label>
      <input className="input" id="apiBase" type="url" readOnly spellCheck={false} value={API_BASE_URL} />
      <p className="tiny muted mt-2" aria-live="polite">
        <span className={`dot${online ? " ok" : ""}`} />
        {statusText(health)}
      </p>
      <p className="tiny muted mt-1">
        Set <code>NEXT_PUBLIC_API_BASE_URL</code> in <code>frontend/.env.local</code> to point somewhere else.
      </p>
      <div className="mt-4 flex justify-end gap-2">
        <button className="btn btn-secondary btn-sm" type="button" onClick={onClose}>
          Close
        </button>
        <button className="btn btn-primary btn-sm" type="button" onClick={recheck} disabled={health === "checking"}>
          Recheck connection
        </button>
      </div>
    </ModalDialog>
  );
}
