import {
  ArrowRight,
  Check,
  ClipboardList,
  FileText,
  PenLine,
  ReceiptText,
  Search,
  ShieldCheck,
  TriangleAlert,
  Upload,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { MouseEvent, RefObject } from "react";
import { CategoryTile } from "@/components/findings/FindingBadges";
import { SARAH_ROWS, SARAH_TOTALS } from "@/lib/demo";
import { formatCents } from "@/lib/types";

export type SampleScreen = "results" | "finding" | "letter";

interface HowItWorksProps {
  refs: {
    dock: RefObject<HTMLDivElement | null>;
    uploadStage: RefObject<HTMLDivElement | null>;
    scanStage: RefObject<HTMLDivElement | null>;
    scanTable: RefObject<HTMLDivElement | null>;
  };
  onOpenUpload: () => void;
  onOpenSample: (screen: SampleScreen) => void;
  onTrySample: () => void;
  isLoadingSample: boolean;
}

const STEPS = [
  { id: "step-1", label: "Upload" },
  { id: "step-2", label: "Compare" },
  { id: "step-3", label: "Verify" },
  { id: "step-4", label: "Ask" },
];

function WinBar({ url }: { url: string }) {
  return (
    <div className="win-bar">
      <i />
      <i />
      <i />
      <span className="url">sana.app/{url}</span>
    </div>
  );
}

function Tick() {
  return (
    <span className="tick">
      <Check size={11} strokeWidth={3} aria-hidden="true" />
    </span>
  );
}

function jumpTo(event: MouseEvent<HTMLAnchorElement>) {
  event.preventDefault();
  const id = event.currentTarget.getAttribute("href")?.slice(1);
  if (id) document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
}

/** "How it works": four mock screens built from the Sarah sample case, then principles and the CTA band. */
export function HowItWorks({ refs, onOpenUpload, onOpenSample, onTrySample, isLoadingSample }: HowItWorksProps) {
  const [cbc, xray] = SARAH_ROWS.slice(3);
  const miniTile = { width: 28, height: 28, borderRadius: 8 };

  return (
    <section className="mk" id="how" aria-labelledby="howTitle">
      <div className="mk-wrap">
        <div className="mk-head reveal">
          <div className="eyebrow">How it works</div>
          <h2 className="serif" id="howTitle">
            From a confusing bill
            <br />
            to a <em>clear</em> next step.
          </h2>
          <p>Four simple steps, about a minute from start to finish. You stay in control the whole way.</p>
          <div className="guide-rail">
            {STEPS.map((step, i) => (
              <a key={step.id} href={`#${step.id}`} onClick={jumpTo}>
                <span>{i + 1}</span>
                {step.label}
              </a>
            ))}
          </div>
        </div>

        <div className="step-row" id="step-1">
          <div className="step-copy">
            <div className="step-num">01</div>
            <h3>Upload your documents</h3>
            <p>
              Start with your medical bill. Add your insurance EOB or Good Faith Estimate too, if you have them. More
              documents unlock more checks.
            </p>
            <ul>
              <li>
                <Tick />
                PDF, PNG, or JPG
              </li>
              <li>
                <Tick />
                Nothing is sent until you press Analyze
              </li>
            </ul>
            <button className="try-link" type="button" onClick={onOpenUpload}>
              Open the upload screen <ArrowRight size={15} aria-hidden="true" />
            </button>
          </div>
          <div className="stage-card" id="uploadStage" ref={refs.uploadStage}>
            <div className="win">
              <WinBar url="upload" />
              <div className="win-body">
                <h4>Upload Your Documents</h4>
                <div className="s">Add your bill and, if you have it, your EOB.</div>
                <div className="m-drop">
                  <div className="m-slot" id="billDock" ref={refs.dock}>
                    <span className="wait-txt" />
                  </div>
                  <div className="m-status">
                    <span className="wait">Drop your medical bill here</span>
                    <span className="ok">
                      <span className="check-circle" style={{ width: 15, height: 15, color: "#fff" }}>
                        <Check size={9} strokeWidth={3} aria-hidden="true" />
                      </span>
                      itemized-bill.pdf uploaded
                    </span>
                  </div>
                </div>
                <div className="m-docs">
                  <div className="m-doc">
                    <span className="icon-tile" style={miniTile}>
                      <ReceiptText size={15} aria-hidden="true" />
                    </span>
                    <span className="n">Medical Bill</span>
                    <span className="f">
                      <span className="wait">Waiting</span>
                      <span className="ok items-center" style={{ gap: 5 }}>
                        <span className="check-circle" style={{ width: 14, height: 14, color: "#fff" }}>
                          <Check size={8} strokeWidth={3} aria-hidden="true" />
                        </span>
                        itemized-bill.pdf
                      </span>
                    </span>
                  </div>
                  <div className="m-doc">
                    <span className="icon-tile teal" style={miniTile}>
                      <ShieldCheck size={15} aria-hidden="true" />
                    </span>
                    <span className="n">Insurance EOB</span>
                    <span className="f">Optional</span>
                  </div>
                  <div className="m-doc">
                    <span className="icon-tile gray" style={miniTile}>
                      <ClipboardList size={15} aria-hidden="true" />
                    </span>
                    <span className="n">Good Faith Estimate</span>
                    <span className="f">Optional</span>
                  </div>
                </div>
                <div className="m-btn">Analyze Documents</div>
              </div>
            </div>
          </div>
        </div>

        <div className="step-row flip" id="step-2">
          <div className="step-copy">
            <div className="step-num">02</div>
            <h3>We compare every number</h3>
            <p>
              Gemini reads each line of your documents. Then a transparent rules engine checks the math, looks for repeated
              or mismatched codes, and lines up your bill against your EOB.
            </p>
            <ul>
              <li>
                <Tick />
                Math checks
              </li>
              <li>
                <Tick />
                Repeated or mismatched codes
              </li>
              <li>
                <Tick />
                Bill vs. EOB comparison
              </li>
            </ul>
            <button className="try-link" type="button" onClick={() => onOpenSample("results")}>
              See the sample results <ArrowRight size={15} aria-hidden="true" />
            </button>
          </div>
          <div className="stage-card b scan-pending" id="scanStage" ref={refs.scanStage}>
            <div className="win">
              <WinBar url="results" />
              <div className="win-body">
                <h4>Here&apos;s what we found</h4>
                <div className="s">Checking 5 line items on itemized-bill.pdf</div>
                <div className="m-scan" id="scanTable" ref={refs.scanTable}>
                  {SARAH_ROWS.map((row, i) => (
                    <div key={row.id} className="sr" data-row={i} data-flag={i > 2 ? "1" : "0"}>
                      <span className="c">{row.code}</span>
                      <span className="d">{row.desc}</span>
                      <span className="a">{formatCents(row.charge)}</span>
                      <span className="k">
                        {i > 2 ? <TriangleAlert size={10} aria-hidden="true" /> : <Check size={10} strokeWidth={3} aria-hidden="true" />}
                      </span>
                    </div>
                  ))}
                  <div className="sr total" data-row="5" data-flag="0">
                    <span className="c">Total</span>
                    <span className="d">
                      {formatCents(SARAH_TOTALS.charge)} - {formatCents(SARAH_TOTALS.ins)} insurance
                    </span>
                    <span className="a">{formatCents(SARAH_TOTALS.pt)}</span>
                    <span className="k">
                      <Check size={10} strokeWidth={3} aria-hidden="true" />
                    </span>
                  </div>
                </div>
                <div className="m-result">
                  <div className="m-res">
                    <CategoryTile category="possible_duplicate" size={28} />
                    <div className="flex-1">
                      <b>Same code on two services</b>
                      <span className="sm">80004 is listed for a blood count and a chest X-ray</span>
                    </div>
                    <span className="m-pill" style={{ background: "var(--amber-bg)", color: "var(--amber)" }}>
                      Needs review
                    </span>
                  </div>
                  <div className="m-res">
                    <CategoryTile category="arithmetic" size={28} />
                    <div className="flex-1">
                      <b>The math checks out</b>
                      <span className="sm">
                        {formatCents(SARAH_TOTALS.charge)} in charges minus {formatCents(SARAH_TOTALS.ins)} insurance ={" "}
                        {formatCents(SARAH_TOTALS.pt)} due
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="step-row reveal" id="step-3">
          <div className="step-copy">
            <div className="step-num">03</div>
            <h3>See exactly where it came from</h3>
            <p>
              Every finding links back to the document, page, and line it came from, with possible innocent explanations.
              Check it yourself in seconds.
            </p>
            <ul>
              <li>
                <Tick />
                Source page for every figure
              </li>
              <li>
                <Tick />
                Highlighted line items
              </li>
            </ul>
            <button className="try-link" type="button" onClick={() => onOpenSample("finding")}>
              Open the evidence view <ArrowRight size={15} aria-hidden="true" />
            </button>
          </div>
          <div className="stage-card">
            <div className="win">
              <WinBar url="finding" />
              <div className="win-body">
                <h4>Same code listed for two different services</h4>
                <div className="s">itemized-bill.pdf · page 1 · service date 09/14/2026</div>
                <div className="m-cmp">
                  <div>
                    <span className="l">Line 4 · code 80004</span>
                    <b>{formatCents(cbc.charge)}</b>
                    <span className="chip">{cbc.desc}</span>
                  </div>
                  <div>
                    <span className="l">Line 5 · code 80004</span>
                    <b>{formatCents(xray.charge)}</b>
                    <span className="chip">{xray.desc}</span>
                  </div>
                </div>
                <div className="m-paper">
                  <div className="pp">
                    <div className="h">
                      Itemized Medical Bill<span>SAMPLE</span>
                    </div>
                    {SARAH_ROWS.slice(2).map((row, i) => (
                      <div key={row.id} className={`ln${i > 0 ? " hl" : ""}`}>
                        <span>
                          {row.code} {row.desc}
                        </span>
                        <span>{formatCents(row.charge)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
            <div className="float-tag" style={{ right: -18, top: 26 }}>
              <span className="icon-tile">
                <FileText size={14} aria-hidden="true" />
              </span>
              Page 1, highlighted
            </div>
          </div>
        </div>

        <div className="step-row flip reveal" id="step-4">
          <div className="step-copy">
            <div className="step-num">04</div>
            <h3>Ask with confidence</h3>
            <p>
              Pick the findings you care about and get a polite, specific letter that uses only the facts we found. Edit it,
              copy it, and send it yourself.
            </p>
            <ul>
              <li>
                <Tick />
                Clarification or dispute tone
              </li>
              <li>
                <Tick />
                Copy or download as text
              </li>
              <li>
                <Tick />
                Never sent automatically
              </li>
            </ul>
            <button className="try-link" type="button" onClick={() => onOpenSample("letter")}>
              Draft a sample letter <ArrowRight size={15} aria-hidden="true" />
            </button>
          </div>
          <div className="stage-card b">
            <div className="win">
              <WinBar url="letter" />
              <div className="win-body">
                <h4>Prepare your request</h4>
                <div className="s">Subject: Request for clarification, account #482-9012-XM</div>
                <div className="m-sheet">
                  <div className="sh">
                    Hello,
                    <br />
                    <br />
                    My itemized bill lists code <b>{cbc.code}</b> for two different services on 09/14/2026: {cbc.desc} (
                    <b>{formatCents(cbc.charge)}</b>) and {xray.desc} (<b>{formatCents(xray.charge)}</b>). Could you confirm the
                    correct procedure code for each?
                    <br />
                    <br />
                    Thank you,
                    <br />
                    <span className="m-ph">[Your name]</span>
                  </div>
                </div>
                <div className="m-actions">
                  <span className="p">Copy to clipboard</span>
                  <span>Download TXT</span>
                </div>
                <div className="m-note">Review and verify all details before sending. This draft has not been sent.</div>
              </div>
            </div>
          </div>
        </div>

        <div className="principles reveal">
          <div className="principle">
            <span className="icon-tile">
              <Search size={19} aria-hidden="true" />
            </span>
            <h4>Evidence, not guesses</h4>
            <p>Every flag points to the exact figures and pages behind it.</p>
          </div>
          <div className="principle">
            <span className="icon-tile amber">
              <TriangleAlert size={19} aria-hidden="true" />
            </span>
            <h4>Honest labels</h4>
            <p>A difference is something to ask about, not proof of an error. We say so plainly.</p>
          </div>
          <div className="principle">
            <span className="icon-tile teal">
              <PenLine size={19} aria-hidden="true" />
            </span>
            <h4>You stay in control</h4>
            <p>Nothing is sent for you. You review, edit, and decide what happens next.</p>
          </div>
        </div>

        <div className="family reveal">
          <div className="ph">
            <Image
              src="/demo/family.jpg"
              alt="A couple smiling at a phone on their living room couch, with paperwork and mugs on the coffee table"
              fill
              sizes="(max-width: 860px) 100vw, 620px"
            />
            <div className="tag-card">
              <span className="icon-tile">
                <Check size={14} strokeWidth={3} aria-hidden="true" />
              </span>
              Bills sorted, questions ready
            </div>
          </div>
          <div>
            <div className="eyebrow">Made for real life</div>
            <h2 className="serif">
              Less time decoding bills. <em>More time</em> for what matters.
            </h2>
            <p>
              Medical paperwork piles up fast. Sana shows what each bill says, what your insurance covered, and what is worth a
              question, in plain English.
            </p>
            <p>No jargon, no guesswork, and nothing sent without you.</p>
          </div>
        </div>

        <div className="mk-bottom">
          <div className="cta-band reveal">
            <h2 className="serif">
              See it with a <em>sample bill</em>.
            </h2>
            <p>Walk through a full example in under a minute. No account or upload needed.</p>
            <div className="cta-row justify-center">
              <button className="btn btn-light" type="button" onClick={onTrySample} disabled={isLoadingSample}>
                {isLoadingSample ? "Loading sample…" : "Try the sample case"}
              </button>
              <Link className="btn btn-outline" href="/analyze">
                <Upload size={17} aria-hidden="true" /> Upload your documents
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
