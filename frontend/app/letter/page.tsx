import type { Metadata } from "next";
import { LetterView } from "./LetterView";

export const metadata: Metadata = { title: "Prepare a request" };

export default function LetterPage() {
  return (
    <div className="wrap">
      <LetterView />
    </div>
  );
}
