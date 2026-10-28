# EVAL-01 sensitivity: trace = dry (labelled; primary numbers in results.json are unchanged)
Rule: primary `precip > 0 incl. trace` (frozen conditional, all-series trace YES share 0.615); this run `precip >= 0.01 in (trace = dry)`, the rule the product pays on. By scripts/eval02.py --wet-rule dry, rain_daily only (2 s).
Moved: 55 of 132 rain_daily numbers (exposure label, climatology, HE_wet, station agreement). Market Brier, cost per $ payout and no-offer shares do not use the rule. T3 at 24 h (gain >= 0.02) passes under the dry rule: True.

| number (key under `rain_daily`) | primary -> dry |
|---|---|
| result_vs_station_agreement | 0.958 -> 0.933 |
| horizons.24.brier_clim ; brier_gain | 0.247 -> 0.249 ; 0.141 -> 0.143 |
| horizons.12.brier_clim ; brier_gain | 0.248 -> 0.249 ; 0.182 -> 0.183 |
| horizons.2.brier_clim ; brier_gain | 0.248 -> 0.249 ; 0.227 -> 0.228 |
| horizons.24.he_wet.he_cover.est / he_ladder.est | 0.83 -> 0.76 / 0.27 -> 0.23 |
| horizons.12.he_wet.he_cover.est / he_ladder.est | 0.84 -> 0.78 / 0.19 -> 0.19 |
| horizons.2.he_wet.he_cover.est / he_ladder.est | 0.85 -> 0.74 / 0.11 -> 0.08 |
