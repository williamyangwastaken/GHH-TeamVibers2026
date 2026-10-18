"use client";

import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, type MouseEvent } from "react";

export interface ShellActions {
  openSignIn: () => void;
}

export const ShellContext = createContext<ShellActions>({ openSignIn: () => {} });

export function useShell(): ShellActions {
  return useContext(ShellContext);
}

/** "How it works" links point at /#how; on the homepage itself, scroll there smoothly instead. */
export function useHowItWorksClick() {
  const pathname = usePathname();
  return useCallback(
    (event: MouseEvent<HTMLAnchorElement>) => {
      if (pathname !== "/") return;
      event.preventDefault();
      document.getElementById("how")?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    [pathname],
  );
}
