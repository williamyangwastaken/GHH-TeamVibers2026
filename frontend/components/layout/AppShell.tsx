"use client";

import { useMemo, useState, type ReactNode } from "react";
import { ShellContext } from "./shell";
import { SignInDialog } from "./SignInDialog";
import { SiteFooter } from "./SiteFooter";
import { SiteHeader } from "./SiteHeader";
import { ToastProvider } from "./Toast";

/** Header, footer, toast and the app-wide sign-in dialog around every page. */
export function AppShell({ children }: { children: ReactNode }) {
  const [signInOpen, setSignInOpen] = useState(false);
  const actions = useMemo(() => ({ openSignIn: () => setSignInOpen(true) }), []);

  return (
    <ToastProvider>
      <ShellContext.Provider value={actions}>
        <SiteHeader />
        <main id="main">{children}</main>
        <SiteFooter />
        <SignInDialog open={signInOpen} onClose={() => setSignInOpen(false)} />
      </ShellContext.Provider>
    </ToastProvider>
  );
}
