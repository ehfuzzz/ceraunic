# EVAL-04 add-on: junior return and premium split (pre-registration)

Frozen 2026-09-30 14:23Z (UTC, file time), before any number in this add-on was produced. Asked for by 14-RESEARCH rules 4-5 and the 14-02 summary. Descriptive; the only yes/no line is the 14-RESEARCH §2.4 test ("junior return in a 1-in-20 year still positive over three years"). Script: `scripts/eval04_junior.py` (reads Phase 4 caches, writes nothing Phase 4 already wrote).

**Capital.** Junior J0 = H `junior_ES95_30d_usd` ($206,315); senior S0 = H `C30_usd` - J0.

**SPEC mapping of the Phase 4 book (docs/SPEC.md §6, §8.3, §8.6, §11).**
- Station-leg house fills = policies the pool writes. Premium per scalar unit ($1) = p* for a house offer (pool writes a call), 1 - p* for a house bid (pool writes a put, payout UNIT - L(x), SPEC §6.4). Payout = x or 1 - x.
- Residual-leg house fills and the Kalshi hedge = house deployment (§8.6): all P&L to junior, no premium credit, no senior share.
- Risk margin RM = premium - expected payout at the house's fair value mu_s.
- Treasury cut t in {10 %, 20 %} of station RM (SPEC `feeMarginBps`); the 10 bps notional fee is paid by hedgers on top of p* (Phase 4 convention) and reported on its own line.
- Net premium = premium - t*RM. Senior = s * net premium, s = 20 % (`seniorPremiumBps` 2000). Junior = the rest + residual P&L + hedge P&L - payouts.
- Sensitivity B (not SPEC): senior = s * (1 - t) * station RM (senior shares the kept margin, not the gross premium).

**Observed seasons.** 2023-2026 from `auction_primary.parquet`; sensitivity `auction_resid_trailing5.parquet`. Return = season junior P&L / J0 (uncapped), plus a day-by-day waterfall from J0/S0 (junior floored at 0, senior pays the rest) with the first wipe-out date.

**Model-based seasons.** Phase 4's capital scenario: `proxy_bundle(fit 1951-2025, detrended)`, both legs, seasons 1999-2025 with <= 5 missing book days (the capital years; 26 seasons), book = `average_book(auction_primary)`. Daily pool P&L = book P&L at fair (weather) + per-calendar-month deterministic terms taken as 2023-2026 daily means from the primary auction: edge (RM both legs + Kalshi hedge cost vs fair), station premium, station RM. Season = 153 days; calendar-aligned joint-date block bootstrap (7-day blocks, each block position drawn from a random season, all stations the same date), 10,000 reps, seed 20260930. Report median, 5th percentile (= "1-in-20 season", model-based), 1st percentile, minimum; the 26 historical seasons' median and worst; and the 5th percentile of the sum of three bootstrap seasons.
