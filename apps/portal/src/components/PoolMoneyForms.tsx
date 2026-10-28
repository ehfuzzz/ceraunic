"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Tranche } from "@/lib/api";
import { usd } from "@/lib/trading-format";
import { btnAccent, ErrorLine, field } from "./TradingKit";

function TranchePick({ value, onChange }: { value: Tranche; onChange: (t: Tranche) => void }) {
  return (
    <div className="flex gap-2" role="group" aria-label="Tranche">
      {(["senior", "junior"] as const).map((t) => (
        <button
          key={t}
          type="button"
          aria-pressed={value === t}
          onClick={() => onChange(t)}
          className={`rounded-full border px-3 py-1 text-sm ${value === t ? "border-accent text-accent" : "border-rule text-muted"}`}
        >
          {t}
        </button>
      ))}
    </div>
  );
}

export function PoolDepositForm({ owner }: { owner: string | null }) {
  const qc = useQueryClient();
  const [tranche, setTranche] = useState<Tranche>("senior");
  const [dollars, setDollars] = useState("100");
  const n = Number(dollars);
  const valid = Number.isFinite(n) && n > 0;
  const m = useMutation({
    mutationFn: () => api.poolDeposit({ owner: owner!, tranche, amountE6: Math.round(n * 1e6) }),
    onSuccess: () => {
      for (const k of ["pool", "balances", "positions"]) qc.invalidateQueries({ queryKey: [k] });
    },
  });
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        m.mutate();
      }}
    >
      <h3 className="text-xs uppercase tracking-wide text-muted">Deposit</h3>
      <TranchePick value={tranche} onChange={setTranche} />
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs uppercase tracking-wide text-muted">
          Amount (USDC)
          <input className={`${field} mt-1 block w-32`} inputMode="decimal" value={dollars} onChange={(e) => setDollars(e.target.value)} />
        </label>
        <button className={btnAccent} disabled={!owner || !valid || m.isPending}>
          Deposit
        </button>
      </div>
      <p className="text-sm text-muted">
        Money goes in right away: you get shares at today&apos;s value per share. Taking it out is a withdrawal request (below).
        {tranche === "junior" && " On testnet only the house can add junior money. The sim lets you try it."}
      </p>
      <ErrorLine error={m.error} />
      {m.data && (
        <p className="text-sm text-muted">
          Deposited {usd(m.data.amountE6 ?? 0)} into the {m.data.tranche} tranche (ticket {m.data.ticketId}).
        </p>
      )}
    </form>
  );
}

/** Cancel a still-waiting withdrawal (before its delay ends); the shares go back to the LP. */
export function CancelWithdrawButton({ owner, requestId }: { owner: string; requestId: string }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => api.poolWithdrawCancel(requestId, owner),
    onSuccess: () => {
      for (const k of ["pool", "balances", "positions"]) qc.invalidateQueries({ queryKey: [k] });
    },
  });
  return (
    <span>
      <button type="button" className={btnAccent} disabled={m.isPending} onClick={() => m.mutate()}>
        Cancel
      </button>
      <ErrorLine error={m.error} />
    </span>
  );
}

export function PoolWithdrawForm({ owner, seniorShares, juniorShares }: { owner: string | null; seniorShares: number; juniorShares: number }) {
  const qc = useQueryClient();
  const [tranche, setTranche] = useState<Tranche>("senior");
  const [shares, setShares] = useState("10");
  const n = Number(shares);
  const have = tranche === "senior" ? seniorShares : juniorShares;
  const valid = Number.isInteger(n) && n > 0 && n <= have;
  const m = useMutation({
    mutationFn: () => api.poolWithdraw({ owner: owner!, tranche, shares: n }),
    onSuccess: () => {
      for (const k of ["pool", "balances", "positions"]) qc.invalidateQueries({ queryKey: [k] });
    },
  });
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        m.mutate();
      }}
    >
      <h3 className="text-xs uppercase tracking-wide text-muted">Withdraw</h3>
      <TranchePick value={tranche} onChange={setTranche} />
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs uppercase tracking-wide text-muted">
          Shares (you hold {have})
          <input className={`${field} mt-1 block w-32`} inputMode="numeric" value={shares} onChange={(e) => setShares(e.target.value)} />
        </label>
        <button className={btnAccent} disabled={!owner || !valid || m.isPending}>
          Request withdrawal
        </button>
      </div>
      <p className="text-sm text-muted">
        A withdrawal waits out the withdrawal delay, then the next daily pool epoch pays it at that day&rsquo;s value per share, from cash
        only, so a rush of withdrawals can&rsquo;t drain money that is backing open cover. A loss during the delay hits the leaver too.
        You can cancel until the delay ends. If the pool can&rsquo;t pay it within 3 days after that (the &ldquo;claim by&rdquo; time),
        the request lapses and your shares simply come back to you.
      </p>
      <ErrorLine error={m.error} />
      {m.data && (
        <p className="text-sm text-muted">
          Queued {m.data.shares} {m.data.tranche} shares (ticket {m.data.ticketId}).
        </p>
      )}
    </form>
  );
}
