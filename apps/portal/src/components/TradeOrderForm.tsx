"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Side } from "@/lib/api";
import { basisF, signedF, UNIT_E6, usd } from "@/lib/trading-format";
import { btnAccent, ErrorLine, field } from "./TradingKit";

export function TradeOrderForm({ auctionId, trader, range }: { auctionId: string; trader: string | null; range: number }) {
  const qc = useQueryClient();
  const [side, setSide] = useState<Side>("buy");
  const [qty, setQty] = useState("10");
  const [cents, setCents] = useState("30");

  const q = Number(qty);
  const c = Number(cents);
  const valid = Number.isInteger(q) && q > 0 && Number.isInteger(c) && c >= 1 && c <= 99;
  const priceE6 = valid ? c * 10_000 : 0;
  const lock = valid ? q * (side === "buy" ? priceE6 : UNIT_E6 - priceE6) : 0;

  const place = useMutation({
    mutationFn: () => api.postOrder({ auctionId, trader: trader!, side, qty: q, limitPriceE6: priceE6 }),
    onSuccess: () => {
      for (const key of ["auction", "auctions", "balances", "positions"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        place.mutate();
      }}
    >
      <div className="flex flex-wrap items-end gap-4">
        <fieldset>
          <legend className="text-xs uppercase tracking-wide text-muted">Side</legend>
          <div className="mt-1 flex gap-2">
            {(["buy", "sell"] as const).map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={side === s}
                onClick={() => setSide(s)}
                className={`rounded-full border px-4 py-1.5 text-sm ${side === s ? "border-accent text-accent" : "border-rule text-muted"}`}
              >
                {s}
              </button>
            ))}
          </div>
        </fieldset>
        <label className="text-xs uppercase tracking-wide text-muted">
          Units
          <input className={`${field} mt-1 block w-24`} inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} />
        </label>
        <label className="text-xs uppercase tracking-wide text-muted">
          Limit price (cents, 1 to 99)
          <input className={`${field} mt-1 block w-28`} inputMode="numeric" value={cents} onChange={(e) => setCents(e.target.value)} />
        </label>
        <button className={btnAccent} type="submit" disabled={!valid || !trader || place.isPending}>
          {place.isPending ? "Placing…" : `Place ${side} order`}
        </button>
      </div>
      <p className="text-sm text-muted">
        {valid ? (
          <>
            {side === "buy" ? "Buying" : "Selling"} {q} unit{q === 1 ? "" : "s"} at up to {c}&cent; means a basis of{" "}
            <span className="font-mono">{signedF(basisF(priceE6, range))}</span>. You put {usd(lock)} aside until the auction clears; whatever
            the clearing price leaves over comes back.{" "}
            {side === "buy"
              ? "A buy pays more when the metro runs warmer than its station."
              : "A sell pays more when the metro runs cooler than its station."}
          </>
        ) : (
          "Units must be a whole number above zero; the price is a whole number of cents from 1 to 99."
        )}
      </p>
      {!trader && <p className="text-sm text-accent">Pick a trader above first.</p>}
      <ErrorLine error={place.error} />
      {place.isSuccess && !place.isPending && (
        <p className="text-sm text-muted">Order {place.data.orderId} placed ({place.data.status}).</p>
      )}
    </form>
  );
}
