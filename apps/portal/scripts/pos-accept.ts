// pnpm pos:accept -- pre-registered acceptance A1-A4 for phase 12-01 (rules in 12-RESEARCH.md).
// Always runs in fixture mode, explicitly: never resolves the mode from env, so a pasted sandbox
// token can never make this script touch the network.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { csvSalesSource } from "../src/lib/sales/csv-source";
import { canonicalPanelCsv } from "../src/lib/sales/serialize";
import type { LocalDate, SalesLocation } from "../src/lib/sales/types";
import { createFixtureFetch } from "../src/lib/sales/square/fixture-fetch";
import { squareSalesSource } from "../src/lib/sales/square/source";

const portal = process.cwd().endsWith("apps/portal") ? process.cwd() : path.join(process.cwd(), "apps/portal");
const repo = path.resolve(portal, "../..");
const fx = (f: string) => readFileSync(path.join(portal, "fixtures/square", f), "utf8");
const outDir = path.join(repo, "var/pos");
mkdirSync(outDir, { recursive: true });

const manifest = JSON.parse(fx("MANIFEST.json"));
const truthText = fx("truth-daily.csv");
const params = JSON.parse(fx("params.json"));
const start = params.window.start as LocalDate;
const end = params.window.end as LocalDate;

const results: Array<{ id: string; ok: boolean; detail: string }> = [];
const check = (id: string, ok: boolean, detail: string) => { results.push({ id, ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} ${id}: ${detail}`); };

async function main() {
  // --- A3 setup: any use of the global fetch during the run is a failure ---
  const realFetch = globalThis.fetch;
  let stubCalls = 0;
  globalThis.fetch = (() => { stubCalls++; throw new Error("network call attempted in fixture mode"); }) as typeof fetch;

  const ff = createFixtureFetch();
  const sq = squareSalesSource({ mode: "fixture" }, { fetch: ff.fetch });
  const t0 = process.hrtime.bigint();
  let panel;
  let a3err = "";
  try {
    panel = await sq.fetchDaily({ locationIds: [], start, end, includeCategories: true });
  } catch (e) { a3err = String(e); }
  const pullMs = Number((process.hrtime.bigint() - t0) / BigInt(1_000_000));
  globalThis.fetch = realFetch;
  check("A3 offline", !!panel && stubCalls === 0 && panel.mode === "fixture" && panel.provenance.host === "fixture",
    panel ? `completed with throwing fetch stub, stub calls=${stubCalls}, mode=${panel.mode}, host=${panel.provenance.host}` : `run failed: ${a3err}`);
  if (!panel) return finish({ pullMs });

  // --- A1 exactness against the truth ledger ---
  const tl = truthText.trim().split("\n");
  const th = tl[0].split(",");
  const catNames = th.filter((h) => h.startsWith("cat_")).map((h) => h.slice(4));
  const truth = new Map<string, { gross: number; count: number; cats: Record<string, number> }>();
  for (const l of tl.slice(1)) {
    const f = l.split(",");
    const cats: Record<string, number> = {};
    catNames.forEach((c, i) => { const v = Number(f[4 + i]); if (v) cats[c] = v; });
    truth.set(`${f[0]}|${f[1]}`, { gross: Number(f[2]), count: Number(f[3]), cats });
  }
  let bad = 0, firstBad = "";
  for (const r of panel.rows) {
    const t = truth.get(`${r.locationId.replace(/^square:/, "")}|${r.date}`);
    const rc = r.categories ?? {};
    const tc = t?.cats ?? {};
    const keys = new Set([...Object.keys(rc), ...Object.keys(tc)]);
    const catBad = [...keys].some((k) => (rc[k] ?? 0) !== (tc[k] ?? 0));
    if (!t || t.gross !== r.grossSalesCents || t.count !== r.orderCount || catBad) {
      bad++;
      if (!firstBad) firstBad = `${r.locationId} ${r.date}: got ${r.grossSalesCents}/${r.orderCount} want ${t?.gross}/${t?.count}`;
    }
  }
  check("A1 fixture exactness", panel.rows.length === 1200 && truth.size === 1200 && bad === 0 && panel.provenance.duplicates === 0,
    `rows=${panel.rows.length} mismatches=${bad} duplicates=${panel.provenance.duplicates}${firstBad ? " first=" + firstBad : ""}`);

  // --- A2 CSV parity ---
  const locs: SalesLocation[] = panel.locations.map((l) => ({ ...l, id: l.id.replace(/^square:/, "csv:") }));
  const csvPanel = await csvSalesSource(fx("csv-export.csv"), { locations: locs }).fetchDaily({ locationIds: [], start, end, includeCategories: true });
  const a = canonicalPanelCsv(panel.rows, catNames);
  const b = canonicalPanelCsv(csvPanel.rows, catNames);
  check("A2 CSV parity", a === b && csvPanel.start === panel.start && csvPanel.end === panel.end,
    `square rows=${panel.rows.length} csv rows=${csvPanel.rows.length} (zero-filled ${csvPanel.provenance.zeroFilledRows}) byte-identical=${a === b}`);

  // --- A4 exclusions ---
  const pl = manifest.planted_total;
  const p = panel.provenance;
  const okA4 = p.returnOrders === pl.returnOrders && p.giftCardLines === pl.giftCardLines && p.customAmountLines === pl.customAmountLines && p.nonCompletedSeen === 0;
  check("A4 exclusions", okA4,
    `returns ${p.returnOrders}/${pl.returnOrders}, giftCardLines ${p.giftCardLines}/${pl.giftCardLines}, customAmountLines ${p.customAmountLines}/${pl.customAmountLines}, OPEN/CANCELED seen ${p.nonCompletedSeen} (planted ${pl.open}+${pl.canceled} server-side)`);

  writeFileSync(path.join(outDir, "panel-square-fixture.csv"), a);
  writeFileSync(path.join(outDir, "panel-csv.csv"), b);
  finish({
    pullMs, pages: p.pages, ordersSeen: p.ordersSeen, stubCalls, fixtureStats: ff.stats, provenance: p,
    fixtureManifestSha256: manifest.order_stream_sha256,
  });

  function finish(extra: Record<string, unknown>) {
    writeFileSync(path.join(outDir, "run-manifest.json"), JSON.stringify({
      mode: "fixture", host: "fixture", results, ...extra,
    }, null, 2) + "\n");
    console.log(`fixture pull time: ${(pullMs / 1000).toFixed(1)} s (informational, target <= 15 s)`);
    if (results.some((r) => !r.ok)) process.exit(1);
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
