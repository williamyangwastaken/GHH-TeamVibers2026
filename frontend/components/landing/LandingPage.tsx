"use client";

import { useRouter } from "next/navigation";
import { useLayoutEffect, useMemo, useRef, type RefObject } from "react";
import { useTrySample } from "@/components/layout/useTrySample";
import { getBundledSample, SARAH_TOTALS } from "@/lib/demo";
import { useAppState } from "@/lib/state";
import { formatCents } from "@/lib/types";
import { BillCard } from "./BillCard";
import { HomeHero } from "./HomeHero";
import { HowItWorks, type SampleScreen } from "./HowItWorks";
import { useBillFlight } from "./useBillFlight";

/**
 * Fade sections in as they scroll into view. Sections already on screen are marked
 * visible before the hiding class goes on, so server-rendered content never flashes out.
 */
function useRevealOnScroll(rootRef: RefObject<HTMLElement | null>) {
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root || !("IntersectionObserver" in window)) return;
    const sections = Array.from(root.querySelectorAll<HTMLElement>(".reveal"));
    const vh = window.innerHeight;
    for (const section of sections) {
      const box = section.getBoundingClientRect();
      if (box.top < vh && box.bottom > 0) section.classList.add("in");
    }
    root.classList.add("reveal-on");
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("in");
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.12 },
    );
    sections.filter((section) => !section.classList.contains("in")).forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [rootRef]);
}

export function LandingPage() {
  const router = useRouter();
  const { setAnalysis } = useAppState();
  const { trySample, isLoading } = useTrySample();

  const root = useRef<HTMLDivElement>(null);
  const traveler = useRef<HTMLDivElement>(null);
  const heroSlot = useRef<HTMLDivElement>(null);
  const dock = useRef<HTMLDivElement>(null);
  const uploadStage = useRef<HTMLDivElement>(null);
  const scanStage = useRef<HTMLDivElement>(null);
  const scanTable = useRef<HTMLDivElement>(null);
  const flightRefs = useMemo(
    () => ({ root, traveler, heroSlot, dock, uploadStage, scanStage, scanTable }),
    [],
  );

  useRevealOnScroll(root);
  useBillFlight(flightRefs);

  // The step mock-ups show Sarah's itemized bill, so their links open that sample.
  const openSarahSample = (screen: SampleScreen) => {
    const sample = getBundledSample("demo-sarah");
    if (!sample) return;
    const first = sample.findings[0];
    setAnalysis(sample, "bundled-sample", screen === "letter" ? { selectedFindingIds: [first.id] } : undefined);
    router.push(screen === "finding" ? `/results?finding=${encodeURIComponent(first.id)}` : `/${screen}`);
  };

  return (
    <div className="home-root" ref={root}>
      <HomeHero billSlotRef={heroSlot} />
      <HowItWorks
        refs={{ dock, uploadStage, scanStage, scanTable }}
        onOpenUpload={() => router.push("/analyze")}
        onOpenSample={openSarahSample}
        onTrySample={() => void trySample()}
        isLoadingSample={isLoading}
      />
      <div
        className="traveler"
        ref={traveler}
        role="img"
        aria-label={`Sample itemized medical bill for Sarah Johnson: total charges ${formatCents(SARAH_TOTALS.charge)}, insurance payments ${formatCents(SARAH_TOTALS.ins)}, amount due ${formatCents(SARAH_TOTALS.pt)}`}
      >
        <BillCard />
      </div>
    </div>
  );
}
