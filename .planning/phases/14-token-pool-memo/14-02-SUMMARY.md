---
phase: 14-token-pool-memo
plan: 02
status: complete (two pre-registered section-5 items open, see below)
files: [reports/pitch/14-TOKEN-POOL-MEMO.md]
---
# 14-02 Summary: real numbers in the token + pool memo

**What changed.** Section 5 filled. The 30 % haircut cap and 10-day delays are now stated as SPEC §17 open parameters (v0 `haircutCapBps` 3000; `withdrawDelay`/`unstakeCooldown`/`houseReturnWindow` 10 d). §1 rewritten: HE_cover 0.95 is no longer the lead, the day-ahead cost is stated, Kalshi depth is small next to the leftover (33–55 units vs ~4,400 at NYC), and the pool is the counterparty for most flow. §2 now matches SPEC §8.3/§8.6/§11: two layers, max payout reserved in cash, fee first, senior 20 % of net premium, junior gets the rest plus all hedge P&L. The old "house P&L stays in the house's account" line contradicted SPEC and is gone. §3 cut is per day. §4 is shortened to one line per rule; the full text moved to Appendix H. §6 table moved to Appendix G, with three new rows. §7 seed rule now cites the $206k junior target and says the $1.5M seed line exceeds it. §8 revised. New appendices: E (numbers + keys), F (deviations/open), G, H. 22 footnotes carry file + key.

**Six numbers** (H = reports/eval-04-05/handoff.json, R4 = reports/eval-04-05/results.json, E1 = reports/eval-01/results.json, E6 = reports/eval-06/results.json)
1. Capital per $ of pool notional at H30: 0.126 [H `capital_per_usd_cover_H30.per_usd_pool_notional_both_legs`]. Station leg only: 0.251. Climatology-priced: 0.177 both legs / 0.360 station leg [`..._clim_priced_*`]. C_30 $412k [H `C30_usd`].
2. Junior share 0.501, junior ES95 $206k [H `junior_share`, `junior_ES95_30d_usd`]. Worst 1-day loss $34.8k [H `capital_H.H1.worst_window`].
3. Fee per $ notional: 10/25/50 bps = 0.001/0.0025/0.005; CoW50 0.0040 [H `fee_income_per_usd_notional.*`]. Per season: $22k / $56k / $112k / $90k [H `fee_income_per_season_usd.*`].
4. Netting: central pooled 0.396 (3 of 5 stations ≥ 0.25); null 0.019 [H `netting_ratio.central.*`, `netting_ratio.null.pooled`].
5. Worst 30-day window $412k; ES99 $269k [H `worst_window_30d_usd`, `ES99_30d_usd`].
6. HE_ladder / HE_cover by group, G1–G5: 0.006/0.072, 0.001/0.053, −0.001/0.009, 0.001/−0.001, −0.000/−0.006 [E6 `verdicts.T3.G*.ladder_median`, `groups.G*.primary.arms.A3.ladder_heat_rain_daily.median`, `verdicts.T2.G*.heat_rain_median`]. Station ladders: HE_ladder −0.32 pooled [E1 `verdicts.T1b.he_ladder`], 0.37 for 2025+ [E1 `temperature.pooled[2].he_ladder.est`].
Also cited: house P&L +$1,154/day primary vs +$384/day trailing-5 [H `house_markout_mean_daily_usd.*`]; season returns on C_30 [R4 `pool_return.*`].

**Word count.** Main text (§1–8) is 2,500 words counting tables and the diagram, and 2,360 counting prose only. Appendices and footnotes are extra.
**Banned-word grep** (14-01 list, plus revolution/game-chang/cutting-edge/transformative/value proposition/go-to-market/effortless/allows us to): 0 hits. The word "placeholder" no longer appears anywhere in the memo.

**Open for the owner**
- Junior return in a median, 1-in-20 and worst year, and the premium split at 10 %/20 % treasury cuts (14-RESEARCH rules 4–5): Phase 4 computed neither. Four seasons can't give a 1-in-20 year, and 2026 was −23 %. This needs a Phase 4 add-on run.
- Deviations logged in Appendix F. The capital-per-$ definition is Phase 4's, not rule 3's. The junior target uses the pooled worst 1-day loss, because there is no per-metro worst day and no pilot book yet.
- The $1.5M seed line ($300–450k) is more than the simulated book's junior target. You may want to cut it.
- The haircut cap and lock lengths are still unset (SPEC §17 lists them as Phase 14 TODOs). No stress test has picked values yet.
- §4 was moved to an appendix to meet the word limit. If you want the full precedent stories in the main text, the limit has to go up.
