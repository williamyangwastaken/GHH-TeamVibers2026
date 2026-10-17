import {
  Calculator,
  CircleHelp,
  ClipboardList,
  Copy,
  Info,
  ReceiptText,
  Scale,
  ShieldCheck,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import {
  SEVERITY_LABEL,
  STATUS_LABEL,
  type DocumentKind,
  type FindingCategory,
  type FindingSeverity,
  type FindingStatus,
} from "@/lib/types";

type Tone = "" | "amber" | "clay" | "teal" | "gray";

const CATEGORY_TILE: Record<FindingCategory, { icon: LucideIcon; tone: Tone }> = {
  insurance_comparison: { icon: Scale, tone: "amber" },
  possible_duplicate: { icon: Copy, tone: "clay" },
  arithmetic: { icon: Calculator, tone: "teal" },
  estimate_comparison: { icon: ClipboardList, tone: "teal" },
  missing_context: { icon: CircleHelp, tone: "gray" },
};

export const KIND_ICON: Record<DocumentKind, LucideIcon> = {
  bill: ReceiptText,
  eob: ShieldCheck,
  estimate: ClipboardList,
};

export const KIND_TONE: Record<DocumentKind, Tone> = { bill: "", eob: "teal", estimate: "gray" };

export function CategoryTile({ category, size = 40 }: { category: FindingCategory; size?: number }) {
  const { icon: Icon, tone } = CATEGORY_TILE[category] ?? { icon: Info, tone: "gray" };
  return (
    <span className={`icon-tile ${tone}`.trim()} style={{ width: size, height: size }}>
      <Icon size={size * 0.48} aria-hidden="true" />
    </span>
  );
}

interface KindTileProps {
  kind: DocumentKind;
  size?: number;
  iconSize?: number;
  radius?: number;
  /** Defaults to the kind's own tone. */
  tone?: Tone;
}

export function KindTile({ kind, size = 36, iconSize = 17, radius = 10, tone = KIND_TONE[kind] }: KindTileProps) {
  const Icon = KIND_ICON[kind];
  return (
    <span className={`icon-tile ${tone}`.trim()} style={{ width: size, height: size, borderRadius: radius }}>
      <Icon size={iconSize} aria-hidden="true" />
    </span>
  );
}

export function StatusPill({ status }: { status: FindingStatus }) {
  const Icon = status === "needs_review" ? TriangleAlert : Info;
  return (
    <span className={`status ${status}`}>
      <Icon size={13} aria-hidden="true" />
      {STATUS_LABEL[status]}
    </span>
  );
}

export function SeverityTag({ severity }: { severity: FindingSeverity }) {
  return <span className={`tag ${severity}`}>{SEVERITY_LABEL[severity]}</span>;
}
