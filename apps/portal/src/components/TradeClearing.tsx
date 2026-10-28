"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Auction, ClearingResult } from "@/lib/api";
import { tradingApi } from "@/lib/trading-api";
import { useAdminToken } from "@/lib/trading-store";
import { short, UNIT_E6, usd } from "@/lib/trading-format";
import { btn, btnAccent, ErrorLine, td, th } from "./TradingKit";
import { TradePrice } from "./TradePrice";

export function TradeClearButton({ auction, isSim, onCleared }: { auction: Auction; isSim: boolean; onCleared?: () => void }) {
  const qc = useQueryClient();
  const { token } = useAdminToken();
  const clear = useMutation({
    mutationFn: (override: boolean) => tradingApi.clearAuction(auction.auctionId, override ? token : null),
    onSuccess: () => {
      onCleared?.();
      for (const key of ["auction", "auctions", "balances", "positions", "pool"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });

  if (auction.status === "cleared") return null;
  const open = auction.status === "open";
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        {open ? (
          <>
            <button className={btn} disabled title="Anyone can clear once the public cutoff has passed">
              Clear auction
            </button>
            {isSim && (
              <button className={btnAccent} disabled={!token || clear.isPending} onClick={() => clear.mutate(true)}>
                Clear early (admin)
              </button>
            )}
            <span className="text-sm text-muted">
              {isSim && !token
                ? "Anyone can clear after the cutoff. To clear early in the sim, enter the admin token on the Admin page."
                : "Anyone can clear after the cutoff."}
            </span>
          </>
        ) : (
          <>
            <button className={btnAccent} disabled={clear.isPending} onClick={() => clear.mutate(false)}>
              {clear.isPending ? "Clearing…" : "Clear auction"}
            </button>
            <span className="text-sm text-muted">The cutoff has passed, so anyone can press this. It needs no admin rights.</span>
          </>
        )}
      </div>
      <ErrorLine error={clear.error} />
    </div>
  );
}

export function TradeClearingResult({ result, range }: { result: ClearingResult; range: number }) {
  const { longLockedE6, shortLockedE6, ok } = result.conservation;
  // Recompute instead of trusting the engine's flag: long money plus short money must equal exactly
  // one USDC per filled unit, or the clearing created or destroyed value.
  const expected = result.filledQty * UNIT_E6;
  const balanced = longLockedE6 + shortLockedE6 === expected;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-x-10 gap-y-3">
        <div>
          <div className="text-xs uppercase tracking-wide text-muted">Clearing price</div>
          <div className="mt-1 text-lg">
            <TradePrice priceE6={result.priceE6} range={range} />
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-muted">Units traded</div>
          <div className="mt-1 font-mono text-lg">{result.filledQty}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-muted">Pool took</div>
          <div className="mt-1 font-mono text-lg">{result.poolFilledQty}</div>
        </div>
      </div>
      {result.priceE6 == null && <p className="text-sm text-muted">Nothing traded: no buy and sell crossed.</p>}
      <p className={`text-sm ${ok && balanced ? "text-muted" : "text-accent"}`} role={ok && balanced ? undefined : "alert"}>
        Conservation check: long side locks {usd(longLockedE6)}, short side locks {usd(shortLockedE6)}; together {usd(longLockedE6 + shortLockedE6)},
        and {result.filledQty} unit{result.filledQty === 1 ? "" : "s"} at $1 is {usd(expected)}.{" "}
        {ok && balanced ? "They match, so no value was created or lost." : "THEY DO NOT MATCH. Do not trust this clearing."}
      </p>
      {result.fills.length > 0 && (
        <table className="w-full max-w-xl border-collapse">
          <thead>
            <tr className="border-b border-rule">
              <th className={th}>Order</th>
              <th className={th}>Trader</th>
              <th className={th}>Side</th>
              <th className={th}>Units filled</th>
            </tr>
          </thead>
          <tbody>
            {result.fills.map((f) => (
              <tr key={f.orderId} className="border-b border-rule">
                <td className={`${td} font-mono`}>{f.orderId}</td>
                <td className={`${td} font-mono`}>{short(f.trader)}</td>
                <td className={td}>{f.side}</td>
                <td className={`${td} font-mono`}>{f.qty}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
