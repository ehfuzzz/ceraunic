"use client";

// Policies, payouts (there are no claims to file: every covered day settles from the public record) and
// one policy in detail with each day's settlement status and the data vintage hash it settled on.
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api, type Policy, type Settlement } from "@/lib/api";
import { coreApi, explain } from "@/lib/core-api";
import { addDays } from "@/lib/sales/dates";
import { dayRange, level, PERIL_LABEL, settlesAt, settlementValue, trigger, usdE6, utc } from "@/lib/core-format";
import { useEngineMode, useHolder } from "@/lib/core-session";
import { useStationName } from "./BusinessCard";
import { HolderCard } from "./HolderCard";
import { Muted, Row, Stat } from "./ui";

const STATUS: Record<Settlement["status"], string> = { pending: "Pending", reported: "Reported", final: "Final", disputed: "Disputed", void: "Void (refunded)" };
const finalAt = (day: string) => `${addDays(day, 2)}T12:00:00Z`;
// The full 66-character hash pushed the payout column off screen; show its ends, keep the whole value in the tooltip.
const shortHash = (h: string) => (h.length > 20 ? `${h.slice(0, 10)}…${h.slice(-6)}` : h);
const paid = (p: Policy) => p.settlements.reduce((s, x) => s + x.payoutE6, 0);

function short(p: Policy) {
  if (p.peril === "heat") return `above ${level("heat", p.strikeTenthsF)}`;
  if (p.peril === "cold") return `below ${level("cold", p.strikeTenthsF)}`;
  return `$${p.units} per wet day`;
}

function ClockNote() {
  const cfg = useEngineMode();
  const isSim = cfg.data?.mode === "sim";
  const clock = useQuery({ queryKey: ["clock"], queryFn: () => coreApi.clock(), enabled: isSim });
  if (!isSim || !clock.data) return null;
  return (
    <p className="mt-2 text-xs text-muted" data-testid="demo-clock">
      Demo clock: {utc(clock.data.simTime)}. Settlements appear as the clock passes each day&apos;s final time; the Admin page
      moves the demo clock forward.
    </p>
  );
}

export function PoliciesView() {
  const holder = useHolder();
  const policies = useQuery({ queryKey: ["policies", holder.address], queryFn: () => coreApi.policies(holder.address!), enabled: !!holder.address });
  const settlements = useQuery({
    queryKey: ["policies", "settlements", holder.address],
    queryFn: () => api.settlements(holder.address!),
    enabled: !!holder.address,
  });

  return (
    <>
      <div className="mt-8 max-w-3xl">
        <HolderCard showBalance />
        <ClockNote />
      </div>

      <section className="mt-10 max-w-4xl">
        <h2 className="font-display text-xl tracking-tight">Policies</h2>
        {policies.error && <Muted className="mt-3">{explain(policies.error)}</Muted>}
        {policies.data && policies.data.length === 0 && (
          <Muted className="mt-3">
            No policies for this account yet. <Link href="/app/coverage">Get a quote on the Cover page.</Link>
          </Muted>
        )}
        {policies.data && policies.data.length > 0 && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm" data-testid="policy-table">
              <thead>
                <tr className="border-b border-rule text-left text-muted">
                  <th className="py-1.5 pr-3 font-normal">Policy</th>
                  <th className="py-1.5 pr-3 font-normal">Cover</th>
                  <th className="py-1.5 pr-3 font-normal">Days</th>
                  <th className="py-1.5 pr-3 text-right font-normal">Paid</th>
                  <th className="py-1.5 pr-3 text-right font-normal">Most it pays</th>
                  <th className="py-1.5 pr-3 text-right font-normal">Paid out so far</th>
                  <th className="py-1.5 font-normal">Status</th>
                </tr>
              </thead>
              <tbody>
                {policies.data.map((p) => (
                  <tr key={p.policyId} className="border-b border-rule/60" data-testid="policy-row">
                    <td className="py-1.5 pr-3 font-mono text-xs">
                      <Link href={`/app/policies/${p.policyId}`}>{p.policyId}</Link>
                    </td>
                    <td className="py-1.5 pr-3">
                      {PERIL_LABEL[p.peril]} {short(p)}
                      <span className="text-muted"> · {p.path === "house-hedge" ? "we hedge" : "you hedge"}</span>
                    </td>
                    <td className="py-1.5 pr-3">{dayRange(p.days)}</td>
                    <td className="py-1.5 pr-3 text-right">{usdE6(p.premiumE6)}</td>
                    <td className="py-1.5 pr-3 text-right">{usdE6(p.maxPayoutE6)}</td>
                    <td className="py-1.5 pr-3 text-right">{usdE6(paid(p))}</td>
                    <td className="py-1.5">{p.status === "active" ? "Active" : p.status === "settled" ? "Settled" : "Expired"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="mt-12 max-w-4xl">
        <h2 className="font-display text-xl tracking-tight">Payouts</h2>
        <Muted className="mt-2">
          There&apos;s nothing to file. Each covered day settles on its own from the public weather record, and the payout is added
          to this account.
        </Muted>
        {settlements.data && settlements.data.length === 0 && <Muted className="mt-3">No settled days yet.</Muted>}
        {settlements.data && settlements.data.length > 0 && <SettlementTable rows={settlements.data} showRef />}
        {settlements.error && <Muted className="mt-3">{explain(settlements.error)}</Muted>}
      </section>
    </>
  );
}

function SettlementTable({ rows, showRef }: { rows: Settlement[]; showRef?: boolean }) {
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-rule text-left text-muted">
            <th className="py-1.5 pr-3 font-normal">Day</th>
            {showRef && <th className="py-1.5 pr-3 font-normal">Policy</th>}
            <th className="py-1.5 pr-3 font-normal">Reading</th>
            <th className="py-1.5 pr-3 font-normal">Source</th>
            <th className="py-1.5 pr-3 font-normal">Data version</th>
            <th className="py-1.5 pr-3 font-normal">Status</th>
            <th className="py-1.5 text-right font-normal">Payout</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.refId} className="border-b border-rule/60" data-testid="settlement-row">
              <td className="py-1.5 pr-3 font-mono text-xs">{s.day}</td>
              {showRef && (
                <td className="py-1.5 pr-3 font-mono text-xs">
                  <Link href={`/app/policies/${s.refId.split(":")[0]}`}>{s.refId.split(":")[0]}</Link>
                </td>
              )}
              <td className="py-1.5 pr-3">
                {settlementValue(s.unit, s.value)} <span className="text-muted">({s.index})</span>
              </td>
              <td className="py-1.5 pr-3">{s.source}</td>
              <td className="py-1.5 pr-3 font-mono text-xs" title={`Hash of the exact data release this day settled on: ${s.vintageHash}`}>
                {shortHash(s.vintageHash)}
              </td>
              <td className="py-1.5 pr-3">{STATUS[s.status]}</td>
              <td className="py-1.5 text-right">{usdE6(s.payoutE6)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PolicyDetail({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["policies", "one", id], queryFn: () => coreApi.policy(id) });
  const biz = useQuery({ queryKey: ["business", q.data?.businessId], queryFn: () => coreApi.business(q.data!.businessId), enabled: !!q.data });
  const station = useStationName(biz.data?.settlementStation);
  const tempWhere = station?.name ?? biz.data?.settlementStation ?? "the settlement station";
  const where = q.data ? settlesAt(q.data.peril, biz.data, tempWhere) : tempWhere;

  if (q.error) return <Muted className="mt-6">{explain(q.error)}</Muted>;
  if (!q.data) return <Muted className="mt-6">Loading…</Muted>;
  const p = q.data;
  const byDay = new Map(p.settlements.map((s) => [s.day, s]));

  return (
    <div className="mt-6 max-w-4xl" data-testid="policy-detail">
      <p className="text-[15px]">{trigger(p.peril, p.strikeTenthsF, p.capTenthsF, where, p.units)}</p>
      <ClockNote />
      <div className="mt-6 grid grid-cols-2 gap-5 sm:grid-cols-4">
        <Stat label="Status" value={p.status === "active" ? "Active" : p.status === "settled" ? "Settled" : "Expired"} testId="policy-status" />
        <Stat label="Paid" value={usdE6(p.premiumE6)} />
        <Stat label="Paid out so far" value={usdE6(paid(p))} />
        <Stat label="Most it can pay out" value={usdE6(p.maxPayoutE6)} />
      </div>
      <div className="mt-6 max-w-2xl">
        <Row k="Business" v={biz.data ? `${biz.data.name} (${p.businessId})` : p.businessId} />
        <Row k="Path" v={p.path === "house-hedge" ? "We handle the hedge" : "You place the Kalshi part"} />
        <Row k={p.peril === "rain" ? "Dollars per wet day" : "Units per day (each pays up to $1)"} v={p.units} />
        <Row k="Days covered" v={dayRange(p.days)} />
        <Row k="Holder" v={p.holder} mono />
      </div>

      <h2 className="mt-10 font-display text-xl tracking-tight">Day by day</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-muted">
              <th className="py-1.5 pr-3 font-normal">Day</th>
              <th className="py-1.5 pr-3 font-normal">Reading</th>
              <th className="py-1.5 pr-3 font-normal">Data version</th>
              <th className="py-1.5 pr-3 font-normal">Status</th>
              <th className="py-1.5 text-right font-normal">Payout</th>
            </tr>
          </thead>
          <tbody>
            {p.days.map((d) => {
              const s = byDay.get(d);
              return (
                <tr key={d} className="border-b border-rule/60" data-testid={s ? "settlement-row" : "pending-row"}>
                  <td className="py-1.5 pr-3 font-mono text-xs">{d}</td>
                  <td className="py-1.5 pr-3">{s ? `${settlementValue(s.unit, s.value)} (${s.source})` : "–"}</td>
                  <td className="py-1.5 pr-3 font-mono text-xs" title={s?.vintageHash}>{s ? shortHash(s.vintageHash) : "–"}</td>
                  <td className="py-1.5 pr-3">{s ? STATUS[s.status] : `Final ${utc(finalAt(d))}`}</td>
                  <td className="py-1.5 text-right">{s ? usdE6(s.payoutE6) : "–"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-muted">
        Data version is a hash of the exact weather-data release the day settled on, so anyone can check the number later even if
        the weather service revises it.
      </p>
      <Link href="/app/policies" className="mt-6 inline-block !text-accent">
        All policies
      </Link>
    </div>
  );
}
