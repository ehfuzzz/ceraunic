"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { tradingApi } from "@/lib/trading-api";
import { usd } from "@/lib/trading-format";
import { POLL_MS, useContractInfo } from "@/lib/trading-queries";
import { TradePrice } from "./TradePrice";
import { Bar, btnAccent, Empty, ErrorLine, Panel, Stat, td, th } from "./TradingKit";

export function AdminHouseMm({ token }: { token: string }) {
  const qc = useQueryClient();
  const info = useContractInfo();
  const mm = useQuery({ queryKey: ["admin-mm", token], queryFn: () => tradingApi.houseMm(token), refetchInterval: POLL_MS, retry: false });
  const auctions = useQuery({ queryKey: ["auctions"], queryFn: () => api.auctions(), refetchInterval: POLL_MS });
  const tick = useMutation({
    mutationFn: () => tradingApi.houseMmTick(token),
    onSuccess: () => {
      for (const k of ["admin-mm", "auctions", "auction", "pool"]) qc.invalidateQueries({ queryKey: [k] });
    },
  });

  const byAuction = new Map((auctions.data ?? []).map((a) => [a.auctionId, a]));
  const d = mm.data;

  return (
    <Panel title="House market maker" aside="Kalshi hedges are paper: no real orders are sent">
      <div className="flex flex-wrap items-center gap-4">
        <button className={btnAccent} disabled={tick.isPending} onClick={() => tick.mutate()}>
          {tick.isPending ? "Running…" : "Run a tick"}
        </button>
        <span className="text-sm text-muted">
          A tick posts the house quotes and places any hedges that are due. Running it twice at the same sim time does nothing the second time.
        </span>
      </div>
      <ErrorLine error={tick.error ?? mm.error} />
      {tick.data && (
        <p className="mt-3 text-sm text-muted">
          Tick {tick.data.tickKey}: {tick.data.quotesPosted} quotes posted, {tick.data.hedgesPlaced} hedges placed.
        </p>
      )}

      {d && (
        <>
          <div className="mt-6 flex flex-wrap gap-x-10 gap-y-4">
            <Stat label="P&L" value={usd(d.pnlE6)} />
            {Object.entries(d.capsUsed).map(([name, used]) => (
              <div key={name} className="w-44">
                <div className="text-xs uppercase tracking-wide text-muted">{name} cap used</div>
                <div className="mt-1 font-mono text-lg">{(used * 100).toFixed(1)}%</div>
                <div className="mt-1">
                  <Bar fraction={used} label={`${name} cap used`} />
                </div>
              </div>
            ))}
          </div>

          <h3 className="mb-2 mt-8 text-xs uppercase tracking-wide text-muted">Quotes on open auctions</h3>
          {d.quotes.length === 0 ? (
            <Empty>No open auctions to quote.</Empty>
          ) : (
            <table className="w-full max-w-3xl border-collapse">
              <thead>
                <tr className="border-b border-rule">
                  <th className={th}>Market</th>
                  <th className={th}>Day</th>
                  <th className={th}>Bid</th>
                  <th className={th}>Ask</th>
                  <th className={th}>Size</th>
                </tr>
              </thead>
              <tbody>
                {d.quotes.map((q) => {
                  const a = byAuction.get(q.auctionId);
                  const range = a ? info.range(a.contractId) : 50;
                  return (
                    <tr key={q.auctionId} className="border-b border-rule">
                      <td className={td}>
                        {a ? info.city(a.stationId) : q.auctionId}
                        {a && <div className="font-mono text-xs text-muted">{a.contractId}</div>}
                      </td>
                      <td className={`${td} font-mono`}>{a?.day ?? ""}</td>
                      <td className={td}><TradePrice priceE6={q.bidE6} range={range} /></td>
                      <td className={td}><TradePrice priceE6={q.askE6} range={range} /></td>
                      <td className={`${td} font-mono`}>{q.maxQty}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          <h3 className="mb-2 mt-8 text-xs uppercase tracking-wide text-muted">Inventory</h3>
          {d.inventory.length === 0 ? (
            <Empty>Flat. The house holds no residual units.</Empty>
          ) : (
            <table className="w-full max-w-md border-collapse">
              <thead>
                <tr className="border-b border-rule">
                  <th className={th}>Market</th>
                  <th className={th}>Net units</th>
                </tr>
              </thead>
              <tbody>
                {d.inventory.map((r) => (
                  <tr key={r.contractId} className="border-b border-rule">
                    <td className={td}>{info.contractCity(r.contractId)} <span className="font-mono text-xs text-muted">{r.contractId}</span></td>
                    <td className={`${td} font-mono`}>{r.netQty}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3 className="mb-2 mt-8 text-xs uppercase tracking-wide text-muted">Paper Kalshi hedges, by rung</h3>
          {d.hedges.length === 0 ? (
            <Empty>No hedges yet. They appear when a policy is sold on the house-hedge path.</Empty>
          ) : (
            <div className="space-y-5">
              {d.hedges.map((h, i) => (
                <div key={`${h.series}-${h.day}-${i}`}>
                  <div className="text-sm">
                    <span className="font-mono">{h.series}</span> for {h.day}: cost {usd(h.costE6)},{" "}
                    {h.payoutE6 == null ? "payout not known yet" : `payout ${usd(h.payoutE6)}`}
                  </div>
                  <table className="mt-1 w-full max-w-md border-collapse">
                    <thead>
                      <tr className="border-b border-rule">
                        <th className={th}>Rung</th>
                        <th className={th}>Contracts</th>
                        <th className={th}>Ask</th>
                      </tr>
                    </thead>
                    <tbody>
                      {h.rungs.map((r) => (
                        <tr key={r.ticker} className="border-b border-rule">
                          <td className={`${td} font-mono`}>{r.ticker}</td>
                          <td className={`${td} font-mono`}>{r.qty}</td>
                          <td className={`${td} font-mono`}>{r.askCents}&cent;</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
          <p className="mt-6 text-xs text-muted">Refreshes every few seconds.</p>
        </>
      )}
    </Panel>
  );
}
