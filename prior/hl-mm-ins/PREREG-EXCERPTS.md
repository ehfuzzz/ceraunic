# Pre-registration excerpts (verbatim)

Source: ~/hl-mm-wt/corpus-fix/reports/S4-RESULTS.md (uncommitted worktree at copy time, 2026-09-30). Line references are to that file. Text below each header is copied verbatim.

## 1. ins1 pre-registration (S4-RESULTS.md lines 1536-1552)

## Pre-registered: ins1 — insurance payoffs from Kalshi event-contract ladders (course PDF 3a)

**Question.** Can a progressive (linear-above-threshold) weather payout be replicated from Kalshi's bracketed event contracts at executable bid/ask, and what is the hedge error by source?

**Data.** Kalshi public API: settled daily high-temperature ladders `KXHIGHNY`, `KXHIGHTEWR`, `KXHIGHTTTN`, `KXHIGHCHI`, `KXHIGHMIA` (settled since 2026-07-24; hourly candlesticks with yes bid/ask), order-book snapshots 2026-09-29 for the 09-30 ladders + monthly rain NYC + hurricane counts + tornado + Cincinnati HDD; NWS ASOS daily max (IEM) for NYC/LGA/JFK, EWR/TTN, ORD/MDW, MIA/FLL/OPF. Open weather markets snapshot (1,291 markets, 412 series).

**Target payoff.** Per city-day: heat cover H(T) = $1 × min(max(T − K, 0), 6) with K = floor of the ladder's second bracket (so the ladder spans the payoff). Replicating portfolio = for each bracket contract, buy H(bracket midpoint) YES contracts (top open-ended bracket priced at H at its floor+1), at the YES ask at the decision time.

**Tests (thresholds fixed now).**
- T1 replication cost/error at 24 h, 12 h, 2 h before close: premium paid (asks) vs realised H(T_settle). Report mean error, RMSE, and hedge effectiveness HE = 1 − Var(H − portfolio payoff)/Var(H). PASS if HE ≥ 0.70 at 24 h with |mean error| ≤ 15% of mean premium. Because the settle value falls inside a known bracket, portfolio-vs-payoff error at settlement is pure binning error (piecewise-constant vs linear): report it exactly.
- T2 decomposition per city-day: (a) binning = H(T) − ladder payoff; (b) spread = Σ contracts × (ask − mid); (c) settlement source = TWC-settled bracket vs NWS ASOS max at the same station (mismatch rate); (d) geography = H(T_nearby station) − H(T_settlement station) for LGA/JFK vs NYC, TTN vs EWR, MDW vs ORD, FLL/OPF vs MIA; (e) liquidity = contracts fillable within 1c/3c/5c of best ask per bracket from the 09-29 books, → max replicable notional; (f) capital = collateral-days × 5%/yr for the seller side (1 − p per contract).
- T3 horizon: share of open weather-market volume by time-to-close (≤2 d, 3–7 d, 8–35 d, 36–120 d, >120 d) and count of series with ≥30-day horizon AND two-sided quotes ≤10c wide. Insurance needs ≥30 d cover; PASS for "insurance-grade primitives exist" if ≥5 such series.
- T4 variants (idea-variants rule): V1 sell-side (be the insurer: sell the ladder at ask, collect spread; markout to settlement); V2 weather-LP on the thin monthly/seasonal ladders (quote where spreads are 20–90c); V3 rolling daily cover for a seasonal exposure (roll cost = Σ daily spreads); V4 cross-venue (Polymarket cat-landfall + Kalshi counts); V5 course-paper deliverable (3a).

**Kill/keep rule.** Business variant is KEEP if V1 or V2 shows ≥ +1c/contract all-maker markout with ≤ $150 worst-window loss on the same inventory caps as kl2; course-paper variant is judged on whether T1–T3 give a clean empirical basis-risk decomposition (PDF 3a evaluation).


## 2. ins1 results entry (S4-RESULTS.md lines 1553-1555)

### ins1 results — 2026-09-30 00:20Z (see reports/ins1/README.md)
T1 PASS on liquid ladders (NYC/CHI/MIA HE 0.94/0.94/0.86 at own station, overpay 17%/7%/0%), FAIL on thin EWR/TTN (asks 3.4× payoff). T2: geography dominates (raw HE 0.13–0.64, 0.30–0.68 bias-corrected); binning RMSE 0.42–0.51 per unit; TWC-vs-NWS mismatch 0–4%; depth 80–450/rung within 3c → ~$100/day policy. T3 FAIL (no local ≥30-day two-sided ladders; only hurricane counts). V1 sell-side +1.5c/+1.1c/0c per contract with worst days 9–19× the mean → not a bot. V5 course paper KEEP. Corrections during the run: Chicago settles at Midway; market day = ticker date; rung "no offer" rule.


## 3. Pre-registered: ins2 V1 (S4-RESULTS.md lines 1623-1626)

## Pre-registered: ins2 V1 — grid-cell basis overlay (course paper test 1–3)
_2026-09-30 05:58Z, before any read. Source IDEA-VARIANTS ins2._
**Data.** The ins1 272 city-days (Kalshi asks, NWS station obs) plus NOAA nClimGrid-Daily (or PRISM daily, 4 km) cells within 40 km of each settlement station (NYC, EWR, TTN, ORD, MIA). **Tests.** (1) hedge effectiveness of the station ladder for a linear payout at each cell vs at the station; (2) pooled dealer book: variance of the sum of cell−station residuals across cells vs the sum of individual variances; (3) prelim-vs-final revision: share of cell-days whose value moves across a $1/F payout bin between first publication and T+5d (if the dataset exposes revisions; else report unavailable). **Pass.** Pooled/individual variance ratio < 0.5 AND per-cell HE ≥ own-station HE − 0.1 for ≥ 70 % of cells. Cost 0 (public data, < 1 GB).

