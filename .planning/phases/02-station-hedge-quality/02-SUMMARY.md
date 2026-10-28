# Phase 2 (EVAL-01) summary: station hedge quality

Worker: worker, 2026-09-30. PREREG frozen 13:22:08Z; final run 13:37Z (`uv run python scripts/eval02.py --all`,
24 s, deterministic). Nothing committed or staged.

## Verdicts (rule A: K = second-bracket floor, 24 h before close, liquid = NY + CHI + MIA)
| test | result | verdict |
|---|---|---|
| T1 HE_cover ≥ 0.85 and overround ≤ 20 % | HE_cover 0.95 [0.95, 0.96]; overround 24.6 % [21.4, 27.9] | FAIL (price, driven by 2023-24) |
| T1b HE_ladder, expected ~0.5 | −0.32 pooled; 0.37 [0.33, 0.42] for 2025+ | below expectation |
| T2 thin ladders fail if overround > 100 % | EWR 241 %, TTN 266 % | FAIL (both) |
| T3 rain Brier gain vs climatology ≥ 0.02 | 0.141 [0.128, 0.152] (0.106 vs 0.247) | PASS |
| T4 no-offer ≤ 10 % every city-year 2024+ | 2024: 12.3-13.7 %; 2025: 0.3 %; 2026: 0 % | FAIL (2024) |
Same verdicts on the frozen sample without the CLI fill.

## Headline numbers
- 4,462 liquid city-days (NY/CHI 2022-04 → 2026-09-28, MIA 2023-05 →), 68 thin, 1,053 daily rain markets.
- Three eras: 2022 overround 12-18 %; 2023-24 33-47 % with spread cost > $1/unit and 12-42 % no-offer days;
  2025+ (post-hoc, descriptive) 9.7 % [7.7, 11.7], no-offer 0.2 %, HE_ladder 0.37.
- HE_cover ≈ 0.95 every year; binning RMSE 0.42. HE_ladder is low because the 24 h ask already prices the
  forecast; only the forecast miss moves. At 2 h HE_ladder ≈ 0. Gap HE_cover − HE_ladder ≈ 0.6 (2025+) = the
  forecast-level risk the house carries on the default path (→ Phase 4).
- Fixed strike (rule B, trailing 7-day mean): tail outside ladder on 3.1 % of days, 2.6 % of payout; ladder buys
  nothing on 27 % of days (CHI 37 %); HE_cover 0.97, HE_ladder −0.75 (−0.20 for 2025+).
- Settlement: CLI ≠ Kalshi settled value on 0.2 % of 3,822 days (2023+). ins1's 5/272 was IEM measurement noise.
- Rain: $1.20 per $1 payout at the 24 h ask (with fees); wet HE_cover 0.83, HE_ladder 0.27; trace days settle YES
  61.5 %. Monthly rain ladders: 47-64 % no offer at month start.
- Depth (books.json, one snapshot): max 33 (NY) / 54 (CHI) / 55 (MIA) units at ≤ 3c, sized by rung.
- ins1 check: NYC 07-24..09-29 premium 1.728 vs 1.73, payout 1.448 vs 1.43 → within 5 %.

## Files
- reports/eval-01/PREREG.md, RESULTS.md, results.json, tables.md, citydays.csv.gz, rain_daily.csv,
  figures/{he_by_year,overround_by_year,no_offer_share,depth_hist}.png
- src/wi/eval/ladder.py (brackets, cap−1/floor+1 reps, call/put quantities, ask-at-t forward fill, both candle
  schemas, price_leg, book depth), fees.py (Kalshi quadratic fee), hedge.py (HE, joint block bootstrap). Phase 7
  can import ladder.py and fees.py directly.
- scripts/eval02.py (the run), scripts/pull_kxrain.py (keyless KXRAIN pull, 300 requests at ≤ 4 req/s →
  data/cache/kalshi/kxrain_*.parquet, gitignored)
- tests/test_eval_ladder.py (5 tests: ins1 19.5-contract day, put bottom bracket cap−1, no look-ahead property,
  candle schemas, fee rounding). Full suite: 16 passed.

## Deviations (logged in PREREG.md with UTC times)
1. 205 events with no API expiration_value (2025-10..2026-01) filled from the CLI when it sits inside the settled
   bracket; strict sample reported as a sensitivity. 2. Bracket disjoint/contiguous check (4 events out).
3. Rain Brier on all quoted markets, cost/HE on executable ones. 4. Wet-day conditional fired (trace = wet).
5. KXRAINNY dropped (Pier 26 gauge). 6. Post-hoc "liquid 2025+" pool, descriptive only. 7. Rule-B strike caveat
   (t−1 final CLI not issued by the 24 h decision).

## Open items for the seat
- S3 recorder prefix not listable (anonymous AccessDenied; default profile session expired). Depth rests on the
  single books.json snapshot. Re-run the depth part when hl-mm shares read access.
- KXRAIN was not in the Phase 1 cache; pulled here (five cities only). Consolidating it into
  data/cache/kalshi/{markets,candles}.parquet is left to the data owner.
