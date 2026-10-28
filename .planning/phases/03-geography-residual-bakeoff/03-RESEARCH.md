# Phase 3: Geography basis + residual bake-off - Research

**Researched:** 2026-09-30
**Domain:** Spatial (geographic) basis risk in weather hedging; gridded vs station weather indexes (PRISM, nClimGrid-Daily, IEM/NWS ASOS); settleable index design; pre-registered evaluation
**Confidence:** MEDIUM overall. HIGH on data conventions (read from PRISM/NCEI/NWS/RMA documents and file metadata). MEDIUM on what the literature implies for us (it is mostly agricultural). LOW-MEDIUM on the pass thresholds (judgment calls anchored to ins1/ins2).

**Numbers computed during this research:** station metadata only (IEM coordinates, great-circle distances, data coverage counts, CLI availability). No temperature or rain comparison between stations or grids was computed, so the pre-registration draft below is still clean.

## Summary

The literature measures geographic basis risk the way ins1 did: how much of the variance of an exposure at location A is removed by an index measured at location B, as a function of distance and of the aggregation of both sides (Woodard & Garcia 2008a/b; Norton, Turvey & Osgood 2013; Musshoff, Odening & Xu 2011; Ritter, Musshoff & Odening 2014; Leppert, Dalhaus & Lagerkvist 2021). The findings agree across papers. (1) Temperature basis is much smaller than rain basis at the same distance. (2) Basis falls as you aggregate in space and time, on the exposure side and on the index side. (3) Interpolating several stations (IDW, kriging) beats the single nearest station, but only by a little: about 2–3 % of relative risk reduction for heat indexes, and about 18 % lower RMSE for daily rain in one preprint. (4) The best predictor of the payout at a point is the payout at nearby points, not geography covariates. (5) Weights optimized on history beat IDW in sample, but out of sample equal weights are hard to beat (the 1/N result in portfolio choice). Gridded rain was no better than station rain for basis risk in the one direct test (Dalhaus & Finger 2016).

Four data facts decide the design. (a) Both grids are "day ending in the morning" products. PRISM's day is 12Z–12Z, labelled by the end date. nClimGrid-Daily's day is "the 24-hour period ending in the early morning of the specified day", mixing midnight and morning observers. So for temperature, grid label D+1 matches ASOS calendar day D (ins2 confirmed this for nClimGrid). For rain, the grid day and the ASOS day overlap only about 17 of 24 hours, which puts a hard ceiling on daily rain HE for any grid. (b) NCEI's own user guide says single-day values at single grid points "should not be interpreted as an indication of the true conditions at that particular location on that day". The product is built for aggregated use. That, not bad luck, is why ins2's per-cell daily overlay failed. (c) ins2's residual mixed two sources (grid cell minus ASOS station). The grid's day-definition and smoothing error at the station went into every cell's residual. That is where the 0.74–0.83 common-mode correlation comes from. A residual computed within one source (index at the target minus the same index at the station) cancels that shared error. (d) NCEI publishes county and census-tract averages as CSV files, and USDA's PRF (0.25° grid, 2-month windows) moved from CPC to NCEI data on 2026-08-31 so producers "can look up the rainfall data themselves". The index that works at scale is area plus time aggregation on public numbers, not point accuracy.

**Primary recommendation:** Judge every residual design against held-out ASOS stations (leave-one-out truth), not against grid cells. Build every residual within one source. Fix all weights before the test window: equal weights for the regional factor, IDW with p=2 for per-point blends, and PC1 frozen on 2024 as an exploratory comparison only. Evaluate temperature daily and rain on weekly totals. Then run the pre-registration draft at the end of this file. The ASOS-network "metro minus station" factor (equal weight, published station list, NWS CLI or GHCN-D inputs) is the design to beat for temperature. For rain, expect only weekly-or-longer aggregates to clear any bar.

## Standard Stack

### Core (all already in `pyproject.toml`; versions from `uv.lock`)
| Library | Version | Purpose | Why standard |
|---------|---------|---------|--------------|
| numpy | 2.5.3 | HE, bootstrap, PCA (`linalg.eigh`), haversine | Everything here is small dense arrays |
| pandas | 3.0.6 | Station and date panels, weekly resampling | Calendar logic (`resample("W-SUN")`) |
| xarray + netCDF4 | 2026.9.0 / 1.7.4 | nClimGrid monthly NetCDF; PRISM via `?format=nc` | PRISM's web service serves netCDF, so no GDAL/rasterio is needed |
| scipy / statsmodels | 1.18.1 / 0.15.0 | Optional OLS for the fitted-beta sensitivity | Already locked |
| duckdb / pyarrow | 1.5.6 / 25.0.1 | Parquet panels from Phase 1 | Phase 1 convention |

### Data sources (free; licence checked)
| Source | Access | What we use | Notes |
|--------|--------|-------------|-------|
| nClimGrid-Daily v1.0.0 (NCEI) | `https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/YYYY/ncdd-YYYYMM-grd-{scaled,prelim}.nc` | Cell tmax/prcp, 1/24° (4.6 km N–S, 3.0–4.2 km E–W) | Licence "no restrictions". One file per month. Prelim is replaced by scaled around day 4–6 of the next month. No vintage archive. |
| nClimGrid-Daily area averages | `.../access/averages/YYYY/{tmax,prcp}-YYYYMM-{cty,cen}-scaled.csv` | County (and tract) averages, published | Rows look like `cty,28013,NJ: Essex County,2026,08,TMAX, d1..d31` in °C or mm. Code = NCEI state code + county FIPS (NJ=28, NY=30, IL=11, FL=08). Missing days are -999.99. |
| PRISM AN91d daily 4 km (D2) | `https://services.nacse.org/prism/data/get/us/4km/{tmax,ppt}/YYYYMMDD?format=nc` | Cell tmax/ppt | Terms (2026): data "may be freely reproduced and distributed" with attribution (PRISM Group, URL, access date). Each zip has a `.stn.csv` listing that day's input stations. The download limit is 2 per file per 24 h. The old web service was disabled 2025-09-30. |
| PRISM grid version | `https://services.nacse.org/prism/data/get/gridCount/us/tmax/YYYYMMDD` and `.../releaseDate/...` | Grid count 1–8 per day | 8 releases: T+1, T+5, then around the 15th of the next 6 months. Grid count 8 is final. |
| IEM ASOS daily summary | `https://mesonet.agron.iastate.edu/api/1/daily.json?station=LGA&network=NY_ASOS&year=2025` | Station `max_tmpf`, `precip` | Same source as ins1. AWOS sites often lack precip. |
| IEM NWS CLI archive | `https://mesonet.agron.iastate.edu/json/cli.py?station=KLGA&year=2025` | Official daily high/low/precip for CLI sites | CLI is Kalshi's settlement source. Day = midnight to midnight local standard time (1 AM–1 AM during DST). |
| IEM station metadata | `https://mesonet.agron.iastate.edu/geojson/network/{NY,NJ,PA,IL,IN,FL}_ASOS.geojson` | Coordinates, archive begin, AWOS flag, GHCN IDs | Used for the station table below |

### Alternatives considered
| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| PRISM/nClimGrid for daily rain | NCEP Stage IV hourly (4 km radar + gauge) or MRMS (~1 km) | Hourly data can be summed to the exact ASOS LST day, which removes the 7-hour misalignment. But it means GRIB2 volume and radar artifacts. Add it only if the gridded rain designs pass weekly and fail daily because of alignment. |
| ASOS truth points | NYS Mesonet NYC micronet, NJWXNET, CWOP | Denser and more urban-interior (closer to where businesses are). Data terms for NYSM/NJWXNET not verified. CWOP quality is uncontrolled. Validation only, never settlement. |
| ASOS for rain truth | CoCoRaHS gauges (in GHCN-D as `US1*`) | Dense, 7 AM observations, fine for weekly totals. Volunteer-run, so it is a manipulation vector if used for settlement (same reason ins2 V4 excluded business-owned gauges). Secondary truth only. |
| nClimGrid/PRISM | CPC Unified 0.25° (old PRF source), gridMET, Daymet | CPC is being retired by RMA for PRF. Daymet is released annually, so it is not operational. gridMET is derived from PRISM plus NLDAS and adds nothing for settlement. |
| Any of the above | Open-Meteo | Non-commercial licence (AGENTS.md). Paper only. |

**Installation:** nothing new. `uv sync` covers it; PRISM is read with `xarray.open_dataset` on the `?format=nc` download.

## Architecture Patterns

### Method recommendation (what 03-01..03-04 should build)

1. **Truth = held-out ASOS/AWOS stations, leave-one-out (LOO).** The exposure at a "business point" b is the station value at b. The index under test never uses b, and weights are never fitted with b's data. Grid cells are never used as truth. In ins2 the grid cell was both truth and index, so interpolation noise was mistaken for geography.
2. **Same-source residuals.** A residual contract pays r = H(I(target)) − H(I(S)), where I is one data source (PRISM, nClimGrid, or the ASOS network) and S is the settlement station. The station leg pays H(T_S) from the Kalshi ladder. The business ends up holding H(T_S) + r. The source's bias and day-definition error at S cancel between the two terms. The ins2 form (grid cell minus ASOS station) stays in the table only as a continuity check.
3. **One payout function per variable, one strike per market-day, all sources.** Temperature: H(T;K) = min(max(round(T) − K, 0), 6) in $ per $1/°F unit (the ins1 shape). Rain: capped weekly totals. Rounding follows the settlement source (integer °F, 0.01 in).
4. **Weights fixed before the test window.** Equal weights (primary), IDW p=2 from geometry (per point), and PC1 frozen on 2024 (exploratory). Never refit during the test window except at a pre-registered annual reconstitution (1 Jan 2026) that uses only data that were final on that date.
5. **Dependence-aware inference.** A joint circular block bootstrap (14-day blocks, the same resampled days for every point in every market), because NYC and EWR share truth points and all points share weather regimes.

### Recommended project structure
```
src/wi/eval03/
├── points.py      # station registry: coords, market, role (settle/network/truth/outer), AWOS flag, county code
├── align.py       # the only place day conventions live (grid label D+1 <-> calendar D; weekly maps)
├── sources.py     # loaders: IEM daily, IEM CLI, nClimGrid cells + county CSV, PRISM cells (+ gridCount, .stn.csv)
├── indexes.py     # index formulas: cell, disc mean, county avg, network mean (LOO), IDW, frozen PC1
├── designs.py     # design registry D0, G1-*, C1-N, R-*, P-* -> residual series per (market, point)
├── metrics.py     # HE, dHE, beta/eta, sd(r), book concentration, premium loading, block bootstrap
└── run.py         # typer CLI -> reports/eval-03/{prereg.md, results.json, tables.md, figures/}
```

### Pattern 1: Same-source residual (spread)
**What:** r_b = H(I_src(target_b)) − H(I_src(S)); the business holds H(T_S) + r_b.
**When:** every grid design. For the ASOS network, I(S) = T_S itself.
**Why:** in the per-cell cell-minus-station form, every residual contains the same term (G_cell(S) − T_S): smoothing, day window, and siting at S. That term is common across cells, which is exactly ins2's ρ 0.74–0.83. The spread removes it and keeps only the grid's spatial difference.

### Pattern 2: Regional factor = weighted metro mean minus station
**What:** every "metro minus station" factor is F = Σ_j w_j X_j − X_S with Σ w_j = 1. The three estimation choices differ only in w:
- **Equal weight:** w_j = 1/n over a published list. No parameters. The primary.
- **PC1:** take the first principal component v of the residual matrix R_tj = X_tj − X_tS on the train window, then w = v⁺/Σv⁺ (sign fixed so Σv > 0, negatives clipped to 0). Because R_tj = X_tj − X_tS, the PC1 score is (up to scale) Σ w_j X_j − X_S, a metro mean with PCA weights. When residual correlations are near uniform (ins2: 0.74–0.83), PC1 loadings are near uniform and PC1 ≈ equal weight. PCA can only win if the loadings are uneven and stay uneven out of sample.
- **Distance-weighted:** only makes sense relative to the business location (w_j ∝ d_bj^-2). That is a per-point station blend, not a regional factor. It is tested as design P-A-IDW.
**Out of sample:** fit w on 2024 using only data that were final at fit time (ASOS: immediate; nClimGrid: scaled files; PRISM: grid count 8, i.e. at least 6 months old). Fit without the held-out point. Freeze. Optionally reconstitute once on 2026-01-01 under the same rule.
**Settleable form:** publish the station list and weight vector at listing. Index_t = Σ w_j T_j,t from NWS CLI (or GHCN-D where no CLI exists), rounded to 0.1 °F. Plus a quorum rule, a fallback, and a revision cut-off (see the template in Code Examples).

### Pattern 3: Leave-one-out truth
For each market m and truth point b: network index excludes b; PCA fit excludes b; pair and IDW choose among the network minus b, plus S. In production nobody sits exactly at an airport, so LOO is the honest stand-in for "business between stations".

### Pattern 4: Evaluate the residual's efficiency, not just the HE
With u = E_b − H(T_S) (the basis left by the station leg alone) and residual r:
- ΔHE = [Var(u) − Var(u − r)] / Var(E_b) = Var(r)·(2β − 1)/Var(E_b), with β = Cov(u, r)/Var(r).
- η = 2β − 1 is the share of the variance handed to the house that actually removes variance from the business. η = 1 is a perfect residual; η ≤ 0 means the residual adds as much noise as it removes. This one number separates a residual that tracks the true basis from one that mainly passes grid noise to the pool.

### Tests that belong (AGENTS.md: only silent-corruption failure modes)
- `align.py`: a fixture day with a known NYC heat maximum lands on grid label D+1 for both grids, and the weekly map covers labels Tue–Mon.
- No look-ahead: every fitted object (PC1 weights, fitted-β sensitivity) records its fit dates. Assert max(fit date) < 2025-01-01, or < the reconstitution date, using only data final at that date.
- LOO property: perturbing T_b leaves every index used to evaluate point b unchanged (network mean, IDW, PC1 weights).
- End-to-end fixture: 2 markets × 3 points × 60 days produces `results.json` with known row counts and one hand-checked HE.

### Anti-patterns to avoid
- **Mixed-source residual** (grid minus ASOS): brings day-definition and smoothing error into the residual (ins2).
- **Grid cell as truth:** measures the grid against itself. Grids also ingest the truth stations, so grid designs look better at station points than at a random business point.
- **In-sample offsets and ratios:** ins1's "HE after offset/ratio fit" (e.g. LGA 0.21 → 0.49) was fitted on the evaluation days. Fitted betas are a sensitivity only, computed on train and applied to test.
- **Choosing the network radius, K rule, or design list after seeing numbers.**
- **Daily rain HE on grids without saying that the day windows overlap only about 70 %.**
- **Treating PRISM provisional grids as final:** days in the last 6 months are at grid count below 8.
- **The ins2 variance-ratio rule** (pooled/individual < 0.5): for N positively correlated residuals the ratio ≈ 1 + (N−1)ρ, so it cannot pass. Use a normalized concentration κ instead (below).

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| County/tract averages of nClimGrid | Your own polygon averaging | NCEI `*-cty-*.csv` / `*-cen-*.csv` | The published number is the settleable index. NCEI does the cos-latitude weighting. Nothing for the oracle to argue about. |
| Official station daily max/precip | Recomputing from hourly METARs | NWS CLI (IEM `cli.py` JSON); GHCN-D for non-CLI ASOS | ASOS highs come from 5-min averages of 1-min data that METARs can miss. The CLI uses the LST day and is Kalshi's settlement source. |
| PRISM version tracking | File-timestamp diffing | PRISM `gridCount` / `releaseDate` services | 8 releases over 6 months. The service reports the release number. |
| PRISM file parsing | BIL/COG readers, GDAL | `?format=nc` + xarray/netCDF4 | Already installed |
| Which stations went into a PRISM day | Guessing the contamination | `.stn.csv` inside each grid zip | Lists that day's input stations. Gives the contamination share at each truth point. |
| Day alignment | Offsets scattered across scripts | One `align.py` plus one fixture test | ins2's unaligned run had median cell HE −0.96 to −0.09 |
| PCA | Power iteration | `numpy.linalg.eigh` on the train covariance | Trivial at 5–300 series |
| Distances | geopandas/pyproj | 5-line haversine | Error is negligible under 100 km |

**Key insight:** the settleable index should be a number someone else already publishes (a CLI value, a GHCN-D value, an NCEI county average) or a fixed arithmetic combination of such numbers. Every bespoke computation the oracle performs is something a counterparty can dispute and something that has to be versioned.

## Common Pitfalls

### Pitfall 1: Day-definition mismatch
**What goes wrong:** a grid value is joined to the wrong calendar day, or rain windows only partly overlap.
**Why:** PRISM "July 2" covers 12Z July 1 to 12Z July 2 (PRISM update schedule). nClimGrid-Daily values apply to "the 24-hour period ending in the early morning of the specified day" (NetCDF attribute; midnight and morning observers mixed). The ASOS/NWS climate day is midnight to midnight LST, which is 1 AM–1 AM local daylight time in summer (NWS Chicago FAQ).
**How to avoid:** temperature: calendar day D ↔ grid label D+1 for both grids. Rain: same map for daily (majority overlap, about 17 h of 24); calendar week Mon–Sun ↔ grid labels Tue–Mon. Keep all of it in `align.py` with one fixture test (a known NYC heat day must land on the right label).
**Warning signs:** nearest-cell tmax RMSE vs ASOS above about 2 °F, or a lag-1 cross-correlation above lag-0 (ins2: 4.6 °F unaligned vs 1.7 °F aligned for NYC).

### Pitfall 2: Common-mode residuals from mixed sources
**What goes wrong:** residuals across cells correlate at about 0.8, so the book does not diversify and HE collapses.
**Why:** the term (G_cell(S) − T_S) is shared by every cell-minus-station residual.
**How to avoid:** same-source spreads (Pattern 1). Report ins2-form residuals only as continuity.
**Warning signs:** mean pairwise residual correlation above 0.6 for spread designs.

### Pitfall 3: Truth contamination
**What goes wrong:** grid designs look better at truth points than they would at business locations.
**Why:** both grids ingest the ASOS stations we use as truth. PRISM also ingests CWOP, NYS Mesonet, NJWXNET, CoCoRaHS and radar. In PRISM, ASOS/WBAN precipitation is used only May–Sep ("gauges not suited to freezing conditions").
**How to avoid:** report the share of test days on which each truth station appears in PRISM's `.stn.csv`, and state that grid-at-station HE is an upper bound. There is no clean fix, since no truth exists away from stations.

### Pitfall 4: Fitting on the test window
**What goes wrong:** the "regional factor" wins because its weights, beta, offset, or radius were tuned on the days it is scored on.
**How to avoid:** train = 2024 only. Freeze weights. LOO. Pre-registered radii (30 km disc for grid regional means; 50 km network) and pre-registered K rule. Every sensitivity is labelled as such.

### Pitfall 5: Revisions and vintages
**What goes wrong:** evaluating on final data a product that would settle on preliminary data.
**Why:** PRISM has 8 releases over 6 months. nClimGrid prelim files are replaced by scaled files and there is no vintage archive (ins2). NCEI warns that input data grow 50–100 % after first availability.
**How to avoid:** evaluate on final/scaled data. Record the PRISM grid count at pull. Run a sensitivity on grid-count-8 days only. Revision risk itself belongs to Phase 4 (going forward only).

### Pitfall 6: Station data quality and IDs
- AWOS sites (LDJ, LOM, CKZ, IGQ, 06C, JOT) mostly lack precipitation. MMU, GYY, BLM, HST, WRI, DYL, PNE have too little precipitation data for the rain sets.
- IEM keys West Palm Beach as **DJT**, not PBI (GHCN USW00012844). The `ncei91` field for MMU, BLM, GYY and HST points to a nearby COOP station, not the ASOS. Use `GHCNH_ID` / USW IDs for the ASOS record.
- TMB tmax coverage is 81.9 % in the test window, so it is excluded from temperature. HWO, FXE and JRB are at 93 %.
- IEM daily summaries can differ from the CLI (the NWS FAQ explains why). Check IEM against the CLI at CLI stations before the evaluation (rule in the pre-registration).

### Pitfall 7: Zero-inflated payouts
The capped heat cover pays zero on many days, and Var(E_b) can be tiny in a subsample, which makes HE unstable. Require at least 60 paying days and Var(E_b) > 0 for a point to enter pooled statistics. Report how many days paid.

### Pitfall 8: Many designs × sources × markets
Picking the best of about 12 designs over 5 markets inflates the winner. Fix the eligible list, the pooled metric and the tie-break rule before running, report every design, and give paired bootstrap CIs for the winner against the runner-up.

### Pitfall 9: Central Park is a cool-island station
The NYC settlement station sits at Belvedere Castle inside the park. The Conservancy's 2022 sensor study found park woodland 10 °F cooler and park lawns 5 °F cooler than street trees on the hottest day. Grids smooth anomalous stations toward their neighbours (NCEI guide), so on hot days the grid cell at Central Park will differ from the CLI. That is another reason for same-source spreads, and a reason to expect a persistent sign in NYC residuals. How big the bias is at the ASOS sensor is not verified.

## Code Examples

### Day alignment (the only place it lives)
```python
# Sources: PRISM_update_schedule.pdf ("a grid for July 2 covers 1200 UTC July 1 - 1200 UTC July 2");
# nClimGrid-Daily NetCDF attr ("24-hour period ending in the early morning of the specified day");
# NWS: climate day = midnight-midnight LST. ins2 verified label D+1 for nClimGrid tmax (NYC RMSE 4.6F -> 1.7F).
import datetime as dt
import pandas as pd

def grid_label_for_calendar_day(d: dt.date) -> dt.date:
    return d + dt.timedelta(days=1)

def grid_series_on_calendar_days(g: pd.Series) -> pd.Series:
    """g indexed by grid label date -> re-indexed by the calendar day it represents."""
    out = g.copy()
    out.index = pd.DatetimeIndex(out.index) - pd.Timedelta(days=1)
    return out

def weekly_total(p_calendar: pd.Series) -> pd.Series:
    """Mon-Sun calendar weeks; a week counts only if all 7 days are present."""
    return p_calendar.resample("W-SUN").sum(min_count=7)
```

### Payout, HE, and residual efficiency
```python
import numpy as np

def H(T_f, K, cap=6.0):
    """ins1 heat cover: $ per $1/F unit; T rounded to integer F like the CLI."""
    return np.clip(np.round(T_f) - K, 0.0, cap)

def he(E, hedge):
    v = np.var(E)
    return np.nan if v == 0 else 1.0 - np.var(E - hedge) / v

def evaluate_point(E_b, H_S, r):
    """E_b: exposure at held-out point; H_S: station-leg payout; r: residual payout (same days)."""
    u = E_b - H_S
    beta = np.cov(u, r, bias=True)[0, 1] / np.var(r) if np.var(r) > 0 else np.nan
    he0, he1 = he(E_b, H_S), he(E_b, H_S + r)
    return {"he0": he0, "he": he1, "dhe": he1 - he0, "beta": beta, "eta": 2 * beta - 1,
            "sd_r": float(np.std(r)), "mean_r": float(np.mean(r))}
# identity worth asserting in a test on synthetic data: dhe == var(r)*(2*beta-1)/var(E_b)
```

### LOO network mean with a quorum
```python
def network_mean(T: "pd.DataFrame", members: list[str], exclude: str | None, quorum: float = 0.6):
    """T: days x stations (F). Equal weight over members minus the held-out point; NaN if quorum fails."""
    cols = [j for j in members if j != exclude]
    X = T[cols]
    ok = X.notna().sum(axis=1) >= int(np.ceil(quorum * len(cols)))
    return X.mean(axis=1, skipna=True).where(ok)
```

### Frozen PC1 weights (train only, LOO, settleable)
```python
def frozen_pc1_weights(T_train: np.ndarray, S_train: np.ndarray):
    """T_train: (days, stations) excluding the held-out point; S_train: (days,).
    Returns w >= 0, sum 1, so index = T @ w and factor = index - S. Also returns PC1 variance share."""
    R = T_train - S_train[:, None]
    R = R[~np.isnan(R).any(axis=1)]
    vals, vecs = np.linalg.eigh(np.cov(R, rowvar=False))
    v = vecs[:, -1]
    v = v if v.sum() > 0 else -v
    w = np.clip(v, 0.0, None)
    return w / w.sum(), float(vals[-1] / vals.sum())
```

### Joint circular block bootstrap of the pooled median dHE
```python
rng = np.random.default_rng(20260930)

def block_index(n_days: int, block: int = 14) -> np.ndarray:
    starts = rng.integers(0, n_days, int(np.ceil(n_days / block)))
    return ((starts[:, None] + np.arange(block)[None, :]) % n_days).ravel()[:n_days]

def pooled_median_dhe(panel, idx):
    """panel: list of (E_b, H_S, r) arrays on the common test calendar (NaN where missing)."""
    d = []
    for E, HS, r in panel:
        e, h, rr = E[idx], HS[idx], r[idx]
        m = ~(np.isnan(e) | np.isnan(h) | np.isnan(rr))
        d.append(he(e[m], h[m] + rr[m]) - he(e[m], h[m]))
    return np.nanmedian(d)

# boot = [pooled_median_dhe(panel, block_index(n)) for _ in range(2000)]; ci = np.percentile(boot, [2.5, 97.5])
```

### Settleable regional index: spec template (goes to Phase 7 if R-A wins)
```
Index      WI-<MKT>-METRO-TMAX v1, listed <date>
Inputs     NWS CLI daily max (integer F) for CLI stations in the list; NCEI GHCN-D TMAX (USW id) otherwise
Formula    M_t = equal-weight mean of available inputs, rounded to 0.1 F; published with the input count
Quorum     >= 60 % of listed inputs; else use the T+7 GHCN-D snapshot; if still short, the residual leg voids
Residual   r_t = H(M_t; K_t) - H(T_S,t; K_t), same H and strike K_t as the policy
Timing     provisional T+1 12:00 local; final T+7 snapshot; later QC edits ignored (cf. PRF "conclusively presumed accurate")
Changes    station list and weights reviewed each 1 Jan using data final by 1 Dec; never changed during a policy
```

## State of the Art

| Old approach | Current approach | When changed | Impact |
|--------------|------------------|--------------|--------|
| PRF rainfall index on NOAA CPC Unified 0.25° gauge grid | PRF on NCEI data, same grids and intervals | Announced 2026-04-30; PRF effective 2026-08-31 (2027 crop year) | Public precedent that settlement data should be public and readable ("in formats like Microsoft Excel"). RMA says loss ratios are nearly unchanged. RMA names no product; it is presumably nClimGrid-based, unverified. |
| PRISM old web service, BIL files | New service (COG default, `?format=nc`), releaseDate and gridCount endpoints | Old service disabled 2025-09-30 | Phase 1 must use `services.nacse.org/prism/data/get/...` |
| PRISM radar weighting with ST2un | 24-h radar-only MRMS as the weighting reference; ST4 as predictor | July 2020 | Daily ppt east of the Rockies is a station/radar hybrid, strongest for summer convection |
| nClimGrid-Daily beta | v1.0.0 operational, with county/tract/division averages | Sep 2022 | Published area averages usable directly as an index |
| Kriging/IDW for basis reduction (ag literature) | Same, plus copula/multi-site optimized weights, PCA/PLS indexes | 2013–2023 | Small out-of-sample gains over IDW or equal weights. Use the simple forms. |

**Deprecated/outdated:**
- ins2's variance-ratio pass rule: unreachable with positive correlation. Replaced by the normalized concentration κ plus the efficiency η.
- Per-cell daily grid settlement: the product guide itself discourages single-point single-day use.

## Research Findings by Question

### Q1. How spatial basis risk is measured, and which index designs reduce it
- **Measure.** Hedging effectiveness is the variance (or standard deviation, or risk-premium) reduction of the exposure from holding the index, compared across distances and aggregation levels. Woodard & Garcia (2008a, AFR 68(1):99–117) on US corn: geographic basis "can be significant" but "should not preclude geographic cross-hedging, particularly with temperature as opposed to precipitation derivatives", and it "diminishes as spatial aggregation in the risk exposure and hedging instrument increases". Woodard & Garcia (2008b, JARE 33(1):34–51): better hedging at higher aggregation. Musshoff, Odening & Xu (2011, Applied Economics 43(9):1067–1077) separate local and geographic basis. With 39 km of geographic basis, rainfall options still cut revenue s.d. by up to 45 %, but only 10 % once local basis is included. Norton, Turvey & Osgood (2013, J. Risk Finance 14(1):20–34): geographic covariates predict payout differences poorly. "The strongest predictor of payout at a given location is payout at nearby locations." Distance raises payout discrepancy for precipitation, and altitude matters for heat.
- **Reduction by blending stations.** Ritter, Musshoff & Odening (2014, Comput. Econ. 44(1):67–86) derive optimal multi-site portfolio weights from a daily multi-site rainfall model. These reduce basis risk more than IDW (in their setting). Leppert, Dalhaus & Lagerkvist (2021, WCAS 13(2):273–286): heat index insurance for Illinois/Iowa corn. IDW, ordinary kriging and regression kriging beat the nearest-station index by about 2–3 % relative risk reduction, and the advantage grows as stations get sparser. Guo & Li (2023, arXiv 2311.14844), daily rain at 138 US stations: RMSE nearest-neighbour 5.76 mm, IDW 4.71 mm, trans-Gaussian kriging 4.64 mm.
- **Spatial hedging with traded contracts.** Barth, Benth & Potthoff (2011, Appl. Math. Finance 18(2):93–117) build variance-minimizing positions in exchange-traded temperature futures at other locations to hedge an untraded location. This is the theoretical twin of "station ladder + residual".
- **Area and multi-level indexes.** Miranda (1991, AJAE 73(2):233–242): area-yield insurance with an individual β. Elabed et al. (2013, Agric. Econ. 44(4–5):419–431): two-level (zone plus sub-zone) index contracts to cut basis. That is our regional factor plus local residual.
- **Grids vs stations.** Dalhaus & Finger (2016, WCAS 8(4):409–419): "No differences were found between using gridded and weather station precipitation" for basis risk (German wheat). Grids help with coverage and availability, not accuracy.
- **Factor / PCA indexes.** In the insurance literature, PCA is used across weather variables (Boyd et al. 2020, NAAJ 24(3):355–369; Pelka & Musshoff 2013, AFR 73(2):358–372 on mixed indexes), not across locations. We found no paper using PC1 of station residuals as a settleable spatial index. Treat it as new and exploratory.
- **Implication for us:** temperature at 7–50 km is the favourable case in this literature. Expect modest gains from blending and bigger gains from aggregation. Expect weighting cleverness to matter less than removing the source mismatch.

### Q2. Regional factor: PC1 vs mean vs distance-weighted, without look-ahead, as a settleable index
- **They are the same object with different weights** (Pattern 2). PC1 ≈ equal weight when residual correlations are near uniform. IDW is per-business, not regional.
- **Estimation risk.** DeMiguel, Garlappi & Uppal (2009, RFS 22(5):1915–1953): none of 14 optimized portfolio rules beat 1/N out of sample. The estimation window needed grows with the number of assets. Our train window is 366 days with 5–9 stations (or about 200 grid cells). Prior: PC1 will not beat the mean by a meaningful margin. The pre-registered tie-break favours the mean.
- **No look-ahead:** fit on 2024 using data final at fit time. Fit without b. Freeze sign and scale. Clip negative weights. Optional reconstitution on 2026-01-01 under the same rule. PRISM data used for fitting must be at grid count 8.
- **Settleable:** a published list plus a published weight vector plus a quorum, fallback and revision cut-off rule (template above). With equal weights, the only discretionary input is the station list, set by a written rule (online ASOS within 50 km with at least 90 % coverage the previous year).

### Q3. PRISM daily vs nClimGrid-Daily: day convention, closeness to an ASOS calendar-day max, urban error
- **PRISM (AN91d, D2):** day = 1200–1200 UTC, labelled by the end date ("a day ending at 1200 UTC on 1 January is labeled 1 January"). Once-per-day observers must be within ±4 h of 12Z for tmax/tmin, and COOP morning observations are day-shifted if needed. Networks include ASOS/ISH (hourly), COOP, CWOP, NYSM, NJWXNET, FAWN and many mesonets. The interpolation is CAI on 1991–2020 normals. Precipitation east of the Rockies blends CAI with Stage IV radar (weighted against MRMS since 2020). There are 8 releases (T+1, T+5, then monthly to 6 months). **Inference (MEDIUM):** ASOS enters as hourly data aggregated to the 12Z–12Z window, so PRISM at an ASOS site represents a 12Z–12Z max, not the calendar-day max.
- **nClimGrid-Daily v1.0.0:** thin-plate splines (ANUSPLIN) on GHCN-D morning and midnight observations. The label is the day on which the 24-h period ends, in the early morning. Values are scaled to monthly nClimGrid, which is homogenized with PHA. Cross-validation 1991–2020: half of stations have mean absolute error ≤ 1 °C for Tmax and median absolute precip error ≤ 2 mm. Smoothing "smooths out" stations warmer or colder than their neighbours and gives a slight dry bias. The guide discourages single-day single-point use. ASOS midnight observations are calendar-day values and land on label D+1. ins2 confirmed this: aligned nearest-cell RMSE was 1.1–1.8 °F against 2.3–5.2 °F unaligned.
- **Which is closer to an ASOS calendar-day max:** unknown. There is no direct comparison in the literature we found, and ins2 only tested nClimGrid. Arguments go both ways. nClimGrid's inputs at ASOS sites are calendar-day values, but the spline mixes windows and smooths hard. PRISM is internally consistent (all inputs on the 12Z–12Z day) and much denser in NYC/NJ (CWOP, NYSM, NJWXNET), but its window is not the calendar day. The two windows share the afternoon, so for tmax the difference shows up on frontal days (more in winter). **Handled as a pre-registered descriptive check** (nearest-cell RMSE and correlation, both grids, both alignments), not as a decision input.
- **Urban error:** neither product has an explicit urban heat island term that we could verify. Both smooth station anomalies. The Central Park cool island (Pitfall 9) is the concrete case.

### Q4. Rain: 4 km interpolation error, station pair or network vs grid, lessons from PRF
- **Daily convective rain is where grids are weakest.** Daly et al. (2021, JTECH 38:1979–1992): summer rainfall "dominated by isolated, convective cells that often fall between weather stations". Radar-aided interpolation helps most in summer. nClimGrid-Daily is station-only (no radar) and has a smoothing dry bias. Ensor & Robeson (2008, JAMC 47(9):2468–2476): gridding "significantly increased the frequency of low-precipitation events while greatly reducing the frequency of heavy-precipitation events". So grid wet-day indicators over-trigger and heavy-rain triggers under-trigger. Areal reduction factors decay faster with area where convection dominates (Breinl et al. 2020, JHM 21(4):671–689). Spatial sampling error falls with accumulation time (Villarini et al. 2008, JGR 113 D11102). Correlation estimates for rain are biased by skewness (Habib, Krajewski & Ciach 2001, JHM 2(6):621–629).
- **Pair vs network vs grid.** Blending beats nearest station modestly (Guo & Li: −18 % RMSE for IDW). Gridded is no better than station for basis (Dalhaus & Finger). Distance hurts rain far more than heat (Norton et al.; Woodard & Garcia). So for daily rain at 10–40 km, expect every design to be weak. Aggregation in time is the lever.
- **PRF lessons.** The index is 0.25° cells (about 28 km N–S, 21 km E–W at 40°N) over 2-month intervals, expressed as a ratio to the long-run mean. Payout is "conclusively presumed accurate", and RMA states the grid "may not match the amount of precipitation received by a producer". Measured basis is large: 26–43 % (Yu et al. 2019, JARE 44(1)); false-negative probability 31–46 % in California (Keller & Saitone 2022, AJAE 104(4):1203–1223). Changing only the resolution (5× finer data) changes 13 % of payout determinations in Texas 2012–2023 (Benami, Ramanujan & Cecil 2025, ARER). PRF works at scale because of subsidy, transparency, and aggregation in space and time, not point accuracy. The 2026 switch to NCEI was made for transparency.
- **Recommendation:** make weekly totals the primary rain unit. Kalshi lists NYC daily (KXRAINNYC, KXRAINDNYC), weekly (KXRAINNYCW, TWC-settled) and monthly (KXRAINNYCM, NWS CLI) rain series, plus monthly Chicago/Miami (KXRAINCHIM, KXRAINMIAM, TWC-settled). This comes from a shared 2026-09-30 series snapshot; liquidity and the settlement station are for Phase 1/2 to confirm. Report daily wet-day agreement and monthly totals as secondary.

### Q5. Nearby stations (IEM, online, data since 2024) and distances
Great-circle distance from IEM coordinates. Coverage = share of days with a value (train = 2024; test = 2025-01-01..2026-08-31). CLI = NWS Daily Climate Report present in IEM for 2025. T/R = in the temperature/rain truth set (≥ 90 % coverage both windows). AWOS stations are truth-only, never index inputs.

**NYC (settle: Central Park `NYC`, CLI yes)**
| Stn | Name | km | CLI | AWOS | tmax cov | prcp cov | Sets |
|---|---|---|---|---|---|---|---|
| LGA | LaGuardia | 7.5 | yes | | 100/100 | 100/100 | T R |
| JRB | Manhattan Wall St heliport | 9.3 | no | | 98.9/93.4 | 100/100 | T R |
| TEB | Teterboro | 11.5 | no | | 100/100 | 100/99.8 | T R |
| EWR | Newark | 20.0 | yes | | 100/100 | 100/100 | T R |
| JFK | JFK | 23.4 | yes | | 100/100 | 100/100 | T R |
| CDW | Caldwell | 28.5 | no | | 100/99.7 | 100/99.5 | T R |
| LDJ | Linden | 29.4 | no | yes | 79.8/98.2 | 22/29 | excluded |
| MMU | Morristown | 37.6 | no | | 100/100 | 20/20 | T |
| HPN | White Plains | 38.8 | no | | 100/100 | 99.5/93.9 | T R |
| FRG | Farmingdale | 47.1 | no | | 100/99.7 | 100/98.4 | T R |
| ISP | Islip | 73.1 | yes | | 100/100 | 100/100 | outer ring |

**EWR (settle: `EWR`, CLI yes)**: LDJ 9.6 (excluded), JRB 13.7, NYC 20.0 (CLI), TEB 21.8, CDW 23.6, MMU 24.4 (T only), LGA 26.6 (CLI), JFK 34.7 (CLI), SMQ 42.7 (T R; tmax 100/100, prcp 99.7/99.5). Outer: BLM 56.0 (tmax 100/92.4, prcp 56/64, T outer only), TTN 70.9 (CLI).

**TTN (settle: `TTN`, CLI yes)**: DYL 26.7 (T; prcp 96/60), PNE 27.7 (T; prcp 94/86), WRI McGuire AFB 34.7 (T; prcp 43/42), N40 36.4 (archive starts 2025-12-13, excluded), VAY 37.2 (T R), SMQ 40.5 (T R), LOM 41.2 (AWOS, T truth only), CKZ 42.1 (AWOS, T truth only), NEL 47.7 (tmax 73/50, excluded). Outer (user-listed): BLM 59.2, MMU 67.3, EWR 70.9, CDW 80.4. **The TTN rain set is only VAY and SMQ.**

**MDW (settle: Midway `MDW`, CLI yes; Kalshi Chicago)**: ORD 24.4 (CLI, T R), IGQ 33.5 (AWOS, T truth), GYY 33.9 (T; prcp 19/14), LOT 34.7 (CLI, T R), 06C 37.1 (AWOS, T truth), PWK 39.3 (CLI, T R), DPA 43.3 (CLI, T R; tmax 99.5/98.0), JOT 46.1 (AWOS, T truth). Outer: UGN 71.7 (CLI).

**MIA (settle: `MIA`, CLI yes)**: OPF 14.0 (T R), TMB 20.0 (tmax 100/81.9, so R only), HWO 24.7 (T R; 93 % test), HST Homestead ARB 34.0 (T; prcp 73/71), FLL 35.8 (CLI, T R), FXE 48.1 (T R; tmax 92.8 % test). Outer: DJT (= PBI in IEM) 102.0 (no CLI found in IEM under KPBI/KDJT).

**Index networks** (non-AWOS truth stations; S included in the metro mean; b excluded when b is the truth point):
- Temperature: NYC {LGA, JRB, TEB, EWR, JFK, CDW, MMU, HPN, FRG}; EWR {JRB, NYC, TEB, CDW, MMU, LGA, JFK, SMQ}; TTN {DYL, PNE, WRI, VAY, SMQ}; MDW {ORD, GYY, LOT, PWK, DPA}; MIA {OPF, HWO, HST, FLL, FXE}.
- Rain: NYC {LGA, JRB, TEB, EWR, JFK, CDW, HPN, FRG}; EWR {JRB, NYC, TEB, CDW, LGA, JFK, SMQ}; TTN {VAY, SMQ}; MDW {ORD, LOT, PWK, DPA}; MIA {OPF, TMB, HWO, FLL, FXE}.
- **Truth-set sizes (≤ 50 km):** temperature 9 + 8 + 7 + 8 + 5 = 37 (market, point) pairs; rain 8 + 7 + 2 + 4 + 5 = 26.

**Geometry note for the pair design (LOO, final networks):** under the product rule "pair with the nearest station, and use no residual if that station is S", these points get r ≡ 0:
- Temperature (8 of 37): LGA, JRB, TEB (NYC); DYL, SMQ (TTN); GYY, LOT (MDW); HST (MIA).
- Rain (8 of 26): LGA, JRB, TEB (NYC); SMQ (EWR); VAY, SMQ (TTN, so P-A equals D0 for TTN rain); LOT (MDW); TMB (MIA).

The other pairs are:
- NYC: EWR→JRB, JFK→LGA, CDW↔MMU (rain: CDW→TEB), HPN→LGA, FRG→JFK.
- EWR: JRB→NYC, NYC→LGA, TEB→NYC, CDW↔MMU, LGA→NYC, JFK→LGA, SMQ→MMU.
- TTN: PNE↔VAY, WRI→VAY, LOM→PNE, CKZ→DYL.
- MDW: ORD↔PWK, DPA→ORD, IGQ→GYY, 06C→ORD, JOT→LOT.
- MIA: OPF↔HWO, FLL→HWO, FXE→FLL.

**County design zeros:** C1-N also gives r ≡ 0 where b and S share a county: JRB (New York County, as Central Park), ORD and PWK (Cook County, as MDW), and OPF, TMB and HST (Miami-Dade, as MIA).

**Cross-market point worth reporting on its own:** EWR is a truth point for the NYC market. "Liquid KXHIGHNY plus residual (EWR vs NYC)" vs the thin KXHIGHTEWR ladder (ins1: 241 % overpay at 24 h) is a direct product question. The same applies to TTN.

## Pre-registration Draft (03-01 freezes this verbatim with a UTC timestamp before any evaluation number)

**Questions.** EVAL-02: how much variance of a local weather exposure the settlement-station leg alone removes at nearby points. EVAL-03: which residual designs add hedge effectiveness out of sample, at what residual variance and indicative premium, and whether they are settleable.

**Sample.**
- Calendar days (LST) 2024-01-01 to 2026-08-31. **Train** 2024-01-01..2024-12-31 (weights, PCA, fitted-β sensitivity only). **Test** 2025-01-01..2026-08-31 (608 days; about 86 Mon–Sun weeks). Every reported pass/fail metric is test-window.
- nClimGrid: scaled files only. PRISM AN91d 4 km: grid count recorded per day. Primary uses all days; a sensitivity uses grid count 8 days only.
- Kalshi sub-sample: test-window city-days with settled KXHIGH* ladders (ins1 rows plus the Phase 1 extension). Secondary table with the binned ladder payout replacing H(T_S), and the ins1 K rule.

**Stations.** Settlement S ∈ {NYC, EWR, TTN, MDW, MIA}. Truth points, networks and outer rings exactly as in the Q5 tables. Inclusion rule: online IEM ASOS/AWOS within 50 km of S with ≥ 90 % coverage in both windows. Outer-ring points (50–110 km) are reported but not in pass tests.

**Station values.** IEM daily summary `max_tmpf` / `precip` (as in ins1). Before evaluation, at each CLI station compare IEM against CLI on the full window. If they differ on more than 2 % of days (tmax, integer °F) or more than 2 % of days (precip, 0.01 in), that station switches to CLI values. This check produces data-quality numbers only and is run before any HE.

**Exposure and payouts.**
- Temperature: E_b,t = H(T_b,t; K_t) with H(T;K) = min(max(round(T) − K, 0), 6) $ per $1/°F unit. K_t = floor(mean of T_S over t−7..t−1) (point-in-time, settlement station, same for every point and design in the market-day). Station leg = H(T_S,t; K_t).
- Rain (primary): weekly totals R_w (Mon–Sun calendar weeks, inches); E = min(R_b,w, 3.00). Station leg = min(R_S,w, 3.00). Grids: labels Tue–Mon, mm/25.4.
- Rain (secondary): daily wet-day indicator (≥ 0.01 in, same threshold for every source); monthly totals (descriptive).

**Designs** (residual r_b,t in payout units; the business holds station leg + r):

| ID | Design | Residual | Eligible for verdict |
|---|---|---|---|
| D0 | Station only | 0 | baseline |
| G1-P | Per-cell PRISM spread | H(P[c(b)]) − H(P[c(S)]) | yes |
| G1-N | Per-cell nClimGrid spread | H(N[c(b)]) − H(N[c(S)]) | yes |
| G1-P*, G1-N* | Per-cell vs ASOS (ins2 form) | H(G[c(b)]) − H(T_S) | continuity only |
| C1-N | nClimGrid county-average spread (published CSV) | H(N_cty[k(b)]) − H(N_cty[k(S)]) | yes |
| R-A | Regional factor, ASOS network, equal weight, LOO | H(mean_{N∪S∖b} T) − H(T_S) | yes |
| R-P, R-N | Regional factor, grid disc 30 km around S, equal (cos-lat) weight | H(mean_disc G) − H(G[c(S)]) | yes |
| R-A-PC, R-N-PC | Same as R-A / R-N with frozen PC1 weights (train, LOO, clipped, Σw = 1) | as above | exploratory (answers Q2) |
| P-A | Station pair, LOO: nearest of (N∖b) ∪ {S}; r = 0 if S is nearest | H(T_j*) − H(T_S) | yes |
| P-A-IDW | IDW (p = 2) of the 3 nearest in (N∖b) ∪ {S} | H(Σ w T) − H(T_S) | yes |

Grid cells are the cells containing the point. Rain uses the same designs on weekly totals.

**Metrics per (market, point, design), test window.**
1. HE = 1 − Var(E − H_S − r)/Var(E); ΔHE = HE − HE(D0). HE(D0) at each point is the EVAL-02 geography-basis number, also shown against distance.
2. β = Cov(u, r)/Var(r) with u = E − H_S; efficiency η = 2β − 1 (computed only where Var(r) > 0).
3. sd(r) and mean(r) per unit-day (per week for rain).
4. Book concentration per market κ = Var(Σ_b r_b)/(Σ_b sd(r_b))² ∈ (0, 1] (1 = no diversification; the production regional factor is a single contract, so κ = 1). Count of distinct residual contracts per market. ins2 variance ratio kept for continuity.
5. Indicative premium loading L = λ·sd(r), λ = 0.25 (sensitivities 0.10 and 0.50). Also as % of the station-leg 24 h ask premium (Phase 2 values; ins1 fallback NYC 1.73, CHI 3.14, MIA 4.79 per unit-day), and cost per HE point L/max(ΔHE, 0.01). Capital is Phase 4's job.
6. Descriptive (EVAL-02 extras, no pass rule): station-leg HE at every land cell within 40 km for both grids, correctly aligned (ins2 re-run on both grids); nearest-cell tmax RMSE and correlation vs ASOS for both grids, both alignments; PRISM `.stn.csv` contamination share per truth point.

**Inclusion per point.** At least 60 paying days (weeks: 20 non-zero) and Var(E) > 0 in the test window; missing inputs drop that day for that design; network means need ≥ 60 % of members present.

**Inference.** Joint circular block bootstrap: 14-day blocks (2-week blocks for weekly rain), 2,000 draws, seed 20260930, the same resampled calendar for every point and market. The pooled statistic is the median over all (market, point) pairs in the ≤ 50 km truth sets.

**Pass rule, temperature.** An eligible design SURVIVES if all of:
- P1 gain: pooled median ΔHE ≥ +0.10 and the bootstrap 95 % CI lower bound > 0.
- P2 breadth: ΔHE > 0 at ≥ 70 % of pairs, and the market-median ΔHE > 0 in ≥ 4 of 5 markets. Pairs where the design's residual is identically zero by construction (pair design where S is nearest; county design within S's county) are left out of the P2 denominator. They stay in the P1 pooled median at ΔHE = 0, because that is the design's real effect there.
- P3 efficiency: pooled median η ≥ 0.5.
- P4 settleable: a deterministic written formula on published data; no parameter changes after sale; a first settlement value within 7 days; a stated revision policy.
- Insurance-grade flag (reported, not gating): pooled median HE ≥ 0.70 (the ins1 T1 bar).
- KILL: pooled median ΔHE ≤ 0. The design is dropped from Phase 7.

**Pass rule, rain (weekly).** Same P1–P4, but P2 needs ≥ 3 of 5 markets (TTN has 2 rain points). Secondary, not gating: daily wet-day false-negative rate (point wet, index-implied hedge dry), relative change vs D0.

**Winner and ties.** Among survivors, the highest pooled median HE. If within 0.02, prefer fewer distinct contracts per market, then lower L. For Q2: PC1 replaces the equal-weight mean only if its pooled median HE is higher by ≥ 0.03 and the paired bootstrap CI of the difference excludes 0. Otherwise the equal-weight mean is the product formula. If nothing survives, the verdict is "no residual design clears the bar". Phase 7 then ships station-only cover plus RFQ bespoke residuals at a stated premium, and the report gives the best design's numbers anyway.

**Sensitivities (reported, never gating).** Unrounded temperatures; linear uncapped T; fixed monthly strike instead of trailing K; May–Sep only; metro mean excluding S; network radius 30 km and 70 km; grid disc 15 km and 40 km; PRISM grid count 8 only; β fitted on train and applied to test (the upper bound of a sized overlay); Kalshi-ladder sub-sample; CoCoRaHS weekly rain truth if Phase 1 pulls it.

**Deviations.** Any change after the freeze is logged in 03-04 with the reason and UTC time, and the pre-freeze version is also reported.

## Open Questions

1. **Which grid is closer to ASOS calendar-day tmax.** Unknown. Resolved by the pre-registered descriptive check. It does not gate the verdict.
2. **PRISM's handling of ASOS hourly data.** The inference that it aggregates to 12Z–12Z comes from the PRISM-day rule and the "ASOS/ISH" network listing, not a verbatim statement. Check the `.info.txt` / `.stn.csv` of one grid in 03-02.
3. **Size of the Central Park sensor bias.** Its direction is supported (park cool island); its size at the ASOS is not verified. The NYC results will show it as a persistent mean(r).
4. **RMA's NCEI product for PRF.** Not named in the release or on the RMA page. Likely nClimGrid-based. It matters only for the pitch, not for this evaluation.
5. **Interior truth.** Airports are open, often waterfront sites. Midtown, Loop and Brickell businesses are only proxied (JRB is the one quasi-interior NYC point). Results may understate basis for interior businesses. Candidate validation networks (NYSM NYC micronet, NJWXNET) have unverified access terms.
6. **Rain station leg.** Which Kalshi rain series are active and liquid, and which station the TWC-settled Chicago/Miami monthly series use, is for Phase 1/2 to answer. The rain evaluation does not depend on it.
7. **TTN rain set has 2 points** and the TTN temperature network has 5, so the TTN verdicts will have wide CIs. They are pooled, not decided alone.
8. **Provisional PRISM tail.** Roughly 2026-03..08 is below grid count 8 at pull time. The sensitivity covers it.

## Sources

### Primary (HIGH confidence)
- PRISM, *Descriptions of PRISM Spatial Datasets for the Conterminous US* (rev. Feb 2026): https://prism.oregonstate.edu/documents/PRISM_datasets.pdf (PRISM day, ±4 h rule, COOP day shift, CAI, radar/MRMS, network tables, ASOS ppt May–Sep footnote)
- PRISM update schedule: https://prism.oregonstate.edu/documents/PRISM_update_schedule.pdf ("grid for July 2 covers 1200 UTC July 1 – 1200 UTC July 2"; 8 releases)
- PRISM web service doc (26 Mar 2025): https://prism.oregonstate.edu/documents/PRISM_downloads_web_service.pdf ; terms: https://prism.oregonstate.edu/terms/ ; bulk note: https://prism.oregonstate.edu/downloads/
- Daly et al. 2021, JTECH 38:1979–1992, https://prism.oregonstate.edu/pubs/link/2021_daly-etal_jtech.pdf (PRISM daily ppt method, convective cells, 8 releases)
- NCEI nClimGrid-Daily User Guide: https://www.ncei.noaa.gov/data/nclimgrid-daily/doc/nclimgrid-daily_v1-0-0_user-guide.pdf ; readme/status in the same folder; NetCDF attributes of `data/raw/nclimgrid/ncdd-202608-grd-scaled.nc`
- Durre et al. 2022, JTECH 39(12):1837–1855, https://doi.org/10.1175/JTECH-D-22-0024.1 (abstract via OpenAlex; full text 403)
- NWS Chicago observations FAQ: https://www.weather.gov/lot/weather_observations_faq (LST climate day, 5-min averages, CLI vs METAR, Chicago CLI sites)
- IEM: https://mesonet.agron.iastate.edu/info/datasets/metar.html , https://mesonet.agron.iastate.edu/ASOS/precipnote.phtml , network geojson, `api/1/daily.json`, `json/cli.py` (station table computed 2026-09-30)
- USDA RMA RI-PRF summary: https://www.rma.usda.gov/sites/default/files/2024-05/risummary.pdf ; 2027 RI handbook: https://www.rma.usda.gov/sites/default/files/2026-04/27-18150-Rainfall-Index-Handbook.pdf ; data-source release 2026-04-30: https://www.rma.usda.gov/news-events/news/2026/washington-dc/usda-risk-management-agency-upgrades-rainfall-data-source ; https://www.rma.usda.gov/policy-procedure/general-policies/rainfall-index
- Prior results (read-only): ~/hl-mm-wt/corpus-fix/reports/ins1/README.md, reports/ins2/README.md; prior/hl-mm-ins/scripts/ins2/analyze.py

### Secondary (MEDIUM confidence: peer-reviewed; abstracts or publisher pages read, not full text)
- Woodard & Garcia 2008a, AFR 68(1):99–117, https://doi.org/10.1108/00214660880001221
- Woodard & Garcia 2008b, JARE 33(1):34–51, https://jareonline.org/articles/weather-derivatives-spatial-aggregation-and-systemic-risk-implications-for-reinsurance-hedging/
- Norton, Turvey & Osgood 2013, J. Risk Finance 14(1):20–34, https://doi.org/10.1108/15265941311288086
- Musshoff, Odening & Xu 2011, Applied Economics 43(9):1067–1077, https://doi.org/10.1080/00036840802600210
- Ritter, Musshoff & Odening 2014, Comput. Econ. 44(1):67–86, https://doi.org/10.1007/s10614-013-9410-y
- Barth, Benth & Potthoff 2011, Appl. Math. Finance 18(2):93–117, https://www.tandfonline.com/doi/full/10.1080/13504861003722385
- Leppert, Dalhaus & Lagerkvist 2021, WCAS 13(2):273–286, https://doi.org/10.1175/WCAS-D-20-0070.1
- Dalhaus & Finger 2016, WCAS 8(4):409–419, https://doi.org/10.1175/WCAS-D-16-0020.1
- Elabed et al. 2013, Agric. Econ. 44(4–5):419–431, https://doi.org/10.1111/agec.12025
- Miranda 1991, AJAE 73(2):233–242, https://doi.org/10.2307/1242708
- DeMiguel, Garlappi & Uppal 2009, RFS 22(5):1915–1953, https://doi.org/10.1093/rfs/hhm075
- Ensor & Robeson 2008, JAMC 47(9):2468–2476, https://doi.org/10.1175/2008JAMC1757.1
- Habib, Krajewski & Ciach 2001, JHM 2(6):621–629; Villarini et al. 2008, JGR 113 D11102, https://doi.org/10.1029/2007JD009214 ; Breinl, Müller-Thomy & Blöschl 2020, JHM 21(4):671–689, https://doi.org/10.1175/JHM-D-19-0228.1
- Yu, Vandeveer, Volesky & Harmoney 2019, JARE 44(1), https://jareonline.org/articles/estimating-the-basis-risk-of-rainfall-index-insurance-for-pasture-rangeland-and-forage/
- Keller & Saitone 2022, AJAE 104(4):1203–1223, https://doi.org/10.1111/ajae.12282
- Benami, Ramanujan & Cecil 2025, ARER, https://www.cambridge.org/core/journals/agricultural-and-resource-economics-review/article/rain-check-how-data-details-influence-payout-determinations-in-a-us-rainfall-index-insurance-program/7AB7CE27D0C28E2671FBCAF452AC833E
- Boyd et al. 2020, NAAJ 24(3):355–369, https://doi.org/10.1080/10920277.2019.1669055 ; Pelka & Musshoff 2013, AFR 73(2):358–372, https://doi.org/10.1108/AFR-10-2012-0055
- Central Park Conservancy cooling study (2022): https://www.centralparknyc.org/central-park-climate-lab-cooling-study

### Tertiary (LOW confidence: preprint or single source)
- Guo & Li 2023, arXiv 2311.14844 (kriging vs IDW vs nearest for daily rain), https://arxiv.org/html/2311.14844
- Kalshi rain series list (KXRAINNYC/NYCW/NYCM, KXRAINCHIM, KXRAINMIAM): shared-session series snapshot 2026-09-30, not re-queried here
- nClimGrid as RMA's NCEI product: secondary summaries only

## Metadata

**Confidence breakdown:**
- Standard stack and data conventions: HIGH. Read from the provider documents, file metadata and live endpoints.
- Architecture (LOO truth, same-source residuals, frozen weights): MEDIUM-HIGH. Follows from ins2's failure mechanics and the literature. The per-cell spread's performance is untested.
- Literature carry-over: MEDIUM. Mostly agricultural, and yield-based rather than point-weather-based.
- Pitfalls: HIGH for day conventions, revisions and contamination; MEDIUM for Central Park.
- Thresholds (ΔHE 0.10, η 0.5, 70 % breadth, λ 0.25): LOW-MEDIUM. Judgment anchored to ins1 (raw nearby HE 0.1–0.6, T1 bar 0.70). They are fixed now precisely so they cannot drift later.

**Research date:** 2026-09-30
**Valid until:** 2026-10-30 for the data conventions (stable); re-check the PRISM service and RMA/NCEI status if used after that.
