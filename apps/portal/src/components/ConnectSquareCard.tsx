"use client";

import { useEffect, useState } from "react";
import type { SalesPanel } from "@/lib/sales/types";

type Loc = { id: string; name: string; timezone: string };
type Row = { locationId: string; date: string; grossSalesCents: number; orderCount: number };
type Panel = { mode: string; locations: Loc[]; rows: Row[]; start: string; end: string; pulledAt: string; provisionalFrom?: string };
type Info = { mode: "fixture" | "sandbox"; locations: Loc[]; defaultEnd: string };

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

const MODE_LABEL: Record<string, string> = {
  fixture: "Demo data (recorded Square responses)",
  sandbox: "Square sandbox (test seller)",
};

function shift(d: string, n: number): string {
  const [y, m, day] = d.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, day) + n * 86_400_000).toISOString().slice(0, 10);
}

// onUse (Phase 10, optional): hands the pulled panel to the onboarding flow so it can feed the elasticity step.
export function ConnectSquareCard({ onUse }: { onUse?: (panel: SalesPanel) => void } = {}) {
  const [info, setInfo] = useState<Info | null>(null);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    fetch("/api/pos/square")
      .then(async (r) => {
        const j = await r.json();
        if (!r.ok) throw new Error(j.error ?? `HTTP ${r.status}`);
        if (live) setInfo(j);
      })
      .catch((e) => live && setError(String(e.message ?? e)));
    return () => {
      live = false;
    };
  }, []);

  async function connect() {
    if (!info) return;
    setBusy(true);
    setError(null);
    try {
      const r = await fetch("/api/pos/square", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ locationIds: [], start: shift(info.defaultEnd, -29), end: info.defaultEnd }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error ?? `HTTP ${r.status}`);
      setPanel(j);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  }

  const locs = panel?.locations ?? info?.locations ?? [];
  const dates = panel ? [...new Set(panel.rows.map((r) => r.date))].sort().reverse() : [];
  const cell = new Map(panel?.rows.map((r) => [`${r.locationId}|${r.date}`, r]) ?? []);

  return (
    <section className="mt-10 max-w-3xl border border-rule bg-surface p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="font-display text-xl tracking-tight">Connect Square</h2>
        {info && (
          <span className="border border-rule px-2 py-0.5 font-mono text-xs text-muted" data-mode={info.mode}>
            {MODE_LABEL[info.mode]}
          </span>
        )}
      </div>
      <p className="mt-3 text-sm text-muted">
        Pulls completed orders per location and turns them into daily sales. Gross sales exclude tax, tips, gift-card loads and returns.
      </p>

      {error && <p className="mt-4 font-mono text-xs text-accent">Error: {error}</p>}
      {!info && !error && <p className="mt-4 font-mono text-xs text-muted">Loading locations…</p>}

      {info && (
        <ul className="mt-4 divide-y divide-rule border-y border-rule text-sm">
          {info.locations.map((l) => (
            <li key={l.id} className="flex flex-wrap justify-between gap-2 py-2">
              <span>{l.name}</span>
              <span className="font-mono text-xs text-muted">{l.id.replace(/^square:/, "")} · {l.timezone}</span>
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={connect}
        disabled={!info || busy}
        className="mt-5 border border-accent px-4 py-2 text-sm text-accent disabled:opacity-40"
      >
        {busy ? "Pulling…" : panel ? "Pull again" : "Connect Square"}
      </button>
      {panel && onUse && (
        <button
          type="button"
          onClick={() => onUse(panel as unknown as SalesPanel)}
          className="ml-3 mt-5 border border-rule px-4 py-2 text-sm hover:border-ink"
          data-testid="square-use"
        >
          Use these sales
        </button>
      )}

      {panel && (
        <div className="mt-6 overflow-x-auto">
          <p className="mb-2 font-mono text-xs text-muted">
            Last 30 days, {panel.start} to {panel.end}. Gross sales / orders per location.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-muted">
                <th className="py-1 pr-4 font-normal">Date</th>
                {locs.map((l) => (
                  <th key={l.id} className="py-1 pr-4 text-right font-normal">{l.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dates.map((d) => (
                <tr key={d} className="border-b border-rule/60">
                  <td className="py-1 pr-4 font-mono text-xs">{d}</td>
                  {locs.map((l) => {
                    const r = cell.get(`${l.id}|${d}`);
                    return (
                      <td key={l.id} className="py-1 pr-4 text-right">
                        {r ? `${usd.format(r.grossSalesCents / 100)} / ${r.orderCount}` : "–"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
