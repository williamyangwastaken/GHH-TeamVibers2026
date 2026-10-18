"use client";

import Link from "next/link";
import { useHowItWorksClick } from "./shell";

export function SiteFooter() {
  const onHowItWorks = useHowItWorksClick();

  return (
    <footer className="site-footer">
      <div className="ft">
        <div>
          <span className="wordmark">Sana</span>
          <p>Understand your bill. Find discrepancies. Take action.</p>
        </div>
        <nav aria-label="Footer">
          <Link href="/">Home</Link>
          <Link href="/#how" onClick={onHowItWorks}>
            How it works
          </Link>
          <Link href="/results">My Bills</Link>
        </nav>
        <div className="credit">Girls Hoo Hack 2026 · Team Vibers</div>
      </div>
    </footer>
  );
}
