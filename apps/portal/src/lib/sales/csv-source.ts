// CSV upload path. Columns: date,location_id,gross_sales_cents,order_count[,cat_<name>...]
// `date` is already the location's local calendar date; no time zone conversion happens here.
// Plain comma-separated, no quoting (a quote character is rejected, not guessed at).
import { enumerateDates, isLocalDate } from "./dates";
import { localKey } from "./serialize";
import type { DailySalesRow, FetchDailyRequest, LocalDate, SalesLocation, SalesPanel, SalesSource } from "./types";
import { validatePanel } from "./validate";

interface ParsedCsv {
  cats: string[];
  rows: Array<{ key: string; date: LocalDate; gross: number; count: number; cats: Record<string, number> }>;
}

function toInt(s: string, what: string, line: number): number {
  if (!/^\d+$/.test(s)) throw new Error(`csv line ${line}: ${what} must be a non-negative integer, got ${JSON.stringify(s)}`);
  const n = Number(s);
  if (!Number.isSafeInteger(n)) throw new Error(`csv line ${line}: ${what} out of range`);
  return n;
}

export function parseSalesCsv(text: string): ParsedCsv {
  if (text.includes('"')) throw new Error("csv: quoted fields are not supported");
  const lines = text.replace(/\r\n?/g, "\n").split("\n").filter((l) => l.trim() !== "");
  if (lines.length === 0) throw new Error("csv: empty file");
  const head = lines[0].split(",").map((h) => h.trim());
  const need = ["date", "location_id", "gross_sales_cents", "order_count"];
  for (const n of need) if (!head.includes(n)) throw new Error(`csv: missing column ${n}`);
  const idx = Object.fromEntries(head.map((h, i) => [h, i]));
  const catCols = head.filter((h) => h.startsWith("cat_"));
  const cats = catCols.map((h) => h.slice(4));
  const rows: ParsedCsv["rows"] = [];
  const seen = new Set<string>();
  for (let i = 1; i < lines.length; i++) {
    const f = lines[i].split(",").map((x) => x.trim());
    if (f.length !== head.length) throw new Error(`csv line ${i + 1}: expected ${head.length} fields, got ${f.length}`);
    const date = f[idx.date];
    if (!isLocalDate(date)) throw new Error(`csv line ${i + 1}: bad date ${JSON.stringify(date)}`);
    const key = f[idx.location_id];
    if (seen.has(`${key}|${date}`)) throw new Error(`csv line ${i + 1}: duplicate (${key}, ${date})`);
    seen.add(`${key}|${date}`);
    const c: Record<string, number> = {};
    catCols.forEach((h, j) => {
      const v = toInt(f[idx[h]], h, i + 1);
      if (v > 0) c[cats[j]] = v;
    });
    rows.push({
      key,
      date,
      gross: toInt(f[idx.gross_sales_cents], "gross_sales_cents", i + 1),
      count: toInt(f[idx.order_count], "order_count", i + 1),
      cats: c,
    });
  }
  return { cats, rows };
}

export function csvSalesSource(csvText: string, opts: { locations: SalesLocation[] }): SalesSource {
  return {
    kind: "csv",
    mode: "upload",
    async listLocations() {
      return opts.locations;
    },
    async fetchDaily(req: FetchDailyRequest): Promise<SalesPanel> {
      const parsed = parseSalesCsv(csvText);
      const locs = req.locationIds.length
        ? req.locationIds.map((id) => {
            const l = opts.locations.find((x) => x.id === id);
            if (!l) throw new Error(`unknown location ${id}`);
            return l;
          })
        : opts.locations;
      const inFile = new Set(parsed.rows.map((r) => r.key));
      for (const k of inFile) if (!opts.locations.some((l) => localKey(l.id) === k)) throw new Error(`csv: location_id ${k} has no matching location`);
      // Covered span = min..max date in the file (global). Dates inside it with no row are closed days: 0/0.
      const dates = parsed.rows.map((r) => r.date).sort();
      if (dates.length === 0) throw new Error("csv: no data rows");
      const covMin = dates[0];
      const covMax = dates[dates.length - 1];
      const start = (req.start > covMin ? req.start : covMin) as LocalDate;
      const end = (req.end < covMax ? req.end : covMax) as LocalDate;
      if (end < start) throw new Error("csv: requested range does not overlap the file");
      const have = new Map(parsed.rows.map((r) => [`${r.key}|${r.date}`, r]));
      const rows: DailySalesRow[] = [];
      let zeroFilled = 0;
      for (const l of locs) {
        for (const d of enumerateDates(start, end)) {
          const r = have.get(`${localKey(l.id)}|${d}`);
          if (!r) zeroFilled++;
          const row: DailySalesRow = { locationId: l.id, date: d, grossSalesCents: r?.gross ?? 0, orderCount: r?.count ?? 0 };
          if (req.includeCategories && parsed.cats.length) row.categories = { ...(r?.cats ?? {}) };
          rows.push(row);
        }
      }
      rows.sort((a, b) => (a.locationId === b.locationId ? (a.date < b.date ? -1 : 1) : a.locationId < b.locationId ? -1 : 1));
      const panel: SalesPanel = {
        source: "csv",
        mode: "upload",
        locations: locs,
        rows,
        start,
        end,
        pulledAt: new Date().toISOString(),
        provenance: { host: "upload", fileRows: parsed.rows.length, zeroFilledRows: zeroFilled, coveredFrom: covMin, coveredTo: covMax },
      };
      const errs = validatePanel(panel);
      if (errs.length) throw new Error(`csv panel invalid: ${errs.join("; ")}`);
      return panel;
    },
  };
}
