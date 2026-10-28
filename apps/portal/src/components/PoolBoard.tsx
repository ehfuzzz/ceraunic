"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type QueueTicket } from "@/lib/api";
import { pct, short, usd, utc } from "@/lib/trading-format";
import { POLL_MS, useContractInfo, useSimClock } from "@/lib/trading-queries";
import { useTradingAccount } from "@/lib/trading-store";
import { AdminModeBanner } from "./AdminModeBanner";
import { CancelWithdrawButton, PoolDepositForm, PoolWithdrawForm } from "./PoolMoneyForms";
import { PoolNavChart } from "./PoolNavChart";
import { PoolStakingPanel } from "./PoolStakingPanel";
import { TradeAccountBar } from "./TradeAccountBar";
import { Bar, Empty, ErrorLine, Panel, Stat, td, th } from "./TradingKit";

// One whole share is 1e12 raw units (6 USDC decimals + the 1e6 virtual offset, SPEC 8.2); assets are in
// USDC base units (1e6). Value of one whole share in USDC, the same scale as the chart below.
const SHARE_RAW = 1e12;
function nav(assetsE6: number, shares: number) {
  return shares > 0 ? ((assetsE6 / 1e6) / (shares / SHARE_RAW)).toFixed(4) : "—";
}

function Queue({ title, tickets, me, now }: { title: string; tickets: QueueTicket[]; me: string | null; now?: string | null }) {
  const withdrawals = now !== undefined; // the withdrawals table passes the sim clock: claim-by column + Cancel before maturity
  return (
    <div>
      <h3 className="text-xs uppercase tracking-wide text-muted">{title}</h3>
      {tickets.length === 0 ? (
        <div className="mt-2">
          <Empty>Empty.</Empty>
        </div>
      ) : (
        <table className="mt-1 w-full border-collapse">
          <thead>
            <tr className="border-b border-rule">
              <th className={th}>Ticket</th>
              <th className={th}>Owner</th>
              <th className={th}>Tranche</th>
              <th className={th}>Size</th>
              <th className={th} title="Deposits: when the money went in. Withdrawals: when the delay ends and the next daily pool epoch pays it.">
                When
              </th>
              {withdrawals && (
                <th className={th} title="After this time the request lapses: your shares come back to you and no money moves.">
                  Claim by
                </th>
              )}
              <th className={th}>Status</th>
              {withdrawals && <th className={th} />}
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr key={t.ticketId} className={`border-b border-rule ${me && t.owner.toLowerCase() === me.toLowerCase() ? "bg-surface" : ""}`}>
                <td className={`${td} font-mono`}>{t.ticketId}</td>
                <td className={`${td} font-mono`}>{short(t.owner)}</td>
                <td className={td}>{t.tranche}</td>
                <td className={`${td} font-mono`}>{t.amountE6 != null ? usd(t.amountE6) : `${t.shares} sh`}</td>
                <td className={`${td} font-mono`}>{utc(t.epochTs)}</td>
                {withdrawals && <td className={`${td} font-mono`}>{t.claimBy ? utc(t.claimBy) : "—"}</td>}
                <td className={td}>{t.status}</td>
                {withdrawals && (
                  <td className={td}>
                    {me && t.requestId != null && t.status === "queued" && t.owner.toLowerCase() === me.toLowerCase() &&
                      now != null && Date.parse(now) < Date.parse(t.epochTs) && <CancelWithdrawButton owner={me} requestId={t.requestId} />}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function PoolBoard() {
  const info = useContractInfo();
  const acct = useTradingAccount();
  const pool = useQuery({ queryKey: ["pool"], queryFn: () => api.pool(), refetchInterval: POLL_MS });
  const mine = useQuery({
    queryKey: ["positions", acct.address],
    queryFn: () => api.positions(acct.address!),
    enabled: !!acct.address,
    refetchInterval: POLL_MS,
  });
  const clock = useSimClock();
  const p = pool.data;
  const bal = mine.data?.balances;

  return (
    <div className="max-w-5xl">
      <h1 className="font-display text-3xl tracking-tight">Pool</h1>
      <p className="mt-4 max-w-2xl text-muted">
        The pool is the money that backs the weather cover we sell and takes the other side of the leftover risk traded on the Trade page. It
        has two tranches, and they lose money in a fixed order.
      </p>
      <div className="mt-4 max-w-2xl space-y-2 text-sm">
        <p>
          <strong className="font-medium">Junior loses first.</strong> Junior is the house&rsquo;s own money. Every loss comes out of it until
          it is gone.
        </p>
        <p>
          <strong className="font-medium">Senior loses only after that.</strong> Outside depositors go in senior. They are paid a set rate for
          sitting behind junior, and they only lose if the junior money is wiped out first.
        </p>
      </div>

      <div className="mt-8">
        <AdminModeBanner />
        <TradeAccountBar />
      </div>
      <ErrorLine error={pool.error} />

      {p && (
        <>
          <Panel title="Tranches">
            <div className="grid gap-8 sm:grid-cols-2">
              <div>
                <h3 className="text-xs uppercase tracking-wide text-muted">Senior (paid a set rate, loses second)</h3>
                <div className="mt-3 flex flex-wrap gap-x-10 gap-y-3">
                  <Stat label="Assets" value={usd(p.seniorAssetsE6)} />
                  <Stat label="Shares" value={p.seniorShares.toLocaleString("en-US")} />
                  <Stat label="Value per share" value={nav(p.seniorAssetsE6, p.seniorShares)} />
                  <Stat label="Senior rate" value={pct(p.seniorRateBp)} sub={`${p.seniorRateBp} bp`} />
                </div>
              </div>
              <div>
                <h3 className="text-xs uppercase tracking-wide text-muted">Junior (house money, loses first)</h3>
                <div className="mt-3 flex flex-wrap gap-x-10 gap-y-3">
                  <Stat label="Assets" value={usd(p.juniorAssetsE6)} />
                  <Stat label="Shares" value={p.juniorShares.toLocaleString("en-US")} />
                  <Stat label="Value per share" value={nav(p.juniorAssetsE6, p.juniorShares)} />
                </div>
              </div>
            </div>
          </Panel>

          <Panel title="Utilisation" aside="money set aside for open positions, out of all pool assets">
            <div className="max-w-xl">
              <Bar fraction={p.utilizationBp / 10_000} label="Pool utilisation" />
              <div className="mt-3 flex flex-wrap gap-x-10 gap-y-3">
                <Stat label="Utilisation" value={pct(p.utilizationBp)} />
                <Stat label="Locked" value={usd(p.lockedE6)} />
                <Stat label="Free" value={usd(p.freeE6)} />
              </div>
            </div>
          </Panel>

          <Panel title="Value per share over time">
            <PoolNavChart points={p.navHistory} />
          </Panel>

          <Panel title="Exposure by contract" aside="net units the pool holds after trading">
            {p.exposureByContract.length === 0 ? (
              <Empty>No exposure yet. It appears after an auction clears with orders in it.</Empty>
            ) : (
              <table className="w-full max-w-xl border-collapse">
                <thead>
                  <tr className="border-b border-rule">
                    <th className={th}>Market</th>
                    <th className={th}>Net units</th>
                    <th className={th}>Locked</th>
                  </tr>
                </thead>
                <tbody>
                  {p.exposureByContract.map((e) => (
                    <tr key={e.contractId} className="border-b border-rule">
                      <td className={td}>
                        {info.contractCity(e.contractId)}
                        <div className="font-mono text-xs text-muted">{e.contractId}</div>
                      </td>
                      <td className={`${td} font-mono`}>{e.netQty > 0 ? `+${e.netQty} long` : e.netQty < 0 ? `${e.netQty} short` : "0"}</td>
                      <td className={`${td} font-mono`}>{usd(e.lockedE6)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          <Panel title="Your deposits">
            {acct.address && bal && (
              <p className="mb-5 text-sm text-muted">
                You hold {bal.seniorShares} senior and {bal.juniorShares} junior shares.
              </p>
            )}
            <div className="grid gap-10 md:grid-cols-2">
              <PoolDepositForm owner={acct.address} />
              <PoolWithdrawForm owner={acct.address} seniorShares={bal?.seniorShares ?? 0} juniorShares={bal?.juniorShares ?? 0} />
            </div>
          </Panel>

          <Panel title="Deposits and withdrawals" aside="deposits go in at once; withdrawals wait out the delay, then must be paid within 3 days or they lapse; yours are shaded">
            <div className="grid gap-8">
              <Queue title="Deposits" tickets={p.queue.deposits} me={acct.address} />
              <Queue title="Withdrawals" tickets={p.queue.withdrawals} me={acct.address} now={clock.data?.simTime ?? null} />
            </div>
          </Panel>
        </>
      )}

      <PoolStakingPanel owner={acct.address} />
    </div>
  );
}
