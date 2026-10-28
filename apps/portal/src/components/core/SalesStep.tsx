"use client";

// Sales history -> Phase 12 SalesPanel (csv-source.ts, or the Square card) -> POST /businesses/{id}/sales
// -> POST /businesses/{id}/elasticity. The panel is built in the browser; only daily totals leave it.
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, type Business, type SalesSummary } from "@/lib/api";
import { explain } from "@/lib/core-api";
import { usdCents, usdCentsWhole } from "@/lib/core-format";
import { METRO_TZ, tzForLatLon, type Metro } from "@/lib/geocode";
import { useCoreSession, useEngineMode } from "@/lib/core-session";
import { csvSalesSource, parseSalesCsv } from "@/lib/sales/csv-source";
import { asLocalDate } from "@/lib/sales/dates";
import type { SalesPanel } from "@/lib/sales/types";
import { ConnectSquareCard } from "../ConnectSquareCard";
import { btn, btnPrimary, ErrorLine, input, label, Muted, Stat } from "./ui";

const ZONES = ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"];

interface Loaded {
  source: "csv" | "square";
  fileName: string;
  keys: string[];
  panel?: SalesPanel; // square: already built
  text?: string; // csv: raw text, the panel is built once location + zone are chosen
}

const keyOf = (id: string) => id.replace(/^(square|csv):/, "");

export function SalesStep({ business }: { business: Business }) {
  const cfg = useEngineMode();
  const { sales, save } = useCoreSession();
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [loc, setLoc] = useState<string>("");
  const [tz, setTz] = useState<string>(METRO_TZ[business.city as Metro] ?? tzForLatLon(business.lat, business.lon));
  const [panel, setPanel] = useState<SalesPanel | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const maxRows = cfg.data?.limits.maxSalesRows ?? 5000;

  // Build the one-location panel we would send. Called from event handlers only.
  async function rebuild(l: Loaded, key: string, zone: string) {
    setLoadError(null);
    setPanel(null);
    try {
      if (l.source === "square" && l.panel) {
        const p = l.panel;
        const id = p.locations.find((x) => keyOf(x.id) === key)!.id;
        setPanel({ ...p, locations: p.locations.filter((x) => x.id === id), rows: p.rows.filter((r) => r.locationId === id) });
        return;
      }
      const locations = l.keys.map((k) => ({
        id: `csv:${k}`,
        name: k,
        timezone: zone,
        currency: "USD" as const,
        ...(k === key ? { lat: business.lat, lon: business.lon } : {}),
      }));
      const src = csvSalesSource(l.text!, { locations });
      setPanel(await src.fetchDaily({ locationIds: [`csv:${key}`], start: asLocalDate("1900-01-01"), end: asLocalDate("2999-12-31") }));
    } catch (e) {
      setLoadError(explain(e));
    }
  }

  async function onFile(f: File | undefined) {
    setLoadError(null);
    setLoaded(null);
    setPanel(null);
    if (!f) return;
    try {
      const text = await f.text();
      const parsed = parseSalesCsv(text);
      const keys = [...new Set(parsed.rows.map((r) => r.key))].sort();
      const l: Loaded = { source: "csv", fileName: f.name, keys, text };
      setLoaded(l);
      setLoc(keys[0] ?? "");
      if (keys[0]) await rebuild(l, keys[0], tz);
    } catch (e) {
      setLoadError(explain(e));
    }
  }

  function onSquare(p: SalesPanel) {
    const keys = p.locations.map((l) => keyOf(l.id));
    const l: Loaded = { source: "square", fileName: "Square", keys, panel: p };
    setLoaded(l);
    setLoc(keys[0] ?? "");
    if (keys[0]) void rebuild(l, keys[0], tz);
  }

  const upload = useMutation({
    mutationFn: async (): Promise<SalesSummary> => {
      if (!panel) throw new Error("Pick a location first.");
      const rows = panel.rows.slice(-maxRows).map((r) => ({ date: r.date, grossSalesCents: r.grossSalesCents, orderCount: r.orderCount }));
      const summary = await api.uploadSales(business.businessId, rows, panel.source === "square" ? "square" : "csv");
      save("sales", summary);
      const el = await api.elasticity(business.businessId);
      save("elasticity", el);
      return summary;
    },
  });

  const skip = useMutation({
    mutationFn: async () => {
      const el = await api.elasticity(business.businessId);
      save("elasticity", el);
      return el;
    },
  });

  const stats = panel ? panelStats(panel) : null;
  const trimmed = panel ? Math.max(0, panel.rows.length - maxRows) : 0;

  return (
    <div>
      <div className="border border-rule p-5">
        <h3 className="font-display text-lg">Upload a sales file</h3>
        <p className="mt-2 text-sm text-muted">
          One row per location per day, with the columns <code className="font-mono text-xs">date, location_id, gross_sales_cents, order_count</code>{" "}
          and, if you have them, <code className="font-mono text-xs">cat_&lt;name&gt;</code> columns for categories. The date is the calendar day
          where the shop is, not UTC. Gross sales are in cents and leave out tax, tips, gift-card loads and returns. A day missing
          from the file counts as a closed day with zero sales. Plain commas only; quoted fields are rejected rather than guessed at.
        </p>
        <input
          type="file"
          accept=".csv,text/csv"
          className="mt-4 block text-sm file:mr-3 file:border file:border-rule file:bg-bg file:px-3 file:py-1.5 file:text-sm file:text-ink"
          onChange={(e) => onFile(e.target.files?.[0])}
          data-testid="sales-upload-input"
        />
        {!loaded && <ErrorLine error={loadError} />}
      </div>

      <ConnectSquareCard onUse={onSquare} />

      {loaded && (
        <div className="mt-6 border border-rule p-5" data-testid="sales-preview">
          <h3 className="font-display text-lg">
            {loaded.source === "csv" ? `From ${loaded.fileName}` : "From Square"}
          </h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className={label} htmlFor="sales-loc">
                Which location is {business.name}?
              </label>
              <select id="sales-loc" className={`${input} mt-1`} value={loc} onChange={(e) => {
                  setLoc(e.target.value);
                  void rebuild(loaded, e.target.value, tz);
                }}
                data-testid="sales-location">
                {loaded.keys.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </div>
            {loaded.source === "csv" && (
              <div>
                <label className={label} htmlFor="sales-tz">
                  Time zone the dates are in
                </label>
                <select id="sales-tz" className={`${input} mt-1`} value={tz}
                  onChange={(e) => {
                    setTz(e.target.value);
                    void rebuild(loaded, loc, e.target.value);
                  }}>
                  {ZONES.map((z) => (
                    <option key={z}>{z}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <ErrorLine error={loadError} />

          {panel && stats && (
            <>
              <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat label="Days" value={stats.days} note={`${panel.start} to ${panel.end}`} />
                <Stat label="Closed days (zero sales)" value={stats.closed} />
                <Stat label="Average open day" value={usdCentsWhole(stats.avgOpenCents)} />
                <Stat label="Total gross sales" value={usdCentsWhole(stats.totalCents)} />
              </div>
              <table className="mt-5 w-full text-sm">
                <thead>
                  <tr className="border-b border-rule text-left text-muted">
                    <th className="py-1 font-normal">Last 7 days</th>
                    <th className="py-1 text-right font-normal">Gross sales</th>
                    <th className="py-1 text-right font-normal">Orders</th>
                  </tr>
                </thead>
                <tbody>
                  {panel.rows.slice(-7).map((r) => (
                    <tr key={r.date} className="border-b border-rule/60">
                      <td className="py-1 font-mono text-xs">{r.date}</td>
                      <td className="py-1 text-right">{usdCents(r.grossSalesCents)}</td>
                      <td className="py-1 text-right">{r.orderCount}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {trimmed > 0 && <Muted className="mt-2">The engine takes at most {maxRows} days, so we send the most recent {maxRows} and drop the oldest {trimmed}.</Muted>}
              <button type="button" className={`${btnPrimary} mt-5`} onClick={() => upload.mutate()} disabled={upload.isPending} data-testid="sales-send">
                {upload.isPending ? "Sending…" : `Send ${Math.min(panel.rows.length, maxRows)} days of sales`}
              </button>
              <ErrorLine error={upload.error ? explain(upload.error) : null} />
            </>
          )}
        </div>
      )}

      {sales && <SalesSummaryView summary={sales} />}

      {!sales && (
        <div className="mt-6">
          <button type="button" className={btn} onClick={() => skip.mutate()} disabled={skip.isPending} data-testid="sales-skip">
            No sales file? Use the average for your kind of business
          </button>
          <ErrorLine error={skip.error ? explain(skip.error) : null} />
        </div>
      )}
    </div>
  );
}

function panelStats(p: SalesPanel) {
  const days = p.rows.length;
  const open = p.rows.filter((r) => r.grossSalesCents > 0);
  const totalCents = p.rows.reduce((s, r) => s + r.grossSalesCents, 0);
  return { days, closed: days - open.length, totalCents, avgOpenCents: open.length ? totalCents / open.length : 0 };
}

export function SalesSummaryView({ summary }: { summary: SalesSummary }) {
  return (
    <div className="mt-6 border-l-2 border-accent pl-4" data-testid="sales-summary">
      <p className="text-sm">
        The engine has {summary.rows} days of sales for this business
        {summary.firstDate ? `, ${summary.firstDate} to ${summary.lastDate}` : ""}.{" "}
        {summary.gaps > 0 ? `${summary.gaps} days in that span are missing.` : "No days are missing in that span."}
      </p>
      {summary.warnings.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-sm text-accent">
          {summary.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
