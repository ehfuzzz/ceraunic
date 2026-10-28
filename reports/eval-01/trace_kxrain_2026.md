# KXRAIN trace-day check (2026), how it was counted
1. Markets: every settled NYC/CHI/MIA market of the multi-city KXRAIN series in `data/cache/kalshi/kxrain_markets.parquet` (event dates 2026-07-15..09-29, 216 markets; pulled earlier by `scripts/pull_kxrain.py`, no new API calls).
2. Each market's `result` (yes/no) was joined by event date to the NWS CLI daily precip at its settlement station (CLINYC, CLIORD, CLIMIA per `rules_primary`) from the IEM CLI files on disk; every market matched a CLI row.
3. Classes: trace = CLI "T"; measurable = 0.01 in or more; dry = 0.00 in.
4. Result: 26 trace days, 0 settled YES; 94 measurable days, 94 YES; 96 dry days, 96 NO (demo window to 09-28: 26/0, 93/93, 94/94). Keyed numbers: `trace_kxrain_2026.json`.
5. The eval-01 figure `rain_daily.trace_yes_share` = 61.5 % pools 91 trace days, mostly from the older KXRAINNYC series; it does not describe how KXRAIN settles.
