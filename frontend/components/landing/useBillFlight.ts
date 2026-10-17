"use client";

import { useEffect, type RefObject } from "react";

export interface BillFlightRefs {
  root: RefObject<HTMLElement | null>;
  traveler: RefObject<HTMLElement | null>;
  heroSlot: RefObject<HTMLElement | null>;
  dock: RefObject<HTMLElement | null>;
  uploadStage: RefObject<HTMLElement | null>;
  scanStage: RefObject<HTMLElement | null>;
  scanTable: RefObject<HTMLElement | null>;
}

/** Natural width of the bill card (.bill { width: 620px }). */
const BASE_WIDTH = 620;

const clamp = (v: number) => Math.max(0, Math.min(1, v));
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const bezier = (a: number, c: number, b: number, t: number) => (1 - t) * (1 - t) * a + 2 * (1 - t) * t * c + t * t * b;

/**
 * Scroll-driven homepage animation, ported from the prototype:
 *  1. the hero bill flies along a curve into the upload mock and docks;
 *  2. when the compare mock reaches mid-screen it scans each line, flags the 80004 pair, then shows results.
 * Everything is a pure function of scroll position, so scrolling back reverses it.
 * With prefers-reduced-motion, a static copy is shown docked instead.
 */
export function useBillFlight(refs: BillFlightRefs) {
  useEffect(() => {
    const root = refs.root.current;
    const traveler = refs.traveler.current;
    const heroSlot = refs.heroSlot.current;
    const dock = refs.dock.current;
    const uploadStage = refs.uploadStage.current;
    const scanStage = refs.scanStage.current;
    const scanTable = refs.scanTable.current;
    const card = traveler?.firstElementChild;
    if (!root || !traveler || !heroSlot || !dock || !uploadStage || !scanStage || !scanTable || !(card instanceof HTMLElement)) return;

    const rows = Array.from(scanTable.querySelectorAll<HTMLElement>(".sr"));
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let baseHeight = 0;
    let frame = 0;
    let disposed = false;
    let staticCopy: HTMLElement | null = null;

    const relative = (el: HTMLElement) => {
      const r = el.getBoundingClientRect();
      const o = root.getBoundingClientRect();
      return { x: r.left - o.left, y: r.top - o.top, w: r.width, h: r.height };
    };
    const pageY = (el: HTMLElement) => el.getBoundingClientRect().top + window.scrollY;

    const update = () => {
      frame = 0;
      const vh = window.innerHeight;
      const sy = window.scrollY;
      const narrow = window.innerWidth < 860;

      // Segment 1: hero slot -> upload dock.
      const a = relative(heroSlot);
      const b = relative(dock);
      const end1 = pageY(dock) + b.h / 2 - vh * 0.56;
      const p1 = reduced ? 0 : clamp(end1 > 0 ? sy / end1 : 1);
      const e1 = ease(p1);
      const w = lerp(a.w, b.w, 1 - Math.pow(1 - p1, 2.2)); // shrink early, clear of the headings
      const scale = w / BASE_WIDTH;
      const h = baseHeight * scale;
      const cx = bezier(a.x + a.w / 2, (a.x + a.w / 2 + b.x + b.w / 2) / 2 + (narrow ? 0 : 210), b.x + b.w / 2, e1);
      const cy = lerp(a.y + a.h / 2, b.y + b.h / 2, p1); // linear in scroll: the bill floats alongside the reader
      const rotation = lerp(-2.5, 0, e1) + Math.sin(Math.PI * e1) * 5;
      const x = cx - w / 2;
      const y = cy - h / 2;
      traveler.style.transform =
        `translate(${x}px, ${y}px) translate(${w / 2}px, ${h / 2}px) rotate(${rotation}deg) ` +
        `translate(${-w / 2}px, ${-h / 2}px) scale(${scale})`;
      uploadStage.classList.toggle("docked", reduced || p1 >= 0.995);

      // Segment 2: line-by-line scan as the compare mock reaches mid-screen.
      const end2 = pageY(scanTable) + scanTable.offsetHeight / 2 - vh * 0.5;
      const q = reduced ? 1 : clamp((sy - end2 + vh * 0.12) / (vh * 0.26));
      const step = q * (rows.length + 1);
      rows.forEach((row, i) => {
        const done = step > i + 1;
        row.classList.toggle("ok", done && row.dataset.flag === "0");
        row.classList.toggle("flag", done && row.dataset.flag === "1");
        row.classList.toggle("cur", !done && step > i);
      });
      scanStage.classList.toggle("scan-pending", q < 0.97);
      traveler.dataset.ready = "true";
    };

    const layout = () => {
      if (disposed) return;
      baseHeight = card.offsetHeight;
      heroSlot.style.height = `${(baseHeight * heroSlot.getBoundingClientRect().width) / BASE_WIDTH}px`;
      dock.style.height = `${(baseHeight * dock.getBoundingClientRect().width) / BASE_WIDTH}px`;
      if (reduced) {
        staticCopy?.remove();
        staticCopy = card.cloneNode(true) as HTMLElement;
        staticCopy.setAttribute("aria-hidden", "true");
        staticCopy.style.transform = `scale(${dock.getBoundingClientRect().width / BASE_WIDTH})`;
        staticCopy.style.transformOrigin = "0 0";
        dock.style.placeItems = "start";
        dock.append(staticCopy);
      }
      update();
    };

    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    const onResize = () => requestAnimationFrame(layout);

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    void document.fonts?.ready.then(layout);
    layout();

    return () => {
      disposed = true;
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      if (frame) cancelAnimationFrame(frame);
      staticCopy?.remove();
    };
  }, [refs]);
}
