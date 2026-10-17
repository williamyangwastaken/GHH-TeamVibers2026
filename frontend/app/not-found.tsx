import { FileText } from "lucide-react";
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="wrap">
      <div className="card empty mt-12">
        <span className="icon-tile">
          <FileText size={24} aria-hidden="true" />
        </span>
        <h2 className="text-[26px]">Page not found</h2>
        <p className="muted">That page doesn&apos;t exist. Start from the home page or open the upload screen.</p>
        <div className="cta-row mt-[18px] justify-center">
          <Link className="btn btn-primary" href="/">
            Go home
          </Link>
          <Link className="btn btn-secondary" href="/analyze">
            Upload Documents
          </Link>
        </div>
      </div>
    </div>
  );
}
