"use client";

import { useMemo, useState, type ReactNode } from "react";
import { HelpDialog } from "./HelpDialog";
import { ShellContext } from "./shell";
import { SignInDialog } from "./SignInDialog";
import { SiteFooter } from "./SiteFooter";
import { SiteHeader } from "./SiteHeader";
import { ToastProvider } from "./Toast";

/** Header, footer, toast and the two app-wide dialogs around every page. */
export function AppShell({ children }: { children: ReactNode }) {
  const [helpOpen, setHelpOpen] = useState(false);
  const [signInOpen, setSignInOpen] = useState(false);
  const actions = useMemo(() => ({ openHelp: () => setHelpOpen(true), openSignIn: () => setSignInOpen(true) }), []);

  return (
    <ToastProvider>
      <ShellContext.Provider value={actions}>
        <SiteHeader />
        <main id="main">{children}</main>
        <SiteFooter />
        <HelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
        <SignInDialog open={signInOpen} onClose={() => setSignInOpen(false)} />
      </ShellContext.Provider>
    </ToastProvider>
  );
}
