# Phase 4 (EVAL-04/05) data manifest

Written by `scripts/eval04.py` (stage population/revision), 2026-09-30 UTC. Raw files are gitignored and re-pullable; per-file URL, bytes, md5 and fetch time are in `eval04-sources.csv`.

- Raw pulled by this phase: 60 files, 106.5 MB (Census ZBP detail/totals, CBP county, SUSB 2022, 2024 ZCTA gazetteer under data/raw/census/; 25 GHCN-Daily by_station files under data/raw/ghcnd_eval04/; 30 IEM AFOS CLI season files under data/raw/iem_afos_cli/).
- Population artifact: `data/cache/eval04/population.parquet`, 33702 rows, md5 `e5abc747ab12ffba052dba8a28559b52` (written 2026-09-30T13:48:31Z).
- Other intermediates (data/cache/eval04/): ghcnd_tmax.parquet, unit_weights.parquet, ladders.parquet, rungs.parquet, participants.npz, auction_{primary,coc6,coc30,cutoff2h,resid_ladder_mu,resid_trailing5}.parquet, backtest_days.parquet, results_partial.json.
- Reused read-only: data/cache/kalshi/{markets,candles}.parquet (01-02), data/cache/weather/official_daily.parquet (01-03), data/cache/vintages/nclimgrid_prelim.parquet and data/cache/grid_disc/source=nclimgrid (01-04), data/raw/ghcnd/ghcnd-stations.txt + inventory (01-04) for id lookup.
