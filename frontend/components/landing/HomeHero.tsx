import { ArrowRight, Upload } from "lucide-react";
import Link from "next/link";
import type { RefObject } from "react";

const glyph = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;

function DocGlyph() {
  return (
    <svg width={15} height={15} {...glyph} aria-hidden="true">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h6" />
    </svg>
  );
}

/** The hero, recreated from the 1024px reference design; every position scales with --u. */
export function HomeHero({ billSlotRef }: { billSlotRef: RefObject<HTMLDivElement | null> }) {
  return (
    <div className="home-bg">
      <section className="home" aria-labelledby="homeTitle">
        <div className="h-blob" aria-hidden="true" />
        <svg className="h-band" viewBox="0 52 1024 520" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0,468 C180,436 420,430 600,452 C720,467 820,505 930,514 C982,511 1006,492 1024,466 L1024,572 L0,572 Z" fill="#f7f8f3" />
        </svg>
        <p className="h-eyebrow">Medical Bill Analyzer</p>
        <h1 className="h-title" id="homeTitle">
          You shouldn’t have
          <br />
          to be a billing expert.
        </h1>
        <p className="h-lead">
          Sana reads your medical bills, compares them<br className="dbr" /> with your insurance statements (and estimates, if you
          <br className="dbr" /> have them), and highlights potential issues, so you<br className="dbr" /> can take action with confidence.
        </p>
        <Link className="h-btn" href="/analyze">
          <Upload strokeWidth={1.9} aria-hidden="true" />
          Upload Your Documents
        </Link>
        <p className="h-fine">It’s free, secure, and takes less than a minute.</p>
        <div className="h-note" aria-hidden="true">
          Find
          <br />
          disputable
          <br />
          fees.
        </div>
        <svg
          className="h-arrow"
          viewBox="0 0 34 36"
          fill="none"
          stroke="#161d16"
          strokeWidth={1.3}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M3 2c-2 13 6 25 27 29" />
          <path d="M24 25l7 6-9 2" />
        </svg>
        <div className="h-billslot" ref={billSlotRef} aria-hidden="true" />
        <div className="h-feat" id="features" style={{ left: "calc(61 * var(--u))" }}>
          <span className="ic">
            <svg width={15} height={15} {...glyph} aria-hidden="true">
              <path d="m4 14 6-6 3 3-6 6H4z" />
              <path d="M13 5l6 6-5 5" />
              <path d="M9 3l2 2M15 19l2 2" />
            </svg>
          </span>
          <span>
            <b>Find discrepancies</b>
            <br />
            and duplicate charges
          </span>
        </div>
        <span className="h-sep" style={{ left: "calc(227 * var(--u))" }} aria-hidden="true">
          <ArrowRight strokeWidth={1.4} />
        </span>
        <div className="h-feat" style={{ left: "calc(257 * var(--u))" }}>
          <span className="ic">
            <DocGlyph />
          </span>
          <span>
            Get clear explanations
            <br />
            in plain English
          </span>
        </div>
        <span className="h-sep" style={{ left: "calc(425 * var(--u))" }} aria-hidden="true">
          <ArrowRight strokeWidth={1.4} />
        </span>
        <div className="h-feat" style={{ left: "calc(455 * var(--u))" }}>
          <span className="ic">
            <DocGlyph />
          </span>
          <span>
            <b>Generate a dispute letter</b>
            <br />
            (or call script)
          </span>
        </div>
      </section>
    </div>
  );
}
