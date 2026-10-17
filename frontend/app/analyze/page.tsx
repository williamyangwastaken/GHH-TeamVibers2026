import type { Metadata } from "next";
import { UploadForm } from "@/components/upload/UploadForm";

export const metadata: Metadata = { title: "Upload documents" };

export default function AnalyzePage() {
  return (
    <div className="wrap">
      <UploadForm />
    </div>
  );
}
