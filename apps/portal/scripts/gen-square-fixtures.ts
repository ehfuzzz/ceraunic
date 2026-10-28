// pnpm gen:fixtures  -- deterministic; two runs give an identical MANIFEST.json.
// Writes apps/portal/fixtures/square/{params,locations,catalog,sample-orders}.json,
// truth-daily.csv, csv-export.csv, MANIFEST.json. station-tmax.csv is an input (see MANIFEST.tmax_source).
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { parseTmaxCsv } from "../src/lib/sales/square/fixture-files";
import {
  DEFAULT_PARAMS, buildCatalogWire, buildLocationsWire, generateDay, localDatesOfWindow, zeroPlanted, type Planted, type WireOrder,
} from "../src/lib/sales/square/generate";

const root = process.cwd().endsWith("apps/portal") ? process.cwd() : path.join(process.cwd(), "apps/portal");
const dir = path.join(root, "fixtures/square");
const sha256 = (b: string | Buffer) => createHash("sha256").update(b).digest("hex");
const write = (f: string, s: string) => writeFileSync(path.join(dir, f), s);
const j = (x: unknown) => JSON.stringify(x, null, 2) + "\n";

const p = DEFAULT_PARAMS;
const tmaxPath = path.join(dir, "station-tmax.csv");
if (!existsSync(tmaxPath)) throw new Error("fixtures/square/station-tmax.csv missing (export it from data/cache/weather/official_daily.parquet)");
const tmaxText = readFileSync(tmaxPath, "utf8");
const tmax = parseTmaxCsv(tmaxText);
const dates = localDatesOfWindow(p);
if (dates.length !== 400) throw new Error(`window must be 400 local dates, got ${dates.length}`);
const tmaxRows = tmaxText.trim().split("\n").slice(1);
const carried = tmaxRows.filter((l) => l.split(",")[3] !== "nws_cli").length;

const catNames = [...new Set(p.locations.flatMap((l) => l.items.map((i) => i.category)).concat("Uncategorized"))].sort();
const streamHash = createHash("sha256");
const planted: Record<string, Planted> = {};
const truthRows: Array<{ loc: string; date: string; gross: number; count: number; cats: Record<string, number> }> = [];
const sample: WireOrder[] = [];
let totalOrders = 0;

for (const loc of p.locations) {
  planted[loc.id] = zeroPlanted();
  for (const d of dates) {
    const t = tmax.get(`${loc.station}|${d}`);
    if (t === undefined) throw new Error(`no tmax for ${loc.station} ${d}`);
    const day = generateDay(p, loc, d, t);
    // the ledger row is taken here, from the prices drawn, before any UTC bucketing by the adapter
    truthRows.push({ loc: loc.id, date: d, gross: day.truth.gross, count: day.truth.count, cats: day.truth.cats });
    for (const k of Object.keys(planted[loc.id]) as Array<keyof Planted>) planted[loc.id][k] += day.planted[k];
    for (const o of day.orders) {
      streamHash.update(JSON.stringify(o) + "\n");
      totalOrders++;
      if (loc.id === p.locations[0].id && sample.length < 25) sample.push(o);
    }
  }
}
if (truthRows.length !== 1200) throw new Error(`truth must have 1200 rows, got ${truthRows.length}`);

const total = zeroPlanted();
for (const v of Object.values(planted)) for (const k of Object.keys(total) as Array<keyof Planted>) total[k] += v[k];

const catCols = catNames.map((c) => `cat_${c}`);
const catCells = (c: Record<string, number>) => catNames.map((n) => c[n] ?? 0);
write("params.json", j(p));
write("locations.json", j(buildLocationsWire(p)));
write("catalog.json", j(buildCatalogWire(p)));
write("sample-orders.json", j({ orders: sample }));
write("truth-daily.csv", [["location_id", "date", "gross_sales_cents", "order_count", ...catCols].join(","),
  ...truthRows.map((r) => [r.loc, r.date, r.gross, r.count, ...catCells(r.cats)].join(","))].join("\n") + "\n");
// CSV upload format for the same business: date first, rows by date then location, closed days (0/0) omitted.
const csvRows = truthRows.filter((r) => r.gross > 0 || r.count > 0)
  .sort((a, b) => (a.date !== b.date ? (a.date < b.date ? -1 : 1) : a.loc < b.loc ? -1 : 1));
write("csv-export.csv", [["date", "location_id", "gross_sales_cents", "order_count", ...catCols].join(","),
  ...csvRows.map((r) => [r.date, r.loc, r.gross, r.count, ...catCells(r.cats)].join(","))].join("\n") + "\n");

const files = ["params.json", "station-tmax.csv", "locations.json", "catalog.json", "sample-orders.json", "truth-daily.csv", "csv-export.csv"];
const srcGen = readFileSync(path.join(root, "src/lib/sales/square/generate.ts"));
write("MANIFEST.json", j({
  generator: "apps/portal/scripts/gen-square-fixtures.ts + src/lib/sales/square/generate.ts",
  generator_version: p.generator_version,
  generator_sha256: sha256(srcGen),
  square_version: p.square_version,
  seed: p.seed,
  window: p.window,
  local_dates: dates.length,
  truth_rows: truthRows.length,
  zero_days_omitted_from_csv_export: truthRows.length - csvRows.length,
  tmax_source: `official_daily.parquet (NWS CLI high_f), stations NYC/MDW/MIA; ${carried} of ${tmaxRows.length} rows carried forward from the previous day (missing or null upstream)`,
  planted_betas: Object.fromEntries(p.locations.map((l) => [l.id, { beta: l.beta, tref: l.tref }])),
  total_orders_in_stream: totalOrders,
  planted_total: total,
  planted_by_location: planted,
  order_stream_sha256: streamHash.digest("hex"),
  file_sha256: Object.fromEntries(files.map((f) => [f, sha256(readFileSync(path.join(dir, f)))])),
}));
console.log(`fixtures written: ${totalOrders} orders in stream, ${truthRows.length} truth rows, ${csvRows.length} csv rows`);
