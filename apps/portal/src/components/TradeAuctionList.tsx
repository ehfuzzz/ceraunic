"use client";

import type { Auction } from "@/lib/api";
import { utc } from "@/lib/trading-format";
import { Empty, td, th } from "./TradingKit";
import { TradePrice } from "./TradePrice";

const STATUS_LABEL = { open: "open", closed: "closed, not cleared", cleared: "cleared" } as const;

export function TradeAuctionList({
  auctions,
  selectedId,
  onSelect,
  city,
  range,
}: {
  auctions: Auction[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  city: (stationId: string) => string;
  range: (contractId: string) => number;
}) {
  if (!auctions.length) return <Empty>No auctions yet.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[46rem] border-collapse">
        <thead>
          <tr className="border-b border-rule">
            <th className={th}>Market</th>
            <th className={th}>Day</th>
            <th className={th}>Status</th>
            <th className={th}>Cutoff</th>
            <th className={th}>House bid</th>
            <th className={th}>House ask</th>
            <th className={th}>Book (bids / asks)</th>
          </tr>
        </thead>
        <tbody>
          {auctions.map((a) => {
            const r = range(a.contractId);
            const sel = a.auctionId === selectedId;
            const bidQty = a.bids.reduce((n, l) => n + l.qty, 0);
            const askQty = a.asks.reduce((n, l) => n + l.qty, 0);
            return (
              <tr key={a.auctionId} className={`border-b border-rule ${sel ? "bg-surface" : ""}`}>
                <td className={td}>
                  <button
                    className="text-left underline-offset-4 hover:underline"
                    aria-pressed={sel}
                    onClick={() => onSelect(a.auctionId)}
                  >
                    {city(a.stationId)}
                  </button>
                  <div className="font-mono text-xs text-muted">{a.contractId}</div>
                </td>
                <td className={`${td} font-mono`}>{a.day}</td>
                <td className={`${td} ${a.status === "open" ? "text-accent" : "text-muted"}`}>{STATUS_LABEL[a.status]}</td>
                <td className={`${td} font-mono`}>{utc(a.publicCutoff)}</td>
                <td className={td}>
                  <TradePrice priceE6={a.houseQuote?.bidE6 ?? null} range={r} />
                </td>
                <td className={td}>
                  <TradePrice priceE6={a.houseQuote?.askE6 ?? null} range={r} />
                  {a.houseQuote && <div className="text-xs text-muted">up to {a.houseQuote.maxQty}</div>}
                </td>
                <td className={`${td} font-mono`}>
                  {bidQty} / {askQty}
                  <div className="text-xs text-muted">{a.orderCount} orders</div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
