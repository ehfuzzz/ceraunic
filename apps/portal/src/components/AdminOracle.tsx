"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { tradingApi } from "@/lib/trading-api";
import { utc } from "@/lib/trading-format";
import { POLL_MS, useContractInfo, useSimClock } from "@/lib/trading-queries";
import { btnAccent, Empty, ErrorLine, field, Panel, td, th } from "./TradingKit";

export function AdminOracle({ token }: { token: string }) {
  const qc = useQueryClient();
  const info = useContractInfo();
  const clock = useSimClock();
  const rows = useQuery({ queryKey: ["admin-oracle", token], queryFn: () => tradingApi.oracle(token), refetchInterval: POLL_MS, retry: false });
  const [index, setIndex] = useState<string | null>(null);
  const [day, setDay] = useState<string | null>(null);

  // Default to the newest day the sim clock says is observable: yesterday.
  const defaultDay = clock.data
    ? new Date(new Date(clock.data.simTime).getTime() - 86_400_000).toISOString().slice(0, 10)
    : "";
  const chosenIndex = index ?? (info.stations[0] ? `tmax:${info.stations[0].stationId}` : "");
  const chosenDay = day ?? defaultDay;

  const report = useMutation({
    mutationFn: () => tradingApi.oracleReport(token, chosenIndex, chosenDay),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-oracle"] }),
  });

  return (
    <Panel title="Oracle" aside="daily high temperature, read the day after at 12:00Z">
      <ErrorLine error={rows.error} />
      {rows.data && rows.data.length === 0 && <Empty>No readings yet. Advance the clock past noon UTC the day after.</Empty>}
      {rows.data && rows.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] border-collapse">
            <thead>
              <tr className="border-b border-rule">
                <th className={th}>Index</th>
                <th className={th}>Day</th>
                <th className={th}>High</th>
                <th className={th}>Source</th>
                <th className={th}>Vintage</th>
                <th className={th}>Fetched</th>
                <th className={th}>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.data.map((r) => (
                <tr key={`${r.index}-${r.day}`} className="border-b border-rule">
                  <td className={`${td} font-mono`}>{r.index}</td>
                  <td className={`${td} font-mono`}>{r.day}</td>
                  <td className={`${td} font-mono`}>{(r.value / 10).toFixed(1)} &deg;F</td>
                  <td className={td}>{r.source}</td>
                  <td className={`${td} font-mono`} title={r.vintageHash}>{`${r.vintageHash.slice(0, 8)}\u2026`}</td>
                  <td className={`${td} font-mono`}>{utc(r.fetchedAt)}</td>
                  <td className={td}>{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form
        className="mt-6 flex flex-wrap items-end gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          report.mutate();
        }}
      >
        <label className="text-xs uppercase tracking-wide text-muted">
          Index
          <select className={`${field} mt-1 block`} value={chosenIndex} onChange={(e) => setIndex(e.target.value)}>
            {info.stations.map((s) => (
              <option key={s.stationId} value={`tmax:${s.stationId}`}>
                {s.city} (tmax:{s.stationId})
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs uppercase tracking-wide text-muted">
          Day
          <input className={`${field} mt-1 block w-36`} value={chosenDay} onChange={(e) => setDay(e.target.value)} />
        </label>
        <button className={btnAccent} disabled={!chosenIndex || !/^\d{4}-\d{2}-\d{2}$/.test(chosenDay) || report.isPending}>
          Report reading
        </button>
      </form>
      <ErrorLine error={report.error} />
      {report.data && (
        <p className="mt-3 text-sm text-muted">
          Reported {report.data.index} for {report.data.day}: {(report.data.value / 10).toFixed(1)} &deg;F, now {report.data.status}.
        </p>
      )}
    </Panel>
  );
}
