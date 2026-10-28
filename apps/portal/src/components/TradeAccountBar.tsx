"use client";

// Who is trading. A connected wallet wins; in sim mode with no wallet you can pick an address.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { isAddress } from "viem";
import { api } from "@/lib/api";
import { usd, short } from "@/lib/trading-format";
import { randomSimAddress, useTradingAccount } from "@/lib/trading-store";
import { POLL_MS, useEngineConfig } from "@/lib/trading-queries";
import { btn, ErrorLine, field, Stat } from "./TradingKit";

export function TradeAccountBar() {
  const acct = useTradingAccount();
  const cfg = useEngineConfig();
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const isSim = cfg.data?.mode === "sim";

  const balances = useQuery({
    queryKey: ["balances", acct.address],
    queryFn: () => api.balances(acct.address!),
    enabled: !!acct.address,
    refetchInterval: POLL_MS,
  });
  const faucet = useMutation({
    mutationFn: () => api.faucet(acct.address!, 1_000 * 1_000_000),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["balances"] }),
  });

  if (!acct.address) {
    const valid = isAddress(draft);
    return (
      <div className="border border-rule px-4 py-4">
        <p className="text-sm">
          {isSim
            ? "No wallet connected. In the simulated chain you can trade as any address. Pick one, or connect a wallet above."
            : "Connect a wallet to trade."}
        </p>
        {isSim && (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <input
              aria-label="Sim trader address"
              className={`${field} w-96 max-w-full`}
              placeholder="0x… (40 hex characters)"
              value={draft}
              onChange={(e) => setDraft(e.target.value.trim())}
            />
            <button className={btn} disabled={!valid} onClick={() => acct.setSimAddress(draft)}>
              Use this address
            </button>
            <button className={btn} onClick={() => acct.setSimAddress(randomSimAddress())}>
              Make a new one
            </button>
          </div>
        )}
      </div>
    );
  }

  const b = balances.data;
  return (
    <div className="flex flex-wrap items-end gap-x-10 gap-y-4 border border-rule px-4 py-4">
      <Stat
        label={acct.source === "wallet" ? "Wallet" : "Sim trader"}
        value={<span title={acct.address}>{short(acct.address)}</span>}
        sub={
          acct.source === "sim" ? (
            <button className="underline" onClick={() => acct.setSimAddress(null)}>
              change
            </button>
          ) : undefined
        }
      />
      <Stat label="USDC" value={b ? usd(b.usdcE6) : "…"} />
      <Stat label="Locked" value={b ? usd(b.lockedE6) : "…"} />
      {isSim && (
        <div>
          <button className={btn} disabled={faucet.isPending} onClick={() => faucet.mutate()}>
            Get 1,000 test USDC
          </button>
        </div>
      )}
      <ErrorLine error={faucet.error ?? balances.error} />
    </div>
  );
}
