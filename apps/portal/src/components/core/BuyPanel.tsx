"use client";

// Buy one quote. The engine answers with an Execution envelope: "done" in sim (and anvil with server
// signing), "needs_signature" on testnet, in which case execute.ts walks the wallet through each tx.
import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type HedgePath, type Policy, type Quote } from "@/lib/api";
import { coreApi, explain } from "@/lib/core-api";
import { dayRange, PERIL_LABEL, shortAddr, trigger, usdE6 } from "@/lib/core-format";
import { useEngineMode, useHolder } from "@/lib/core-session";
import type { Step } from "@/lib/execute";
import { HolderCard } from "./HolderCard";
import { btn, btnPrimary, ErrorLine, Row } from "./ui";

const PHASE: Record<Step["phase"], string> = {
  switching: "Switching your wallet to the right chain",
  signing: "Waiting for you to sign in your wallet",
  waiting: "Waiting for the block",
  confirming: "Reading the result",
};

export function BuyPanel({ quote, path, where, onRequote }: { quote: Quote; path: HedgePath; where: string; onRequote: () => void }) {
  const holder = useHolder();
  const cfg = useEngineMode();
  const qc = useQueryClient();
  const [step, setStep] = useState<Step | null>(null);
  const balance = useQuery({ queryKey: ["balances", holder.address], queryFn: () => api.balances(holder.address!), enabled: !!holder.address });
  const short = balance.data ? Math.max(0, quote.premiumE6 - balance.data.usdcE6) : 0;

  const buy = useMutation({
    mutationFn: () => coreApi.buyPolicy({ quoteId: quote.quoteId, holder: holder.address! }, setStep),
    onSettled: () => {
      setStep(null);
      qc.invalidateQueries({ queryKey: ["balances"] });
      qc.invalidateQueries({ queryKey: ["policies"] });
    },
  });
  const expired = buy.error ? explain(buy.error).startsWith("That price has expired") : false;

  if (buy.data) return <Receipt policy={buy.data.policy} mode={buy.data.mode} hashes={buy.data.hashes} quote={quote} path={path} where={where} />;

  return (
    <div className="max-w-2xl">
      <HolderCard showBalance />
      <div className="mt-4">
        <Row k="Path" v={path === "house-hedge" ? "We handle the hedge" : "You place the Kalshi part"} />
        <Row k="You pay now" v={usdE6(quote.premiumE6)} />
        <Row k="Most it can pay out" v={usdE6(quote.maxPayoutE6)} />
      </div>
      {short > 0 && (
        <p className="mt-3 text-sm text-muted">
          This account needs {usdE6(short)} more {cfg.data?.mode === "sim" ? "test USDC. Use the button above to add some." : "USDC."}
        </p>
      )}
      <div className="mt-4 flex items-center gap-3">
        <button type="button" className={btnPrimary} disabled={!holder.address || buy.isPending} onClick={() => buy.mutate()} data-testid="buy-button">
          {buy.isPending ? "Buying…" : `Buy for ${usdE6(quote.premiumE6)}`}
        </button>
        {expired && (
          <button type="button" className={btn} onClick={onRequote}>
            Get a fresh quote
          </button>
        )}
      </div>
      {step && (
        <p className="mt-3 text-sm" data-testid="exec-step">
          Step {step.index} of {step.total}, {step.description}: {PHASE[step.phase]}…
        </p>
      )}
      <ErrorLine error={buy.error ? explain(buy.error) : null} />
    </div>
  );
}

function Receipt({
  policy,
  mode,
  hashes,
  quote,
  path,
  where,
}: {
  policy: Policy;
  mode: string;
  hashes: string[];
  quote: Quote;
  path: HedgePath;
  where: string;
}) {
  return (
    <div className="max-w-2xl border border-accent p-5" data-testid="exec-status-done">
      <p className="font-display text-lg">Done. {PERIL_LABEL[policy.peril]} cover is active.</p>
      <p className="mt-2 text-[15px]">{trigger(policy.peril, policy.strikeTenthsF, policy.capTenthsF, where, policy.units)}</p>
      <div className="mt-4">
        <Row k="Policy" v={<span data-testid="receipt-policy-id">{policy.policyId}</span>} mono />
        <Row k="Holder" v={shortAddr(policy.holder)} mono />
        <Row k="Days covered" v={dayRange(policy.days)} />
        <Row k={policy.peril === "rain" ? "Dollars per wet day" : "Units per day"} v={policy.units} />
        <Row k="Paid" v={usdE6(policy.premiumE6)} />
        <Row k="Most it can pay out" v={usdE6(policy.maxPayoutE6)} />
        <Row k="How it was recorded" v={mode === "sim" ? "simulated chain" : `${hashes.length} transaction${hashes.length === 1 ? "" : "s"} on ${mode}`} />
        {hashes.map((h) => (
          <Row key={h} k="Transaction" v={h} mono />
        ))}
      </div>
      <p className="mt-4 text-sm text-muted">
        There&apos;s nothing to file. Each covered day settles from the National Weather Service daily report for {where}. The
        number is final two days later at 12:00 UTC, and any payout lands in this account then.
      </p>
      {path === "business-ladder" && (
        <p className="mt-3 border-l-2 border-accent pl-3 text-sm">
          Reminder: place the Kalshi rungs yourself ({(quote.ladderForBusiness ?? []).map((r) => r.ticker).join(", ")} for the first
          day). We never place them for you.
        </p>
      )}
      <Link href={`/app/policies/${policy.policyId}`} className="mt-4 inline-block !text-accent" data-testid="receipt-policy-link">
        See this policy
      </Link>
    </div>
  );
}
