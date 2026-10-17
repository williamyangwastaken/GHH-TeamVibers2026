"use client";

import { UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAppState } from "@/lib/state";
import { BrandMark } from "./BrandMark";
import { useHowItWorksClick, useShell } from "./shell";
import { useToast } from "./Toast";

function initials(name: string): string {
  const words = name.replace(/\(.*?\)/g, " ").split(/\s+/).filter(Boolean);
  return words.slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?";
}

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const toast = useToast();
  const { openHelp, openSignIn } = useShell();
  const onHowItWorks = useHowItWorksClick();
  const { user, signOut, analysis, loadSample } = useAppState();
  const [menuOpen, setMenuOpen] = useState(false);
  const avatarRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close the account menu on outside click or Escape, like the prototype.
  useEffect(() => {
    if (!menuOpen) return;
    menuRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const onPointer = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!menuRef.current?.contains(target) && !avatarRef.current?.contains(target)) setMenuOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setMenuOpen(false);
      avatarRef.current?.focus();
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const onAvatar = () => (user ? setMenuOpen((open) => !open) : openSignIn());

  const openMyBills = async () => {
    setMenuOpen(false);
    // Jordan's "bills" are the synthetic sample case.
    if (!analysis && user?.isDemo) await loadSample("demo-mismatch");
    router.push("/results");
  };

  return (
    <header className="site-header">
      <div className="hdr">
        <Link className="brand" href="/" aria-label="Sana home">
          <BrandMark />
          <span className="wordmark">Sana</span>
        </Link>
        <nav className="nav" aria-label="Main">
          <Link href="/" aria-current={pathname === "/" ? "page" : undefined}>
            Home
          </Link>
          <Link href="/results" aria-current={pathname === "/results" ? "page" : undefined}>
            My Bills
          </Link>
          <Link href="/#how" onClick={onHowItWorks}>
            How It Works
          </Link>
          <button type="button" onClick={openHelp}>
            Help
          </button>
        </nav>
        <button
          ref={avatarRef}
          className={`avatar${user ? " signed" : ""}`}
          type="button"
          aria-haspopup={user ? "menu" : "dialog"}
          aria-expanded={user ? menuOpen : undefined}
          aria-label={user ? `Account menu for ${user.name}` : "Sign in"}
          onClick={onAvatar}
        >
          {user ? initials(user.name) : <UserRound strokeWidth={1.8} aria-hidden="true" />}
        </button>
        <div ref={menuRef} className="acct-menu" role="menu" aria-label="Account" hidden={!menuOpen}>
          {user && (
            <div className="who">
              <strong>{user.name}</strong>
              <span>{user.email}</span>
            </div>
          )}
          <button role="menuitem" type="button" onClick={openMyBills}>
            My Bills
          </button>
          <button
            role="menuitem"
            type="button"
            onClick={() => {
              setMenuOpen(false);
              openHelp();
            }}
          >
            Help
          </button>
          <button
            role="menuitem"
            type="button"
            onClick={() => {
              setMenuOpen(false);
              signOut();
              toast("Signed out");
              avatarRef.current?.focus();
            }}
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
