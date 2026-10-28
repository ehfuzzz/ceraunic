import type { DailySalesRow } from "./types";

/** Source-local location key: "square:LFIX1" and "csv:LFIX1" are the same business location. */
export const localKey = (id: string) => id.replace(/^[a-z]+:/, "");

/** Canonical CSV for comparing panels across sources. Rows sorted by (location key, date),
 *  category columns are exactly `catNames` (0-filled), no source prefix on the location id. */
export function canonicalPanelCsv(rows: DailySalesRow[], catNames: string[]): string {
  const cols = [...catNames].sort();
  const head = ["location_id", "date", "gross_sales_cents", "order_count", ...cols.map((c) => `cat_${c}`)].join(",");
  const sorted = [...rows].sort((a, b) => {
    const la = localKey(a.locationId), lb = localKey(b.locationId);
    return la !== lb ? (la < lb ? -1 : 1) : a.date < b.date ? -1 : a.date > b.date ? 1 : 0;
  });
  const lines = sorted.map((r) =>
    [localKey(r.locationId), r.date, r.grossSalesCents, r.orderCount, ...cols.map((c) => r.categories?.[c] ?? 0)].join(","),
  );
  return [head, ...lines].join("\n") + "\n";
}
