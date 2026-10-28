"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { tradingApi } from "@/lib/trading-api";
import { utc } from "@/lib/trading-format";
import { useSimClock } from "@/lib/trading-queries";
import { notifyStoreChanged, useWorldId } from "@/lib/trading-store";
import { btn, btnAccent, Empty, ErrorLine, field, Panel, Stat } from "./TradingKit";

export function AdminSimControls() {
  const qc = useQueryClient();
  const clock = useSimClock();
  const world = useWorldId();
  const [days, setDays] = useState("1");
  const n = Number(days);
  const valid = Number.isInteger(n) && n >= 1 && n <= 10;

  const advance = useMutation({
    mutationFn: () => tradingApi.advanceDays(n),
    onSuccess: () => qc.invalidateQueries(),
  });
  const fresh = useMutation({
    mutationFn: () => api.newWorld(),
    onSuccess: () => {
      notifyStoreChanged();
      qc.invalidateQueries();
    },
  });

  return (
    <Panel title="Simulated clock" aside="sim only">
      <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
        <Stat label="Sim time" value={clock.data ? utc(clock.data.simTime) : "…"} />
        <Stat
          label="World"
          value={<span className="text-base">{world ?? "demo (shared)"}</span>}
          sub={world ? undefined : "everyone on the demo shares this clock"}
        />
        <label className="text-xs uppercase tracking-wide text-muted">
          Days (1 to 10)
          <input className={`${field} mt-1 block w-20`} inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value)} />
        </label>
        <button className={btnAccent} disabled={!valid || advance.isPending} onClick={() => advance.mutate()}>
          {advance.isPending ? "Advancing…" : `Advance ${n === 1 ? "1 day" : `${valid ? n : "?"} days`}`}
        </button>
        <button className={btn} disabled={fresh.isPending} onClick={() => fresh.mutate()}>
          New private world
        </button>
      </div>
      <p className="mt-3 max-w-2xl text-sm text-muted">
        Advancing moves the clock forward and runs everything that would happen in that time: cutoffs, hedges, oracle reads, pool epochs. Use a
        private world if you don&rsquo;t want to move the shared demo.
      </p>
      <ErrorLine error={advance.error ?? fresh.error ?? clock.error} />
      {advance.data && (
        <div className="mt-4">
          <h3 className="text-xs uppercase tracking-wide text-muted">What happened (now {utc(advance.data.simTime)})</h3>
          {advance.data.events.length === 0 ? (
            <Empty>Nothing was scheduled in that time.</Empty>
          ) : (
            <ul className="mt-2 max-h-48 overflow-y-auto text-sm">
              {advance.data.events.map((e, i) => (
                <li key={`${e.ts}-${i}`} className="border-b border-rule py-1">
                  <span className="font-mono text-xs text-muted">{utc(e.ts)}</span> <span className="font-mono text-xs">{e.kind}</span> {e.detail}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Panel>
  );
}
