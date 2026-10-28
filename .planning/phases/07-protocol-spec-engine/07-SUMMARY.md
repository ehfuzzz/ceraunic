# 07-ENGINE SUMMARY — reference engine, fixture run, parity vectors (2026-09-30)

**Shipped.** `src/wi/engine/`: `events` (SPEC §13 catalogue, frozen dataclasses, strict int/addr/b32 checks), `log` (hash chain), `state`, `reducer` (Ledger: emit / apply_line / replay / replay_from_snapshot, invariants after every event), `invariants` (I1–I12, I15, plus a house-wallet identity), `markets`, `auction`, `policy` (quotes, buy, bind, settle, void, strips, positions), `pool`, `staking`, `oracle`, `hedge`, `pricing`, `margin` (C3–C5), `rfq`, `house_mm`, `eip712`, `scenario` (30-day run), `parity`. Plus `scripts/engine_fixture_run.py`, `tests/engine/` (7 files, 19 tests), `tests/engine/fixtures/nyc_30d_inputs.json` (164 KB), `reports/engine/fixture-run/{MANIFEST.json, events.jsonl (1.0 MB), daily_pnl.csv, world.json}` and 8 files in `contracts/test/fixtures/`. Nothing else under contracts/ was touched.
**Reuse, no forks.** `wi.auction.clear.clear` is imported (it matches SPEC §5 line for line). The engine adds `ahead`, the fee and the O(1) claim, and checks at every clear that the O(1) fills equal clear()'s fills. It uses `wi.eval.ladder` (Bracket, Ladder, rep, book_yes_asks, offer_status) and `wi.eval.fees.TAKER_RATE`. The ladder module is imported lazily because it pulls numpy. Under `import wi.engine.*` no pandas, xarray, netCDF4, pyarrow, matplotlib or numpy is loaded (checked by a test).
**Caps.** `reports/eval-04-05/handoff.json` exists but has no u_max/α/β/γ values, so capBps 8000 and α/β/γ 1000/2000/3000 stay at the SPEC §17 placeholders. Its hedge cap of 5 units per city-day fits candleCapCenti 3000, which is unchanged.
**Phase 4 findings (seat message).** (1) Residual fair value uses E[L(basis)] over the trailing 60 finalized days, all finalized at or before the quote time. That is a recent window, not climatology. (2) The half-spread floor is `minHalfTicks` = 1 tick.

## Verification (actual commands)
- `uv run pytest tests/engine -q` → `19 passed in 11.64s`. Full repo `uv run pytest -q` → `42 passed`.
- `uv run python scripts/engine_fixture_run.py` → `"ok": true, "events": 3248, "finalStateSha256": "46a288f3…3877"`. Policies: 116 bought, 114 settled, 2 voided, 0 open. All 30 days closed. Full replay hash matches. Replay from the 2026-08-08 snapshot (seq 1697) plus the tail matches. A second independent run matches. The log chain covers 3,248 lines. Conservation: funded = held = 79,000 USDC.
- Two runs back to back produce byte-identical MANIFEST, events, CSV and all 8 fixture files (checked with shasum).
- Mutation check on the look-ahead tests: I removed the `finalAt <= ts` filter, then separately the candle `ts <= t` filter. Each broke its test. Both were restored.
- The SPEC worked examples reproduce exactly: the 6-order auction, payouts (a)–(d), replication q = 0/0/50/250/450/600, h = 6, Kalshi fees of 2c and 6c, the waterfall (junior 10,000,120,000; redeem 4,000,077,999), and the 500 bps / 50,000 WI haircut.
- Tests cover only money and silent-corruption failures: engine auction conservation with fees on 4,000 books, and the reducer path draining escrow to 0; junior-first, the NAV identity and C1 on random pool sequences; the replay property; a log edit caught even when the hash chain is recomputed; point-in-time (poisoned post-T books and candles, every quote re-priced from the end state, settlement on the corrected revision, VintageChanged, NotFinal); no stranded money; house ticks idempotent when run twice.
- One engine bug was found and fixed by these tests: a junior withdrawal or policy payout paid to the house wallet did not credit its free float.

## Fixture run (engine demo, not evidence)
NYC, 2026-07-24..08-22. Central Park CLI plus IEM daily.py for LGA/JFK (identical to CLI since 2025-10). KXHIGHNY candles are real. Books on 08-07 and 08-08 are **synthetic**, labelled in the inputs and the manifest, and exist only to exercise the book path; the recorder has no data yet. Four businesses (heat and cool, at LGA and at JFK; B1 on a strip), house junior of 8,000 USDC, a senior LP of 20,000 who withdraws 10%, two WI stakers (one unstakes), a random trader, one RFQ. Also one LGA outage (08-14 void, refunds) and one transcription error corrected by revision 1 (LGA 08-01). The heat wave (08-06..08) produced 5 haircut days. In that wave 3 quotes were refused (premium above max payout) and 1 strip day was skipped.

## SPEC ambiguities I resolved (08/09 should follow these, or the seat should overrule)
1. **Fixture names.** SPEC §14 lists 6 files and 08-PLAN names 4, so I wrote all 8. `waterfall_cases.json` is byte-identical to `pool_cases.json`. `oracle_cases.json` is new: P1–P8, finalize/void timing, and one `engineOnly` case that Foundry should skip.
2. **§8.3 worked redeem.** The SPEC text uses supply 4·10¹⁷ and redeems 4·10¹⁶. The mint formula gives 4·10¹⁶ shares for 40,000 USDC, so 10% is 4·10¹⁵. The result, 4,000,077,999, is the same. This is a text slip for §18.
3. **Tail charge.** `p_top_ppm` is the end rung's mid, normalised by Σ mids (the same source as δ). When the whole policy range is beyond the end rung (cool puts in the heat wave), this charges units·UNIT·p_end/2. That is crude and expensive; flag it for 04/09.
4. **Quotes above max payout.** A quote with premium > units·UNIT is not issued, because the chain would revert.
5. **House schedule size per level.** Each level is min(`houseLevelMaxQty` = 100, a new param; headroom ÷ (levels × worst loss per unit)), where headroom is min over C3–C5. The headroom accounts for markets already planned that tick. Read literally, the SPEC would put all headroom on level 1.
6. **House sub-ledger.** State carries `house.ledger[day]` and `house.free`, and `HouseReturned.amount` must equal the day ledger (house P&L is zero by construction, T3). RFQ maker margin is fronted from house float and reimbursed by the day at accept.
7. **Pricing integers.** se = isqrt((nΣL² − (ΣL)²) // (n²(n−1))); halfSpread = max(minHalfTicks·TICK, zBps·se/1e4 + bufferTicks·TICK); bid legs ceil, offer legs floor. Pre-run basis history counts as finalized at D+2 12:00Z.
8. **Fixed vintage.** The engine rejects a revision whose vintageHash differs from revision 0 (`VintageChanged`). The chain cannot check this, because the hash is unsigned.
9. **HedgeDecision rungs.** They carry `depthCenti` and `askCents` as additive extensions so the reducer can assert I14. `source` may be `mixed`. Book levels are floored to CONTRACT_STEP (fractional contracts are unconfirmed).
10. **Strips.** Strip-template checks run at command level (`buy_strip_day`), because `PolicyBought` has no stripId. The WI genesis distribution lives in the world file, because the catalogue has no WI transfer event.
11. **C3–C5 exposure.** Exposure = policy reserves + house escrow on unclaimed orders + house `paid` on unsettled positions (auction and RFQ).
12. **Revert names and check order** follow the current `PoolVault.sol` and `OracleAdapter.sol`. I realigned the engine's finalize/void order to theirs.
13. **Snapshots and hedge settlement.** A snapshot is the state before the first event whose UTC day is later than the previous event's. The hedge settles at Kalshi `settlement_ts`, rounded up (≈ D+1 12:01Z).

## What 08 must know
- Read the fixtures with vm.parseJson. Keys are sorted, there are no nulls, and `revert: ""` means success. Pool steps share one schema (op, ts, actor, day, amount, released, loss, tranche, shares, requestId), and each expected snapshot carries ledgers, actor shares, dayPnl/openPolicies/deployedByDay and `result`.
- payoff qty goes up to 2¹²⁸−1, so some payouts are JSON integers above 2⁵³.
- eip712 chain-998 verifyingContracts are placeholder addresses (anvil deploy nonces 0/1), not deployments. Digests were cross-checked against `eth_account.encode_typed_data`.
- If you change an error name or check order, the seat reruns the script. Never edit the JSON by hand.

## What 09 must know
- Import path: `Ledger(world)` → module commands (`pool.deposit_senior(led, ts, …)`, `policy.issue_quote/buy_policy/bind`, `auction.place_order/clear_market/claim_order`, `oracle.post_report/finalize/void_day`, `house_mm.book/bind/hedge_day/settle_hedge/ret`, `rfq.request/respond/accept`, `rfq.venue_label`).
- A Revert (`.name`) leaves state unchanged. InvariantError means the state is corrupt. Snapshots come from `Ledger(keep_snapshots=True)`, and a restart uses `replay_from_snapshot`.
- Sim EIP-712 domains are chainId 31337 with sentinel verifyingContracts 0x…a1 (oracle) and 0x…a2 (policy), both in the world file.
- Ladder rungs are ints (cents, epoch s). `pricing.price_policy` returns None when the ladder cannot be priced.
- The engine loads eth_abi and eth_utils, never web3. The golden `tests/api/golden/scenario_nyc_3d.json` is still 09's to write.
