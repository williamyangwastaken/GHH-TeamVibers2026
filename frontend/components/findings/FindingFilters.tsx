import { CATEGORY_LABEL, type FindingCategory } from "@/lib/types";

export type FindingFilter = FindingCategory | "all";

interface FindingFiltersProps {
  categories: FindingCategory[];
  total: number;
  value: FindingFilter;
  onChange: (value: FindingFilter) => void;
}

/** Category chips; only categories present in this analysis are offered. */
export function FindingFilters({ categories, total, value, onChange }: FindingFiltersProps) {
  return (
    <div className="chips" role="group" aria-label="Filter findings">
      <button type="button" className="chip" aria-pressed={value === "all"} onClick={() => onChange("all")}>
        All ({total})
      </button>
      {categories.map((category) => (
        <button key={category} type="button" className="chip" aria-pressed={value === category} onClick={() => onChange(category)}>
          {CATEGORY_LABEL[category]}
        </button>
      ))}
    </div>
  );
}
