# Phase 7 context — decisions locked by the seat (2026-09-30 13:20Z) for SPEC.md

Sources: 07-RESEARCH, 08-RESEARCH, 09-RESEARCH, 14-RESEARCH, 15-RESEARCH, OWNER-RULINGS. Where research files disagree, this file wins.

1. **One instrument on-chain and in the engine (08-RESEARCH Pattern 1):** a fully collateralised scalar unit on market (indexId, day, lo, hi); long pays L(x) = clamp((x − lo)·1e6/(hi − lo), 0, 1e6) USDC base units, short pays 1e6 − L(x); ticks 1..99 cents. Every payout family maps onto it: CAPPED_CALL(K,C) = long [K, K+C]; CAPPED_PUT = short [K−C, K]; DIGITAL_ABOVE = [K, K+1]; residual BASIS_SWAP with range ±R = [−R, +R] on the index (index_a − index_b). The engine exposes the business-facing views (per °F units, signed basis price) as pure conversions.
2. **Clearing rule (identical in engine and Solidity; 08-RESEARCH Pattern 2):** open uniform-price call auction per market with a fixed cutoff; p* maximises min(D,S), then minimises |D−S|, then the midpoint of the tied range; at the marginal tick fills are price-time priority (per-order `ahead` offset), lazy claims; no cancels after placement in v0 (short auction epochs); MAX_ORDERS per auction 200; everyone pays p*. Phase 4's src/wi/auction/clear.py implements this same rule; Phase 7 imports it or makes it identical and adds a parity fixture.
3. **Daily timeline (07-RESEARCH Pattern 1):** D−1 14:00Z ladder opens / orders open; D 02:30Z house cutoff (house schedule frozen); D 03:00Z public cutoff + clear; D 05:00Z (06:00Z CHI) house paper-hedges station legs at T−24h; D+1 05:00Z/06:00Z Kalshi close; D+1 12:00Z oracle fetch for CLI indices; D+2 12:00Z CLI final → settle; nClimGrid D+5/D+6; PRISM D+7/D+8; daily 12:30Z pool epoch. Close times come from data, never hard-coded.
4. **Pool (14-RESEARCH option D + 08-RESEARCH Pattern 3):** all claim-paying money is USDC. PoolVault holds USDC with two internal ledgers: senior (outside LPs, `SeniorShare` token) and junior (protocol-owned, seeded by the house; in v0 only the owner/house may deposit junior). Losses hit junior first; premium split by seniorPremiumBps; exposure cap reserved ≤ capBps × assets; request-then-claim withdrawals with delay ≥ forecast horizon + settlement window (v0 default 10 days; testnet demo constructor arg). **WI token = fixed supply, no mint role after deploy; WIStaking contract: staked WI carries governance weight and is cut pro rata (burned, never sold) when the junior ledger loses money, capped per event (haircutCapBps, default 3000); positions in cooldown remain cuttable.** What stakers earn is NOT specified (Phase 15 question); v0 pays stakers nothing. WIToken.sol (08-01, owner-mintable) becomes fixed-supply at deploy (mint once to the deployer, renounce mint).
5. **Margin:** full collateral everywhere; no hedge credit in v0 (reported as a metric). Caps per (contract, day), per (station, day), per (metro, day), overall utilisation; α/β/γ/u_max placeholders until Phase 4 handoff.json lands (read it if present).
6. **Oracle (08-RESEARCH Pattern 4 + 07-RESEARCH Pattern 7):** EIP-712 `Report(bytes32 indexId,uint32 day,int64 value,uint16 revision,uint64 asOf)` signed by an allow-listed reporter, posted by anyone; calendar revision window W per index source (CLI: settle on the D+1 12:00Z fetch, W = 1 day + 24 h dispute; nClimGrid W = 5 d; PRISM W = 7 d); finalize after dayEnd + W; getFinal only; void + refund if nothing posted by W + grace. Vintage hash stored. Values in tenths of °F / hundredths of inch, int64.
7. **Policies (07-RESEARCH Pattern 2 + 08 Pattern 5):** business buys one policy (house-hedge path, default) at a house-signed Quote{market, buyer, units, premium, expiry, nonce}; the house books the station leg (paper Kalshi replication per Pattern 8 of 07-RESEARCH, ins1 rule, fees included) and enters the residual leg as a limit order in D's auction with h = round(n × δ); pool carries the convexity/tail; if the residual leg does not fill the policy is downsized pro rata before the hedge. Overlay path: the portal shows the rung list; the venue sells only the basis unit. Strips = auto-renewing daily policies with a max daily premium. Business strike K is fixed per business; the ladder tail beyond the top bracket is pool exposure.
8. **Residual index registry:** abstract until Phase 3's verdict; register two candidates now: R-A "metro minus station" (equal-weight mean of the published ASOS network from NWS CLI/GHCN-D, minus the settlement station, rounded to 0.1 °F) and P-A station pairs (LGA−NYC etc.). Rain residual = indicator difference with C_r = 1.
9. **RFQ (07-RESEARCH Pattern 10):** one-way request; house first, whitelisted makers; firm EIP-712 Quote; best price wins; acceptQuote on-chain; no last look; labelled single-responder.
10. **Engine (07-RESEARCH Pattern 11):** pure integer-money event reducer, hash-chained JSONL log, canonical JSON, snapshots with sha256, invariants asserted inside apply (conservation, caps, waterfall identity), parity vectors for Foundry under contracts/test/fixtures/. No pandas/xarray/netCDF4 imports at module level anywhere under src/wi/engine (the API bundle must stay slim).
11. **Fees:** Kalshi taker fee ceil-to-cent(0.07·q·P·(1−P)) per rung order; protocol fee placeholder 10 bps of notional on hedger fills + 10 % of risk margin to treasury (Phase 4 sweep may change; parameters, not code).
12. **Legal posture (15-RESEARCH):** the prototype keeps the owner's rulings (open auctions on testnet, mock USDC, no points); SPEC.md carries a "Regulatory notes" section stating that mainnet access rules (ECP/KYC gating, DCM route, carrier wrapper) are undecided and that nothing here is a legal conclusion. Portal copy must not call the product "insurance".

## Seat addendum 2026-09-30 (≈13:55Z, seat clock was an estimate; written right after 07-01-SUMMARY) — 07-01 decisions confirmed

All six decisions listed in 07-01-SUMMARY are CONFIRMED and are part of the law for 07-ENGINE, 08 and 09:
1. Quote has 8 fields (adds `isLong`, `fee`).
2. House acts as the pool's agent per day: fund → return or write off after 10 days; hedge P&L to junior; exposure cap counts money deployed to the house.
3. Premium held until `bind(policyId, residualOrderId)`; 02:15Z sale cutoff before the 02:30Z house cutoff.
4. Market times derive from global settings, never caller-supplied.
5. Oracle revision windows per index; vintage hash stored but not signed (Report type string locked). NOTE for the mainnet spec: the vintage must enter the signed payload; log as open item in §17, do not change now.
6. Residual order-size formula, staker haircut on a day's net junior loss, junior-minimum rule, auction/RFQ fees default 0, void refunds, floating daily strips, `IWIStaking.sol`.

Note: `docs/CONVENTIONS.md` §2 was already rewritten by 01-06 with the full close-time table (05:00Z / 06:00Z from 2026-08-15); the 07-01 change-log remark refers to the v1 file. No edit needed.

## Seat addendum 2026-09-30 (≈14:16Z, right after 07-SUMMARY) — 07-ENGINE resolutions confirmed

All 13 resolutions in 07-SUMMARY ("SPEC ambiguities I resolved") are CONFIRMED as law for 08 and 09, with three notes:
- #2 (§8.3 share counts 10× in the SPEC text): a text slip; fix in SPEC §18 change log when a doc pass next touches SPEC.md (do not block on it).
- #3 (tail charge crude when the whole policy range is beyond the end rung): 09-LEDGER may refine the charge to units·UNIT·max(0, p_end − p_far)/2 style bound or cap it at the ladder's implied residual; must be recorded in SPEC §18 and in the engine with a test on the cool-put-in-heat-wave case. Not a blocker for the demo.
- #8 (fixed vintage enforced only in the engine because the hash is unsigned): joins the mainnet-spec open item from the 07-01 addendum (vintage must enter the signed payload).
Also: `reports/engine/fixture-run/events.jsonl` (≈1 MB, deterministic) is committed once as the reproducible artifact; regenerate only when the engine changes.

## Seat addendum 2026-09-30 (≈14:24Z, right after 08-SUMMARY) — Phase 8 deviations confirmed

All ten deviations in 08-SUMMARY are CONFIRMED, plus these rulings:
- **Staking cooldown = return window + 2 days (12 days in v0).** Closes the escape the 08 worker found (unstake cooldown equal to the 10-day house write-off window lets a staker dodge a haircut). SPEC §17 value; the engine's staking params and the Configure script must both carry 12 days. 09-LEDGER applies it to the engine params; the contracts read it from Configure.
- Deactivated index → unreported days void (SPEC P1 wins over the interface comment). Fix the interface comment in the next doc pass.
- `closeDay` refuses to run before the day's UTC end (both engine and chain).
- PolicyManager at 22,781 bytes: no further code goes into it; new features go into a separate contract or the Lens.
- Sourcify verification and testnet behaviour are unverified until the owner runs RUNBOOK.md.

## Seat addendum 2026-09-30 14:40Z — premium split and season capital (from 04-JUNIOR)

Finding: with `seniorPremiumBps = 2000` on gross net premium, junior loses money in every simulated season, because on a Kalshi-replicating station leg the premium is almost all expected payout; kept margin is ≈ 1.5 % of premium.
Rulings:
1. **Senior's share is a share of kept margin, not of gross premium.** v0 implements this WITHOUT code changes: `seniorPremiumBps = 30` (0.3 % of gross premium ≈ 20 % of the simulated book's 1.5 % margin). SPEC §17 sets 30 with this derivation; SPEC §18 logs the change; Configure.s.sol and the engine params carry 30. The mainnet spec routes margin explicitly (house-signed quote carries the senior cut).
2. **Capital is stated on two horizons.** The pre-registered 30-day figure (0.126 of notional, $412k) stays as M3. The season figure (worst modelled summer loss $731k on the simulated book) is the one a depositor cares about, so v0 caps writing at capital ÷ worst-modelled-season-loss (≈ 0.56 of the simulated book per $412k), i.e. ≈ 0.22 of notional on a season basis. Both numbers appear together everywhere (memo, report §7, decks).
3. The junior layer can be wiped in a 1-in-20 season (modelled −144 %, whole-summer resampling −293 %). The memo says so in plain words; the WI burn haircut cap (30 %) limits token burn per event, not USDC junior loss.

## Seat addendum 2026-09-30 ~17:20Z — rulings on 07-CONSISTENCY

1. `withdrawDelay` = 12 days too (same escape as the staking cooldown, item #28); Deploy default + SPEC §17. A constructor/deploy guard requires `unstakeCooldown ≥ houseReturnWindow + 2 d` and `withdrawDelay ≥ houseReturnWindow + 2 d`.
2. Index registry (SPEC §6.2/§17): three index types — (a) station-pair spread (the v0 auction listing; labelled "residual venue, adds ≈ +0.01 as cover per Phase 3"), (b) P-A-IDW three-nearest-ASOS inverse-distance temperature index (the RFQ reference for heat residuals), (c) PRISM per-cell WEEKLY spread for rain (G1-P). The daily auction stays the venue; rain residuals settle weekly.
3. §8.3 example: labelled "illustration at 2000 bps"; arithmetic corrected; premium base = net premium after the treasury fee everywhere.
4. Mainnet items in SPEC §17: signed vintage; staked-WI parameter voting with ranges + delay (v0 = owner key sets parameters, stated plainly in memo/decks); house settles back within the 10-day window (not "daily").
5. Portal: nav/page "Coverage" → "Cover"; pool page deposit copy = immediate; trace rain = wet stated in the rain cover copy.
6. Wording: "run on 19 of 26 pairs, passed on those"; deck row cite 143; stale deck note removed.

## Seat ruling 2026-09-30T19:12:06Z — trace precipitation (supersedes the 2026-09-30 "trace = wet for the station leg" ruling)
Evidence from 13-RAIN: the KXRAIN series the house trades settled all 26 trace days NO at CLINYC/CLIORD/CLIMIA (2026-07-15..09-28), 94/94 measurable days YES, 96/96 dry days NO. The 61.5 % "trace settles YES" figure (eval-01 `rain_daily.trace_yes_share`) comes mostly from the older KXRAINNYC series and does not describe the contract we hedge with.
Ruling: the rain cover pays on measurable rain only (CLI daily precip ≥ 0.01 in; trace = dry), so the cover settles exactly like the Kalshi leg and no trace charge is needed. This also removes the §1/§7.1 encoding gap (the index already encoded T = 0). Product copy: "Kalshi's rain contract counts a trace as no rain, and so does this cover." Report and decks must stop saying trace days settle YES 62 % of the time without naming the series and window. Rain book (04-RAIN) used the wet-includes-trace rule; its headline verdicts (no netting, depth ~300× too thin, junior fails) do not turn on trace days — logged as a caveat, not rerun.
