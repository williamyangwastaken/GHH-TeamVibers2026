"use client";

import { useEffect, useState, type FormEvent } from "react";
import { DEMO_USER, useAppState, type DemoUser } from "@/lib/state";
import { ModalDialog } from "./ModalDialog";
import { useToast } from "./Toast";

/** Prototype sign-in: the user lives in React memory only and the password is never kept or sent. */
export function SignInDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { signIn } = useAppState();
  const toast = useToast();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (!open) return;
    setMode("signin");
    setName("");
    setEmail("");
    setPassword("");
  }, [open]);

  const finish = (user: DemoUser) => {
    signIn(user);
    setPassword("");
    onClose();
    toast(`Signed in as ${user.name}`);
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const address = email.trim();
    const fromEmail = address
      .split("@")[0]
      .replace(/[._-]+/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
    finish({ name: mode === "signup" && name.trim() ? name.trim() : fromEmail, email: address, isDemo: false });
  };

  const signingUp = mode === "signup";

  return (
    <ModalDialog open={open} onClose={onClose} className="auth" aria-labelledby="authTitle">
      <button className="close" type="button" aria-label="Close" onClick={onClose}>
        ×
      </button>
      <form onSubmit={onSubmit}>
        <span className="wordmark">Sana</span>
        <h3 id="authTitle">{signingUp ? "Create your account" : "Welcome back"}</h3>
        <p className="sub">{signingUp ? "Keep your bills and requests in one place." : "Sign in to see your bills and requests."}</p>
        {signingUp && (
          <div className="field">
            <label className="lbl" htmlFor="authName">
              Full name
            </label>
            <input className="input" id="authName" autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        )}
        <div className="field">
          <label className="lbl" htmlFor="authEmail">
            Email
          </label>
          <input
            className="input"
            id="authEmail"
            type="email"
            required
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label className="lbl" htmlFor="authPassword">
            Password
          </label>
          <input
            className="input"
            id="authPassword"
            type="password"
            required
            minLength={6}
            autoComplete={signingUp ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button className="btn btn-primary btn-block" type="submit">
          {signingUp ? "Create account" : "Sign in"}
        </button>
        <div className="divider">or</div>
        <button className="btn btn-secondary btn-block" type="button" onClick={() => finish(DEMO_USER)}>
          Sign in as Jordan Rivera (Demo)
        </button>
        <p className="switch">
          {signingUp ? "Already have an account? " : "New to Sana? "}
          <button type="button" onClick={() => setMode(signingUp ? "signin" : "signup")}>
            {signingUp ? "Sign in" : "Create an account"}
          </button>
        </p>
        <p className="proto">Prototype sign-in. Nothing is stored or sent.</p>
      </form>
    </ModalDialog>
  );
}
