import { SARAH_ROWS, SARAH_TOTALS } from "@/lib/demo";
import { formatCents } from "@/lib/types";

/** The synthetic itemized bill (Sarah Johnson) that flies from the hero into the upload mock. */
export function BillCard() {
  return (
    <div className="bill">
      <h4>Itemized Medical Bill</h4>
      <div className="meta">
        <span>
          <b>Patient:</b> Sarah Johnson
        </span>
        <span>
          <b>Invoice:</b> Oct 12, 2026
        </span>
        <span>
          <b>Account:</b> #482-9012-XM
        </span>
        <span>
          <b>Statement Date:</b> Oct 12, 2026
        </span>
      </div>
      <table>
        <thead>
          <tr>
            <th style={{ width: "19%" }}>Date</th>
            <th style={{ width: "12%" }}>Code</th>
            <th>Description</th>
            <th className="r">Charge</th>
            <th className="r">Insurance</th>
            <th className="r">Patient</th>
          </tr>
        </thead>
        <tbody>
          {SARAH_ROWS.map((row) => (
            <tr key={row.id}>
              <td>09/14/2026</td>
              <td>{row.code}</td>
              <td>{row.desc}</td>
              <td className="r">{formatCents(row.charge)}</td>
              <td className="r ins">{formatCents(-row.ins)}</td>
              <td className="r">{formatCents(row.pt)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="sum">
        <span className="tc">Total Charges</span>
        <span className="tc">{formatCents(SARAH_TOTALS.charge)}</span>
        <span className="ip">Insurance Payments</span>
        <span>{formatCents(-SARAH_TOTALS.ins)}</span>
        <span className="due">Amount Due</span>
        <span>{formatCents(SARAH_TOTALS.pt)}</span>
      </div>
    </div>
  );
}
