import type { Metadata, Viewport } from "next";
import { Caveat, Figtree, Instrument_Serif } from "next/font/google";
import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { AppStateProvider } from "@/lib/state";
import "./globals.css";

// Same families and weights as the prototype's Google Fonts link, self-hosted by next/font.
const figtree = Figtree({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-figtree",
  display: "swap",
});
const caveat = Caveat({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-caveat", display: "swap" });
const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Sana", template: "%s · Sana" },
  description:
    "Understand your bill. Find discrepancies. Take action. A Girls Hoo Hack 2026 prototype for synthetic medical bills and EOBs.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f6f7f1",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${figtree.variable} ${caveat.variable} ${instrumentSerif.variable}`}>
      <body>
        <AppStateProvider>
          <AppShell>{children}</AppShell>
        </AppStateProvider>
      </body>
    </html>
  );
}
