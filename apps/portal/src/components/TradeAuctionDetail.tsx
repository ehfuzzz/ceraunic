"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Auction } from "@/lib/api";
import { tradingApi } from "@/lib/trading-api";
import { utc, usd } from "@/lib/trading-format";
import { POLL_MS } from "@/lib/trading-queries";
import { TradeClearButton, TradeClearingResult } from "./TradeClearing";
import { TradeOrderForm } from "./TradeOrderForm";
import { TradePrice } from "./TradePrice";
import { btn, Empty, ErrorLine, Panel, td, th } from "./TradingKit";

type Level = Auction["bids"][number];

function Book({ title, levels, range }: { title: string; levels: Level[]; range: number }) {
  return (
    <div>
      <h3 className="text-xs uppercase tracking-wide text-muted">{title}</h3>
      {levels.length === 0 ? (
        <p className="mt-2 text-sm text-muted">No orders.</p>
      ) : (
        <table className="mt-1 w-full border-collapse">
          <thead>
            <tr className="border-b border-rule">
              <th className={th}>Price</th>
              <th className={th}>Units</th>
            </tr>
          </thead>
          <tbody>
            {levels.map((l) => (
              <tr key={l.priceE6} className="border-b border-rule">
                <td className={td}>
                  <TradePrice priceE6={l.priceE6} range={range} />
                </td>
                <td className={`${td} font-mono`}>{l.qty}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function TradeAuctionDetail({
  auction,
  trader,
  city,
  range,
  isSim,
  simTime,
  onCleared,
}: {
  auction: Auction;
  trader: string | null;
  city: string;
  range: number;
  isSim: boolean;
  simTime?: string;
  onCleared?: () => void;
}) {
  const qc = useQueryClient();
  const positions = useQuery({
    queryKey: ["positions", trader],
    queryFn: () => api.positions(trader!),
    enabled: !!trader,
    refetchInterval: POLL_MS,
  });
  const cancel = useMutation({
    mutationFn: (orderId: string) => tradingApi.cancelOrder(auction.auctionId, orderId, trader!),
    onSuccess: () => {
      for (const key of ["auction", "auctions", "balances", "positions"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });

  const mine = (positions.data?.openOrders ?? []).filter((o) => o.auctionId === auction.auctionId);
  const myFilled = (positions.data?.residuals ?? []).filter((p) => p.contractId === auction.contractId && p.day === auction.day);
  const hq = auction.houseQuote;

  return (
    <Panel
      title={`${city}, ${auction.day}`}
      aside={
        <>
          {auction.auctionId} &middot; cutoff {utc(auction.publicCutoff)}
          {simTime && <> &middot; sim time {utc(simTime)}</>}
        </>
      }
    >
      {hq && (
        <div className="mb-6 flex flex-wrap gap-x-10 gap-y-3">
          <div>
            <div className="text-xs uppercase tracking-wide text-muted">House bid</div>
            <div className="mt-1 text-lg"><TradePrice priceE6={hq.bidE6} range={range} /></div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-muted">House ask</div>
            <div className="mt-1 text-lg"><TradePrice priceE6={hq.askE6} range={range} /></div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-muted">House size</div>
            <div className="mt-1 font-mono text-lg">{hq.maxQty}</div>
          </div>
        </div>
      )}

      <div className="grid gap-8 md:grid-cols-2">
        <Book title="Bids (people who want to buy)" levels={auction.bids} range={range} />
        <Book title="Asks (people who want to sell)" levels={auction.asks} range={range} />
      </div>

      {auction.status === "open" && (
        <div className="mt-8">
          <h3 className="mb-3 text-xs uppercase tracking-wide text-muted">Place an order</h3>
          <TradeOrderForm key={auction.auctionId} auctionId={auction.auctionId} trader={trader} range={range} />
        </div>
      )}

      <div className="mt-8">
        <h3 className="mb-2 text-xs uppercase tracking-wide text-muted">Your open orders here</h3>
        {!trader ? (
          <Empty>Pick a trader to see your orders.</Empty>
        ) : mine.length === 0 ? (
          <Empty>None.</Empty>
        ) : (
          <table className="w-full max-w-2xl border-collapse">
            <thead>
              <tr className="border-b border-rule">
                <th className={th}>Order</th>
                <th className={th}>Side</th>
                <th className={th}>Units</th>
                <th className={th}>Limit</th>
                <th className={th}>Locked</th>
                <th className={th} />
              </tr>
            </thead>
            <tbody>
              {mine.map((o) => (
                <tr key={o.orderId} className="border-b border-rule">
                  <td className={`${td} font-mono`}>{o.orderId}</td>
                  <td className={td}>{o.side}</td>
                  <td className={`${td} font-mono`}>{o.qty}</td>
                  <td className={td}><TradePrice priceE6={o.limitPriceE6} range={range} /></td>
                  <td className={`${td} font-mono`}>{usd(o.lockedE6)}</td>
                  <td className={td}>
                    {auction.status === "open" && (
                      <button className={btn} disabled={cancel.isPending} onClick={() => cancel.mutate(o.orderId)}>
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <ErrorLine error={cancel.error} />
      </div>

      <div className="mt-8">
        <h3 className="mb-3 text-xs uppercase tracking-wide text-muted">Clearing</h3>
        <TradeClearButton auction={auction} isSim={isSim} onCleared={onCleared} />
        {auction.result && (
          <div className="mt-4">
            <TradeClearingResult result={auction.result} range={range} />
          </div>
        )}
        {myFilled.length > 0 && (
          <p className="mt-4 text-sm text-muted">
            Your position from this auction:{" "}
            {myFilled.map((p) => `${p.side} ${p.qty} at ${p.entryPriceE6 / 10_000}¢ (${usd(p.lockedE6)} locked)`).join("; ")}.
          </p>
        )}
      </div>
    </Panel>
  );
}
