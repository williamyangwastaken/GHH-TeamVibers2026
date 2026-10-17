import { fieldLabel, formatCents, formatDate, KIND_LABEL, type AnalysisResponse } from "@/lib/types";

const MONEY_FIELDS = [
  "total_charges_cents",
  "insurance_paid_cents",
  "adjustments_cents",
  "patient_responsibility_cents",
  "amount_due_cents",
  "expected_total_cents",
] as const;

const Dash = () => <span className="null">-</span>;

/** Side-by-side values as read from each document; rows that no document reports are hidden. */
export function DocumentsGlance({ analysis }: { analysis: AnalysisResponse }) {
  const docs = analysis.documents;
  const rows = MONEY_FIELDS.filter((field) => docs.some((doc) => doc[field] != null));

  return (
    <div className="card glance">
      <div className="px-5 pb-3.5 pt-[18px]">
        <h3>Documents at a glance</h3>
        <p className="tiny muted mb-0 mt-1">
          Values as read from each document. Verify them against the originals. A dash means the value wasn&apos;t visible.
        </p>
      </div>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Field</th>
              {docs.map((doc) => (
                <th key={doc.id} className="r">
                  {KIND_LABEL[doc.kind]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Provider</td>
              {docs.map((doc) => (
                <td key={doc.id} className="r">
                  {doc.provider_name || <Dash />}
                </td>
              ))}
            </tr>
            <tr>
              <td>Service date</td>
              {docs.map((doc) => (
                <td key={doc.id} className="r">
                  {formatDate(doc.service_date) ?? <Dash />}
                </td>
              ))}
            </tr>
            <tr>
              <td>Claim #</td>
              {docs.map((doc) => (
                <td key={doc.id} className="r">
                  {doc.claim_number || <Dash />}
                </td>
              ))}
            </tr>
            {rows.map((field) => (
              <tr key={field}>
                <td>{fieldLabel(field)}</td>
                {docs.map((doc) => (
                  <td key={doc.id} className="r">
                    {doc[field] != null ? formatCents(doc[field]) : <Dash />}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
