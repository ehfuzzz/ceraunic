"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { tradingApi } from "@/lib/trading-api";
import { POLL_MS } from "@/lib/trading-queries";
import { utc } from "@/lib/trading-format";
import { btn, btnAccent, Empty, ErrorLine, field, Panel, Stat, td, th } from "./TradingKit";

const WEI = BigInt(10) ** BigInt(18);

/** Whole WI with thousands separators from an 18-decimal string (display only). */
function wi(wei: string): string {
  const v = BigInt(wei || "0");
  const whole = v / WEI;
  const frac = Number((v % WEI) / BigInt(10) ** BigInt(14)) / 10_000;
  return `${whole.toLocaleString("en-US")}${frac ? frac.toFixed(4).slice(1) : ""} WI`;
}

/**
 * WI staking, served by the engine's /staking routes (SPEC 8.7). Staked WI votes on pool settings and is cut
 * (burned) pro rata when the junior tranche loses money on a closed day, at most the cap per event; shares in
 * cooldown stay cuttable. Stakers earn nothing in v0.
 */
export function PoolStakingPanel({ owner }: { owner?: string | null }) {
  const qc = useQueryClient();
  const [amount, setAmount] = useState("1000");
  const view = useQuery({ queryKey: ["staking", owner], queryFn: () => tradingApi.staking(owner), refetchInterval: POLL_MS });
  const refresh = () => qc.invalidateQueries({ queryKey: ["staking"] });
  const n = Number(amount);
  const validAmount = Number.isInteger(n) && n > 0;
  const stake = useMutation({ mutationFn: () => tradingApi.stake(owner!, (BigInt(n) * WEI).toString()), onSuccess: refresh });
  const cool = useMutation({ mutationFn: () => tradingApi.unstakeRequest(owner!, view.data!.stakedShares), onSuccess: refresh });
  const claim = useMutation({ mutationFn: (id: number) => tradingApi.claimUnstake(owner!, id), onSuccess: refresh });
  const v = view.data;
  const hasWi = !!v && BigInt(v.wiBalanceWei) > BigInt(0);
  const hasStake = !!v && BigInt(v.stakedShares) > BigInt(0);
  return (
    <Panel title="WI staking" aside={v ? `cooldown ${v.cooldownDays} days · cut cap ${v.haircutCapBps / 100}% per event` : undefined}>
      <div className="max-w-2xl space-y-3 text-sm">
        <p>
          People who stake WI get a vote on the pool&rsquo;s settings. In return they sit behind the junior money: when the junior side loses
          money on a day, staked WI is cut by the same share and the cut WI is burned, never sold. Tokens in cooldown (after you ask to
          unstake) can still be cut until the cooldown ends. In the first version stakers are paid nothing.
        </p>
      </div>
      {view.error ? <ErrorLine error={view.error} /> : null}
      {v && (
        <>
          <div className="mt-4 grid max-w-2xl gap-4 sm:grid-cols-3">
            <Stat label="Total staked" value={wi(v.totalStakedWei)} />
            <Stat label="Your stake" value={wi(v.stakedValueWei)} sub={`voting power ${wi(v.votingPowerWei)}`} />
            <Stat label="Your WI balance" value={wi(v.wiBalanceWei)} />
          </div>
          <div className="mt-5 grid max-w-2xl gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-xs uppercase tracking-wide text-muted">Your stake</h3>
              {!owner ? (
                <Empty>Pick an acting address above to stake.</Empty>
              ) : (
                <form
                  className="mt-2 flex flex-wrap items-center gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (validAmount) stake.mutate();
                  }}
                >
                  <input className={field} value={amount} onChange={(e) => setAmount(e.target.value)} aria-label="WI to stake" />
                  <button className={btnAccent} disabled={!hasWi || !validAmount || stake.isPending}>
                    Stake WI
                  </button>
                  <button type="button" className={btn} disabled={!hasStake || cool.isPending} onClick={() => cool.mutate()}>
                    Start cooldown
                  </button>
                </form>
              )}
              {owner && !hasWi && !hasStake && (
                <p className="mt-2 text-xs text-muted">This address holds no WI in this world. Demo WI sits with the anvil demo accounts #4 to #9.</p>
              )}
              <ErrorLine error={stake.error ?? cool.error ?? claim.error} />
            </div>
            <div>
              <h3 className="text-xs uppercase tracking-wide text-muted">Cooldown and haircut history</h3>
              {v.cooldowns.length === 0 && v.haircuts.length === 0 ? (
                <div className="mt-2">
                  <Empty>Nothing to show. No cooldown is running and no haircut has been reported.</Empty>
                </div>
              ) : (
                <table className="mt-2 w-full">
                  <thead>
                    <tr>
                      <th className={th}>What</th>
                      <th className={th}>Amount</th>
                      <th className={th}>When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {v.cooldowns.map((c) => (
                      <tr key={`c${c.requestId}`}>
                        <td className={td}>Cooldown #{c.requestId}</td>
                        <td className={td}>{wi(c.valueWei)}</td>
                        <td className={td}>
                          {c.claimed ? (
                            "paid"
                          ) : c.claimable ? (
                            <button className={btn} onClick={() => claim.mutate(c.requestId)} disabled={claim.isPending}>
                              Claim
                            </button>
                          ) : (
                            `claimable ${utc(c.claimableAt)}`
                          )}
                        </td>
                      </tr>
                    ))}
                    {v.haircuts.map((h) => (
                      <tr key={`h${h.day}`}>
                        <td className={td}>Haircut {h.day}</td>
                        <td className={td}>
                          {wi(h.burnedWei)} ({h.bps / 100}%)
                        </td>
                        <td className={td}>burned</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </>
      )}
    </Panel>
  );
}
