# Phase 5: Elasticity learning - Research

**Researched:** 2026-09-30
**Domain:** Daily sales-vs-weather regression, hierarchical shrinkage, weather hedge design from Kalshi ladders, out-of-sample hedge evaluation
**Confidence:** MEDIUM (data access and Kalshi history verified live today; regression and shrinkage choices rest on published abstracts plus standard econometrics; effect sizes and thresholds are priors, not measurements)

## Summary

The method is standard and fits in a few hundred lines of statsmodels. Per business (a "unit"), regress log daily sales on calendar controls (day of week, holidays, trend, annual Fourier terms) plus weather terms. The heat term is **the hedge payoff itself**, `min(max(T − K, 0), cap)`, measured on the Kalshi settlement station's NWS climate-report high. The rain term is a wet-day indicator that matches the daily rain binary. By Frisch-Waugh, the coefficient on the payoff, after controls, is the minimum-variance hedge ratio. It turns into Kalshi contracts per day as `units_t = forecast_revenue_t × |β|`. Shrink each unit's coefficient toward a group prior with parametric empirical Bayes: DerSimonian-Laird or Paule-Mandel τ² from `statsmodels.stats.meta_analysis.combine_effects`, estimated leave-one-out and only on data before the forecast origin. This is Bühlmann credibility, and it is the same closed form the portal can run on a new business's CSV. MixedLM is only a cross-check.

Live checks today turned up two facts that change the plan. (1) **Real historical asks exist for five years.** `GET /historical/markets?series_ticker=KXHIGHNY` returns 9,286 markets (1,816 events, 2021-08-06 to 2026-07-30, old `HIGHNY-` tickers included). `GET /historical/markets/{ticker}/candlesticks` returns hourly yes bid/ask for 2022, 2024 and 2025 markets, and Chicago settled at Midway in every year sampled (2023 to 2026). "Estimate on year 1, hedge year 2 at real asks" is therefore doable for 2024→2025 and 2023→2024. It is not stuck with the 68 days ins1 used. (2) **Daily ladders list about 39 hours before close.** For example, `open_time` is D−1 14:00Z and close is D+1 04:59Z. So a ladder bought 24 h out is priced on tomorrow's forecast and moves only the forecast surprise. Scoring a hedge by "payout vs loss" and leaving the premium out overstates what the business gets. Computed from the ins1 rows as a design check (not a Phase 5 result): NYC HE is 0.94 on payout alone but 0.53 net of the 24 h premium, and 0.02 net of the 2 h premium. Phase 5 must report two numbers, **HE_cover** (payout vs loss) and **HE_ladder** (payout minus real ask vs loss). The gap between them is the forecast-level risk the house or pool carries on the default path. Phase 4 and Phase 14 need that number.

On data: there is no Kaggle key (`~/.kaggle/kaggle.json` is absent), so Rossmann and M5 are out. They also have no Kalshi-city location. The usable stand-ins near Kalshi cities are Citi Bike (NYC) and Divvy (Chicago) station-day starts, which are strongly weather-driven, CTA 'L' station-day entries (foot traffic, weather-light), and taxi revenue by zone or community area (real dollars: NYC TLC, Chicago Taxi Trips). I found no public daily revenue series for a real single small business near NYC or Chicago. Miami has no daily stand-in. Bikeshare is far more weather-driven than a restaurant, so results must be reported by sector and never pooled into one headline.

**Primary recommendation:** Per-unit log-linear OLS with HAC standard errors. Use the capped heat payoff and a wet indicator as the weather regressors, taken from IEM's NWS CLI values for KNYC and KMDW. Shrink with empirical Bayes toward a sector×city prior. Evaluate 2024→2025 (TLC: 2023→2024) at real 24 h Kalshi asks with fees. Report HE_cover and HE_ladder per arm (none / own / pooled / EB / oracle) with a day-block bootstrap. Build the days-of-history curve over three forecast origins.

## Verified Facts That Constrain the Plan (checked live 2026-09-30)

| Fact | How verified | Consequence |
|---|---|---|
| Markets settled before 2026-08-01 are served only by `/historical/*`; `GET /historical/cutoff` returns `market_settled_ts: 2026-08-01` | curl, keyless | Candle puller must call `/historical/markets/{ticker}/candlesticks` for older markets; `/series/{s}/markets/{t}/candlesticks` returns 404 for them |
| KXHIGHNY history spans 2021-08-06 to now (5,416 `HIGHNY-` + 3,870 `KXHIGHNY-` markets); KXHIGHCHI history is also paged back from 2026-07-31 (earliest not measured) | paginated `/historical/markets` | Real asks exist for 2023, 2024 and 2025 hedge years |
| Historical candles carry `yes_ask`/`yes_bid` OHLC as strings under key `close` (the live endpoint used `close_dollars` in ins1 code) | 3 tickers (2022, 2024, 2025) | Parser must accept both keys |
| 2022 events had 4 brackets; 2023+ have 6 (`greater`/`less`/`between`); `less` with cap 84 sits next to `between` 84–85, so `less cap=c` means T ≤ c−1 | event listings | ins1 used H(cap) for the bottom bracket (off by one); fix in the mapper |
| Daily high ladders open D−1 14:00Z; close D+1 03:59Z (2021–25) / 04:59–05:00Z (2026) | market metadata | No season-ahead hedge via daily ladders; 24 h decision ≈ 00:00–01:00Z on D |
| Chicago settles at Midway in 2023, 2024, 2025, 2026 rules | `rules_primary` | Weather regressor for Chicago = KMDW |
| KXHIGHNY lists settlement source "The Weather Company"; KXRAINNYC lists "NWS Climatological Report"; rules text for highs cites the NWS climate report | `/series` | Keep ins1's TWC-vs-NWS mismatch check (0–4 %) |
| NYC daily rain binary `KXRAINNYC`: 895 settled markets 2021-09-08 to 2026-07-15 (gaps; fewer than one per day) | `/historical/markets` | NYC rain leg can be priced at real asks on the days it listed |
| Multi-city daily `KXRAIN-{date}-{CITY}` (NYC, CHI, MIA, EWR, TTN, …) exists for 2026-09-01, not for 2026-07-01; resolves YES if CLI precipitation "strictly greater than 0 inches" | event probes | No Chicago daily-rain asks before ~Aug/Sep 2026 → Chicago rain = policy frame only; trace handling unverified |
| Monthly rain: KXRAINNYCM since 2024-02 (176 markets), KXRAINCHIM since 2025-06 (57); weekly NYC KXRAINNYCW only live | `/historical/markets` | Amount-based rain hedges have poor history; hedge the wet indicator only |
| IEM serves the exact NWS CLI daily values (`/json/cli.py?station=KNYC&year=YYYY`), trace as `"T"`, with the CLI product issue time; IEM ASOS daily differs by 1 °F on some days (2025-07-03: CLI 88, ASOS daily 87); IEM daily encodes trace as 0.0001 | curl | Use CLI as the weather regressor (it is the settlement source); map trace explicitly |
| IEM GFS MOS archive answers for KNYC (runtime 2025-07-01 12Z) | curl | Fallback fair price for days with no usable Kalshi quote |
| Data lags: Citi Bike and Divvy through 2026-08; TLC yellow through 2026-07 (Aug = 403); CTA daily entries through 2026-07-31 (from 2001); Chicago Taxi Trips (2024-) through 2026-09-01; MTA hourly (2025+) updated 2026-09-23 | S3 listings, HEAD, SoQL | Hedge windows ending ≤ 2026-06-30 are feasible for every listed dataset |
| `~/.kaggle/kaggle.json` absent | `ls` | Rossmann/M5 excluded |
| venv: Python 3.14.0, statsmodels 0.15.0 (formula engine default `patsy`; `formulaic` 1.2.2 also installed), pandas 3.0.6, numpy 2.5.3, scipy 1.18.1, duckdb 1.5.6; **not installed:** scikit-learn, linearmodels, arch, holidays | uv.lock + import test | Everything needed is already installed; `arch` optional |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| statsmodels | 0.15.0 (installed) | Per-unit OLS with HAC SEs (`fit(cov_type="HAC", cov_kwds={"maxlags": 7})`), GLM Poisson (PPML) for count robustness, `MixedLM` cross-check, `meta_analysis.combine_effects` for τ² | Reference implementation for all three; verified in the venv today |
| pandas | 3.0.6 (installed) | Panels, calendars (`pandas.tseries.holiday.USFederalHolidayCalendar`), tz handling | Already the project's frame library; copy-on-write default in 3.x |
| numpy / scipy | 2.5.3 / 1.18.1 | Hinge/payoff math, bootstrap indices | — |
| duckdb | 1.5.6 (installed) | Trip-level → unit-day aggregation over CSV/Parquet (Citi Bike, Divvy, TLC via httpfs) without loading raw rows into pandas | Handles tens of millions of rows per month on a laptop |
| patsy (via statsmodels formulas) | 1.0.3 | `cr(x, df, constraints='center')` splines for shape diagnostics; stateful transforms re-apply knots in `predict` | Default formula engine in statsmodels 0.15 (verified `options._formula_engine == 'patsy'`) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| statsmodels.tsa.deterministic (`DeterministicProcess`, `CalendarFourier("YE", 3)`) | 0.15.0 | Fourier terms with clean `out_of_sample(steps)` extension | If you want deterministic terms generated rather than hand-written sin/cos (both fine; see Code Examples) |
| arch | latest (optional, `uv add arch`) | `MovingBlockBootstrap` / `StationaryBootstrap` | Only if the planner prefers a library over the 10-line block sampler below |
| matplotlib | installed | Learning-curve and HE figures for reports/eval-06/ | Phase 5 plan 05-04 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Two-stage EB (per-unit OLS → `combine_effects` → shrink) | `MixedLM` with random slopes (`re_formula="~heat + wet"`) | MixedLM forces common DOW/season fixed effects across units or explodes the fixed-effect count, converges slowly or hits boundary at 70k+ rows (warnings seen even on a toy fit), and cannot be run by the portal for one new CSV. Use once as a cross-check on one group. |
| Two-stage EB | Full Bayes (PyMC/Bambi/Stan) | Better uncertainty, but new heavy deps and minutes per fit; no gain for a 2-day prototype |
| log-OLS | PPML (`GLM(family=Poisson())`) | Needed only where zeros exceed ~2 % of unit-days (low-volume stations); gives the same semi-elasticity interpretation. Robustness arm, not primary |
| Capped hinge at group K | Restricted cubic spline / 5 °F bins | Better for describing shape; does not map to a contract. Use for diagnostics and choosing K, not for the hedge ratio |
| linearmodels `PanelOLS` | — | Not needed (no pooled two-way FE estimate is on the critical path); do not add the dependency |
| scikit-learn `TimeSeriesSplit` | explicit origin dates | Origins must be calendar-anchored (season matters); a generic splitter hides that |
| Prophet | — | Stan dependency, opaque seasonality, slow per unit; nothing it does is needed |

**Installation:** nothing required. Optional: `uv add arch` (bootstrap).

## Architecture Patterns

### Recommended Project Structure
```
src/wi/elasticity/
├── panel.py        # unit-day panels from Phase 1 aggregates + CLI weather join (point-in-time, local business day)
├── design.py       # controls, Fourier, holidays, capped heat payoff, wet flags, lags; one function used by fit AND portal
├── estimate.py     # per-unit OLS (HAC), K profile at group level, baseline forecast F_t
├── shrink.py       # EB priors per group (leave-one-out), posterior β̃, priors.json writer
├── hedge.py        # units_t, bracket mapping (rep values), premium at asks + fees, rain binary, P&L legs
├── evaluate.py     # arms, HE_cover / HE_ladder, weekly HE, day-block bootstrap, learning curve, placebo
└── priors.json     # (artifact) per group: K, cap, mu/tau2 for heat & wet, seasonal offset coefs — consumed by Phase 7/9/10
reports/eval-06/     # PREREG copy, results tables, figures, manifest of inputs (md5)
```

### Pattern 1: Unit-day panel with point-in-time weather
**What:** One row per (unit, local business day): `y` (sales, scaled), `tmax_f` (CLI high, int °F), `prcp_in` (CLI precip, trace → 0.0 with a `trace` flag), `snow_in`, calendar fields, and the Kalshi keys (`event_ticker` for that day).
**When:** Every downstream step reads this and nothing else.
**Rules:**
- Business day = local calendar date (`America/New_York` / `America/Chicago`). Trip timestamps in Citi Bike, Divvy, TLC and Chicago taxi are naive local times: localize to the city tz (`ambiguous="NaT"`, `nonexistent="shift_forward"`), store UTC, and derive `date_local`. Never localize them as UTC.
- The NWS climate day is local **standard** time: 00:00–23:59 LST, which is 01:00–00:59 local time during DST. Kalshi's 2026 close at 05:00Z (01:00 EDT) matches this. Sales days are midnight to midnight. Accept the 1-hour offset and document it. It matters only for late-night taxi revenue.
- Scale: `y_scaled = y × (1500 / mean(y over the estimation window))`, so every unit looks like a ~$1,500/day business. The factor is fixed at the origin. This makes contract counts and Kalshi depth caps realistic and leaves HE unchanged.
- Drop unit-days where the unit did not exist (station not yet installed or removed). Keep weather-driven closures (Citi Bike suspends service in severe storms). They are real losses, so flag them.

### Pattern 2: Estimator = hedge payoff as regressor (per unit)
**What:** Log-linear OLS whose weather regressors are exactly the contract payoffs. The coefficient is then both the "elasticity" and the minimum-variance hedge ratio, conditional on controls (Ederington 1979 for MV hedging; Frisch-Waugh for the partialling out).
**When:** Every arm except "pooled-only" and "oracle".
**Why this form:** Retail weather studies use log daily sales with calendar controls and find nonlinear weather effects (Roth Tran 2023; Badorf & Hoberg 2020; Štulec et al. 2019). Roth Tran's baseline (read in the FRBSF working paper) is `ln(net sales_it) = ω·weather_it + date FE + store×month FE + store×day-of-week FE + store-specific linear and quadratic trends + opening/closing indicators`. Zero-sales (closed) days are dropped, and SEs are clustered by store and date. Her dynamic version adds weather leads (7 days) and lags (21 days). Negative weather shocks leave significant net losses after three weeks, while positive shocks may be partly intertemporal shifts. Bikeshare and cycling studies use log-linear or count models with calendar controls. They find temperature effects that turn negative above about 27–28 °C (81–82 °F), rain entering as both presence and amount, and lagged rain effects (Miranda-Moreno & Nosal 2011; An et al. 2019; Bean et al. 2021). Building-energy practice formalises the "flat, then linear above a change point" response as ASHRAE Guideline 14 change-point models (3P/4P/5P). A 4P heat change point is exactly the capped-linear payout with K = change point.

### Pattern 3: Two-stage empirical Bayes (credibility) shrinkage
**What:** Stage 1 gives per-unit (β̂_i, s_i) from HAC OLS. Stage 2 estimates the group prior (μ_g, τ²_g) with `combine_effects(β̂_{-i}, s²_{-i}, method_re="chi2")` (DerSimonian-Laird) or `"iterated"` (Paule-Mandel), leaving unit i out. Then `β̃_i = μ_g + B_i (β̂_i − μ_g)` with `B_i = τ²_g / (τ²_g + s_i²)`.
**When:** Arm A3 (EB). Arm A2 (pooled-only) uses μ_g alone. A new portal business with n days of history gets its own β̂(n), s(n) and the stored sector prior. Nothing else is needed.
**Groups:** sector × city (bike-NYC, bike-CHI, transit-CHI, taxi-CHI, taxi-NYC), split into Y1 volume terciles if τ² appears to depend on volume. This handles the "precision-dependence" problem: low-volume units have larger s_i and may have different true β.
**Evidence it helps:** James-Stein and parametric EB dominate unit-by-unit estimates in total squared error once there are three or more units, and the gain grows with s_i²/τ² (Efron & Morris 1975). Shrunk estimates equal Bühlmann credibility weights. Hierarchical store-level elasticities improved pricing decisions in grocery scanner data (Montgomery 1997). Partial pooling is used for temperature-sensitivity curves of energy demand (Hinrichsen, Rehdanz & Tol 2025). **I found no study that measures the EB gain for weather sensitivities at 100–365 days of history.** Phase 5's learning curve produces that evidence.
Back-of-envelope, LOW confidence: with a residual SD of 0.15–0.25 log points, the heat-slope SE at 365 days is about 0.5 %/°F. A synthetic check today gave SE 0.0058 at σ = 0.15. That is larger than a restaurant-like heat effect (~0.3 %/°F) but smaller than a bikeshare effect (2–3 %/°F). Expect large EB gains for weather-light sectors and for n ≤ 180, and small gains for bikeshare at n ≥ 365.

### Pattern 4: Elasticity → hedge (capped-linear, ins1 mapping, rain binary, residual leg)
- **Payoff:** `g(T) = min(max(T − K_g, 0), cap)` per unit. K_g is set per group by profile SSR over K ∈ {75, …, 92} °F on estimation-window data, summed across the group's units (not per unit, which overfits). cap = 10 °F primary, 6 °F sensitivity (ins1 used 6).
- **Units per day:** `h_t = F_t × (−β̃_heat)` in $ per °F, where F_t is the unit's climatological-weather revenue forecast (scaled $). A positive h buys cover (the business is short heat). A negative h means the business is long heat, so it sells the ladder at bids (NO ask = 1 − YES bid). The linearisation `exp(β g) − 1 ≈ β g` over-hedges by up to ~15 % at g = 10 with β = −0.03; levels-model sizing is the sensitivity check.
- **Ladder replication (ins1 method, corrected):** for each bracket b, the representative integer value r_b is (floor+cap)/2 for `between` (inclusive integers), floor+1 for `greater`, and cap−1 for `less`. Derive each bracket's integer set from `rules_primary` ("greater than"/"less than") and cross-check it against floor/cap. Buy `q_b = round(h_t × g(r_b))` YES contracts. Per-unit ladder payout: `X_lad = g(r_{b*})` for the winning bracket b*, so the leg's P&L is `h_t·X_lad − π_t`. Binning error `g(T) − g(r_{b*})` is at most about 0.5 per unit on interior brackets and larger in open tails. When K lies above the ladder's top floor+1, the portfolio buys nothing, and any realised payout is an "unspanned" error. Record it separately.
- **Premium at asks:** `π_t = Σ_b q_b × ask_b + fees_b`. ask_b is the `yes_ask.close` of the last hourly candle with `end_period_ts ≤ close_ts − 24h`, with at most 6 h staleness. Apply the ins1 no-offer rule (ask ≥ 0.99 and bid < 0.90, or missing). If any bracket with q_b > 0 has no offer, the day is unhedgeable at 24 h: set h_t = 0 and count it. Fees follow Kalshi's quadratic taker fee (series `fee_type: quadratic, fee_multiplier: 1`), applied per bracket order (formula in Code Examples).
- **Rain:** wet_t = 1{CLI precip ≥ 0.01"} (trace = dry, pending the Phase 2 check against settled KXRAINNYC). Units `h^w_t = F_t × (1 − exp(β̃_wet))` YES contracts of that day's KXRAINNYC (payout $1, no binning). Chicago rain uses the policy frame only (no daily asks before ~Sep 2026).
- **Two instruments jointly:** estimate heat and wet in the same regression. Hot and wet days are negatively correlated, so the joint coefficients are the multi-instrument MV ratios (Σ_XX⁻¹ Σ_XU).
- **Residual leg (secondary, only if Phase 3 has a verdict):** re-estimate on local weather (nearest PRISM/nClimGrid cell with the label-D = calendar-D+1 shift, or the nearest ASOS: LGA/JFK for Queens, ORD for north-side Chicago). Add a residual payout `h_t × (g(T_local) − g(r_{b*}))` settled on the Phase 3 index, and report the incremental HE. The primary estimate stays on the settlement-station CLI, because the MV ratio for the ladder is the regression on the ladder's own underlying.

### Pattern 5: Evaluation frames, arms and origins
- **Unexpected revenue:** `U_t = y_t − F_t`. F_t comes from the origin-time model with the trend frozen at the origin, Fourier terms by day of year, DOW and holidays, and the weather terms set to their **climatological expectation** for that calendar day: E_clim[g(T)] and P_clim(wet), from station history before the origin, day-of-year ±7 days, 30 years. The predictable seasonal weather effect is therefore not counted as risk. U is common to all arms at a given origin and unit, from the longest-history model available at that origin, so arms differ only in h.
- **HE_cover (policy frame, pre-cost):** `1 − var(U + h(X − E_clim X)) / var(U)`, with X = g(T_CLI) exact. Cost reported separately as `Σ h × load × E_clim X`, where load = the city's realised ladder cost ratio (premium + fees − payout)/payout from the execution frame, so the policy price reflects what the house pays to hedge.
- **HE_ladder (execution frame, at real asks):** `1 − var(U + h·X_lad − π) / var(U)` over days; realised cost `mean(π − h·X_lad)`. Also report the ladder-transferable share `HE_ladder / HE_cover`.
- **Windows:** heat-only HE over Jun 1–Sep 30; heat+rain over all days; each daily and summed by ISO week. Weekly sums net out intertemporal substitution. Roth Tran 2023: a one-SD one-day shock moves sales about 10 % over four weeks; bad-weather losses persist, good-weather gains may be shifted demand.
- **Arms:** A0 no hedge; A1 own OLS; A2 pooled μ_g (leave-one-out); A3 EB β̃; A4 oracle (MV ratio fit on the hedge year itself; an upper bound, never a strategy).
- **Placebo:** fit A3 on estimation-window sales paired with a *different year's* weather aligned by day of year (so the seasonality stays and the day-to-day weather is wrong), then hedge the real hedge year with real weather. The group μ must be insignificant and the median HE_cover ≤ 0.02. Otherwise the controls are letting seasonality masquerade as weather sensitivity.

### Anti-Patterns to Avoid
- **HE from payout alone at ladder prices.** A 24 h ladder premium already contains the forecast. Always report HE_ladder net of premium. The ins1 rows show 0.94 → 0.53 (NYC, 24 h).
- **Treating units as independent.** All NYC units share the same 365 weather days and one summer. Bootstrap days, not units.
- **Per-unit K search or per-unit spline df with 100 days.** Pure noise. K is fixed per group from pre-origin data.
- **Fourier annual terms with n < 365.** Season and weather cannot be separated. Use the group seasonal offset (Pre-registration §3).
- **Using the hold-out year for anything but scoring:** scale factor, K, trend, the EB prior and the climatology all come from before the origin. AGENTS.md names "a hedge ratio computed on the hold-out days" as a test-worthy failure.
- **Pooling sectors into one headline HE.** Bikeshare HE says nothing about a café.

## Recommended Estimator Spec

| Item | Specification |
|---|---|
| Unit | One stand-in "business": Citi Bike/Divvy start station, CTA station, TLC zone (PULocationID), Chicago community area |
| Target | `ly = log(y_scaled)`; units with > 2 % zero days → PPML robustness (GLM Poisson, log link, HAC) |
| Controls | `C(dow)`; `hol`, `hol_m1`, `hol_p1` (US federal via pandas calendar + Dec 24, Dec 31, day after Thanksgiving); `trend` (years since window start, linear); Fourier annual k = 1..3 (n ≥ 365) **or** group seasonal offset (n < 365); `snow` indicator (CLI snowfall ≥ 1.0") for NYC/CHI |
| Temperature | `tlin = min(T, K_g)` (slope below the change point) + `heat = clip(T − K_g, 0, cap)` (the payoff; slope above K). T = CLI daily high, int °F, settlement station (KNYC / KMDW) |
| Rain | `wet = 1{P ≥ 0.01"}` (the hedged leg); `heavy = 1{P ≥ 0.50"}` (control, unhedged); `wet_l1` (lag) |
| Lags | `wet_l1`, `heat_l1` (controls; net effect = β + β_l1 reported; the hedge uses contemporaneous β) |
| SEs | HAC Newey-West, `maxlags=7` |
| Diagnostics (not for the hedge) | `cr(T, df=5, constraints='center')` shape plot per group; 5 °F bins; K profile curve |
| Outputs per unit | β̂_heat, s_heat, β̂_wet, s_wet, β̃ (EB), B_i (credibility weight), K_g, cap, F_t for the hedge window, h_t series, in-sample R², out-of-sample HE_cover/HE_ladder per arm |
| Shrinkage | Group = sector × city (× volume tercile if needed); prior (μ_g, τ²_g) via `combine_effects(..., method_re="chi2")`, leave-one-out, pre-origin only; τ² = 0 boundary → full pooling (report how often) |
| Portal version | Same `design.py` + OLS + stored priors.json; no MixedLM; closed form so a TS port can match it to 1e-6 on a fixture |

## Datasets (ranked for "mimics a small business near a Kalshi city")

| Rank | Dataset | Unit / measure | Weather class | Access (verified) | Pitfalls |
|---|---|---|---|---|---|
| 1 | Chicago Taxi Trips (2013–2023 `wrvz-psew`, 2024– `ajtu-isnz`) | community-area-day Σ `fare` | moderate (rain probably raises demand; sign unverified, let the data say) | Socrata; aggregate **server-side** with SoQL `$select=pickup_community_area, date_trunc_ymd(trip_start_timestamp), sum(fare), count(*)&$group=…`; data to 2026-09-01 | Real dollars but pooled across many drivers, so smoother than one shop; timestamps rounded to 15 min; suppressed areas; use `fare` not `trip_total` (tips only on cards) |
| 2 | NYC TLC yellow + green | PULocationID-day Σ `fare_amount` | moderate | CloudFront Parquet, DuckDB httpfs; to 2026-07 | **Congestion pricing (CBD toll) began 2025-01-05 ($0.75 per taxi trip in the zone)**, a structural break at the 2024→2025 boundary, so the TLC primary split is 2023→2024; use `fare_amount`, not `total_amount` (surcharges); FHVHV files are ~0.5 GB/month (skip) |
| 3 | Citi Bike (NYC) | start-station-day ride count | **heavy** (upper bound) | public S3 `tripdata`; 2024 monthly zips 0.37–0.81 GB; to 2026-08 | Far more weather-driven than restaurants; supply-censored at full/empty docks on peak days; station IDs changed in 2021 and stations churn; e-bike share and pricing changes; service suspensions in storms |
| 4 | Divvy (Chicago) | docked start-station-day count | heavy | public S3 `divvy-tripdata`; to 2026-08 | Many e-bike trips have null station (drop); same censoring/churn issues |
| 5 | CTA 'L' daily entries (`5neh-572f`) | station-day entries | light (foot-traffic proxy) | Socrata, 2001-01-01 → 2026-07-31 | Construction closures (structural breaks); commuter-dominated, so a weather-light control group |
| 6 | MTA subway hourly (`wujg-7c2s` 2020–24, `5wq4-mkjj` 2025+) | station-complex-day | light | Socrata SoQL day aggregation | Payment-method splits; OMNY transition; optional NYC twin of CTA |
| — | Rossmann, M5 | — | — | **No Kaggle key**; Rossmann is German stores, M5 has state-level location only | Excluded |
| — | Iowa Liquor Sales | store-invoice-day | — | Socrata (endpoint erratic today) | Wholesale orders to the state on weekly cycles, not consumer sales; no Kalshi city. Excluded |
| — | Miami | — | — | none found | No daily stand-in; Phase 5 is NYC + Chicago only |

**Volume realism:** a café does ~150–500 transactions a day. Aggregates (zones, busy stations) are smoother than that, which biases HE upward. Mitigations: (a) report HE by Y1 volume tercile; (b) a pre-registered sensitivity that binomially thins count series to a mean of 150/day, which injects realistic Poisson noise.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Autocorrelation-robust SEs | Manual Newey-West | `OLS.fit(cov_type="HAC", cov_kwds={"maxlags":7})` | Kernel/lag edge cases; s_i feeds the shrinkage weights, so it must be right |
| Between-unit variance τ² | Hand-coded moment estimator | `statsmodels.stats.meta_analysis.combine_effects(eff, var, method_re="chi2")` (or `"iterated"`) → `.tau2`, `.mean_effect_re` | DL and PM with truncation at 0 handled; verified in the venv |
| Spline bases with out-of-sample prediction | Hand knots | patsy `cr(T, df=5, constraints='center')` inside the formula; `results.predict(newdf)` reuses the knots | Unconstrained `cr()` is rank-deficient with an intercept (seen today) |
| Fourier/calendar terms that extend past the sample | Ad-hoc index math | `DeterministicProcess(..., additional_terms=[CalendarFourier("YE",3)])` + `.out_of_sample()`, or day-of-year sin/cos from the date (never from row position) | Row-position Fourier breaks on gaps |
| US holidays | Hard-coded dates | `pandas.tseries.holiday.USFederalHolidayCalendar` (+ 3 manual retail days) | Observed-date rules |
| Trip → unit-day aggregation | pandas on raw CSVs | DuckDB SQL over the monthly files; Socrata SoQL `$group` for CTA, MTA and Chicago taxi | Tens of millions of rows per month; SoQL avoids downloading 18M+ rows |
| NWS settlement values | Deriving daily max from METARs | IEM `/json/cli.py` (CLI) | CLI is the settlement source; ASOS-derived daily differs by 1 °F on some days |
| Kalshi bracket semantics | Parsing tickers (`B84.5`, `T91`) | `strike_type`, `floor_strike`, `cap_strike` + `rules_primary` text | 2021–22 markets lack `strike_type` fields in some rows; the ticker suffix is ambiguous for `T` |
| Block bootstrap | (optional) | `arch.bootstrap.MovingBlockBootstrap`, or the 10-line sampler in Code Examples | Either is fine; must resample days jointly across units |

**Key insight:** every piece here is textbook. The value is in the discipline: common-baseline U, net-of-premium HE, pre-origin priors, day-level inference. Planner tasks should spend their effort there, not on clever models.

## Common Pitfalls

### Pitfall 1: Forecast-conditioned premium makes "HE" meaningless
**What goes wrong:** The hedge scores 0.9 because payout tracks the loss, but the business paid for it at a price that already knew tomorrow's forecast.
**Why:** Daily ladders open ~39 h before close. The 24 h ask ≈ E[payout | forecast].
**How to avoid:** Report HE_ladder net of the ask premium alongside HE_cover. In the ins1 rows, HE falls from 0.94 to 0.53 (24 h) and 0.02 (2 h). ins1's K floated with the ladder (the second bracket's floor; 62–90 °F in NYC, SD 6.6 °F), so its surprise share is higher than it will be at a fixed business K. Expect a lower HE_ladder in Phase 5.
**Warning signs:** HE_ladder ≈ HE_cover; premium at 24 h uncorrelated with the realised payoff.

### Pitfall 2: Look-ahead through "harmless" parameters
**What goes wrong:** The scale factor, K_g, EB prior, trend or climatology is computed on data that includes the hedge year.
**How to avoid:** One `origin` argument threads through every fit. Add a test that corrupts hedge-year sales (e.g., multiplies them by 10) and asserts that h_t and priors.json are byte-identical. This is the AGENTS.md "hedge ratio computed on the hold-out days" failure.
**Warning signs:** In-sample HE ≈ out-of-sample HE; placebo HE_cover > 0.02.

### Pitfall 3: One summer is the real sample size
**What goes wrong:** Hundreds of stations look like hundreds of tests. In fact there are ~120 Jun–Sep days and ~15–30 days above K in a year, shared by every unit in the city.
**How to avoid:** Day-block bootstrap (7-day blocks, same indices for every unit), two hedge years (2024 and 2025 as replication), and report the number of payout days.
**Warning signs:** Very tight CIs; results flip between hedge years.

### Pitfall 4: Seasonality and temperature are collinear with short history
**What goes wrong:** With n < 365, Fourier or month terms soak up the heat effect, or the heat coefficient absorbs seasonality.
**How to avoid:** Below 365 days, use the group seasonal offset. Choose K at the group level. Let EB carry short-history units.
**Warning signs:** Wrong-sign heat coefficients at n = 60–120; huge SEs.

### Pitfall 5: Structural breaks unrelated to weather
- TLC: congestion pricing, Jan 2025 (use 2023→2024 for TLC).
- COVID-19: exclude anything before 2022-07-01.
- Citi Bike and Divvy: station openings and removals, dock changes, pricing and e-bike changes.
- CTA: station construction closures.
**How to avoid:** Eligibility requires a unit active on ≥ 98 % of days across the full window. Also run a level-shift diagnostic on the estimation window, and exclude and log units with a break.

### Pitfall 6: Bracket and settlement semantics
- The `less` bracket with cap c means T ≤ c−1. ins1 used c, which is off by one.
- Historical candles use `close`, not `close_dollars`.
- 2022 ladders had 4 brackets.
- KXHIGH* now lists TWC as source, while the rules cite the NWS CLI.
- KXRAIN counts precipitation "strictly greater than 0 inches". Whether a trace counts is unverified.
- IEM encodes trace as 0.0001 in daily.py and `"T"` in the CLI JSON.
**How to avoid:** Map brackets from the rules text. Measure the CLI-vs-Kalshi-result mismatch per year (ins1 found 0–4 %).

### Pitfall 7: Bikeshare flatters the product
**What goes wrong:** The bikeshare HE becomes the deck number for "small businesses".
**How to avoid:** Headline tables are per sector. Bikeshare is labelled "weather-heavy upper bound", CTA and taxi "weather-light/moderate". The deck claim is limited to sectors that pass T2.

### Pitfall 8: Supply censoring and closures
Bikeshare starts are capped by the bikes available, so the true demand response on perfect days is understated. Service suspensions in storms show up as extreme weather effects. Keep them (they are real losses to a business) but flag them. Report HE with and without suspension days.

### Pitfall 9: τ² at zero, and a prior that isn't credible
With a few units or noisy estimates, DL/PM return τ² = 0 (seen in a toy run today), so every unit gets the group mean. Report the share of groups at the boundary. For a new portal sector without a stand-in panel, the prior is **not** learned. Flag it in the UI.

### Pitfall 10: Date fixed effects in a same-city panel
Roth Tran uses date FE because her stores span many MSAs with different weather. Every Phase 5 unit in a city shares one settlement station, so date FE (or any common day effect) absorbs the weather completely and β becomes unidentified. Use per-unit calendar controls only. The pooled MixedLM cross-check must not add day effects either.

### Pitfall 11: pandas 3 copy-on-write
Chained assignment (`df[df.x>0]["y"] = …`) silently does nothing in pandas 3. Use `.loc`. The panel builder should also assert row counts per unit.

## Code Examples

Verified in the project venv today (Python 3.14, statsmodels 0.15.0, pandas 3.0.6) on synthetic data. The heat coefficient came back as −0.0275 against a true −0.03 (SE 0.0058, n = 366, σ = 0.15).

### Design + per-unit fit (primary spec, n ≥ 365)
```python
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from pandas.tseries.holiday import USFederalHolidayCalendar

def capped_hinge(T, K, cap):             # the contract payoff; also the regressor
    return np.clip(T - K, 0.0, cap)

def design(df, K, cap, fourier=3):       # df: DatetimeIndex (local business day), cols y, tmax_f, prcp_in
    d = df.copy()
    doy = d.index.dayofyear.to_numpy()
    for k in range(1, fourier + 1):      # from the date, never from row position
        d[f"s{k}"] = np.sin(2*np.pi*k*doy/365.25); d[f"c{k}"] = np.cos(2*np.pi*k*doy/365.25)
    hol = USFederalHolidayCalendar().holidays(d.index.min(), d.index.max() + pd.Timedelta(days=1))
    d["hol"] = d.index.isin(hol).astype(int)
    d["hol_m1"] = d.index.isin(hol - pd.Timedelta(days=1)).astype(int)
    d["hol_p1"] = d.index.isin(hol + pd.Timedelta(days=1)).astype(int)
    d["dow"] = d.index.dayofweek
    d["trend"] = (d.index - d.index.min()).days / 365.25
    d["tlin"] = np.minimum(d["tmax_f"], K)
    d["heat"] = capped_hinge(d["tmax_f"], K, cap)
    d["wet"] = (d["prcp_in"] >= 0.01).astype(int)      # CLI 'T' mapped to 0.0 upstream
    d["heavy"] = (d["prcp_in"] >= 0.50).astype(int)
    d["wet_l1"] = d["wet"].shift(1).fillna(0)
    d["ly"] = np.log(d["y"])
    return d

F = ("ly ~ C(dow) + hol + hol_m1 + hol_p1 + trend + s1 + c1 + s2 + c2 + s3 + c3"
     " + tlin + heat + wet + heavy + wet_l1")
fit = smf.ols(F, design(unit_df, K=85, cap=10).loc[:origin - pd.Timedelta(days=1)]).fit(
    cov_type="HAC", cov_kwds={"maxlags": 7})
beta_heat, se_heat = fit.params["heat"], fit.bse["heat"]
```

### Empirical Bayes shrink (leave-one-out, pre-origin)
```python
from statsmodels.stats.meta_analysis import combine_effects

def eb_shrink(b, se, i):
    """b, se: arrays over the group's units (fit on pre-origin data). Returns (shrunk b_i, weight B_i, mu, tau2)."""
    m = np.ones(len(b), bool); m[i] = False
    prior = combine_effects(b[m], se[m]**2, method_re="chi2")    # DerSimonian-Laird; "iterated" = Paule-Mandel
    mu, tau2 = prior.mean_effect_re, prior.tau2
    B = tau2 / (tau2 + se[i]**2)                                 # Bühlmann credibility weight
    return mu + B * (b[i] - mu), B, mu, tau2
```

### Ladder replication at the 24 h ask, with fees
```python
import math

def rep_value(m):                     # integer-°F representative value of a bracket
    t, f, c = m["strike_type"], m.get("floor_strike"), m.get("cap_strike")
    if t == "between": return (f + c) / 2        # inclusive integers f..c
    if t == "greater": return f + 1              # "greater than f" -> T >= f+1
    if t == "less":    return c - 1              # "less than c"    -> T <= c-1  (ins1 used c)
    raise ValueError(m["ticker"])

def kalshi_fee(contracts, price):     # taker fee = round_up(0.07 × C × P × (1−P)) to the cent (Kalshi fee schedule; see Sources)
    return math.ceil(0.07 * contracts * price * (1 - price) * 100) / 100

def ladder_leg(ladder, asks, h, K, cap):
    """ladder: markets of one event; asks: ticker -> 24h yes_ask (None = no offer). Returns (premium, qty by ticker) or None."""
    qty, prem = {}, 0.0
    for m in ladder:
        q = round(h * capped_hinge(rep_value(m), K, cap))
        if q <= 0: continue
        a = asks.get(m["ticker"])
        if a is None: return None                 # unhedgeable at 24h: record, h_t := 0
        qty[m["ticker"]] = q
        prem += q * a + kalshi_fee(q, a)
    return prem, qty
```

### HE with a joint day-block bootstrap
```python
def he(U, Z):                         # U: unexpected revenue; Z: hedge P&L (h*(X - E_clim X) or h*X_lad - premium)
    return 1.0 - np.var(U + Z) / np.var(U)

def block_indices(n, L=7, rng=None):
    rng = rng or np.random.default_rng(20260930)
    starts = rng.integers(0, n - L + 1, size=math.ceil(n / L))
    return np.concatenate([np.arange(s, s + L) for s in starts])[:n]

def median_he_ci(U_mat, Z_mat, draws=2000):   # rows = days (shared), cols = units
    stats = []
    for _ in range(draws):
        ix = block_indices(U_mat.shape[0])
        stats.append(np.median([he(U_mat[ix, j], Z_mat[ix, j]) for j in range(U_mat.shape[1])]))
    return np.percentile(stats, [5, 50, 95])
```

## Pre-registration Draft (seat finalises in plan 05-01 before any Phase 5 number exists)

**Question.** Can a business's weather sensitivity, learned ex ante from its daily sales, prescribe a Kalshi-ladder hedge that reduces out-of-sample revenue variance? Does shrinkage toward a sector prior beat own-history estimates? How many days of history until hedging beats doing nothing?

**1. Data.** Groups G1 NYC-bike (Citi Bike), G2 CHI-bike (Divvy docked), G3 CHI-transit (CTA 'L'), G4 CHI-taxi (community-area Σ fare), G5 NYC-taxi (TLC yellow+green zone Σ fare_amount). Optional G6 NYC-transit (MTA). Weather is the IEM NWS CLI daily high and precipitation at KNYC / KMDW. Kalshi asks come from hourly candles (`/historical/...` before 2026-08-01). Eligibility: unit active on ≥ 98 % of days in [origin − n_max, origin + 365); median ≥ 20/day (bike), ≥ 30 trips/day (taxi) in the estimation window; no detected level break. All eligible units are used and reported by volume tercile. Scale factor, K, priors and climatology all come from pre-origin data only.

**2. Splits.** Primary: origin 2025-01-01, n = 365 (G1–G4); origin 2024-01-01 (G5, congestion-pricing break). Replication: origin 2024-01-01 for G1–G4. Learning curve: origins {2024-07-01, 2025-01-01, 2025-07-01} (G5: {2023-07-01, 2024-01-01}) × n ∈ {30, 60, 90, 120, 180, 270, 365, 545, 730} days immediately before the origin. The hedge window is the 365 days after the origin. Pre-2022-07-01 data is never used.

**3. Estimator.** As in "Recommended Estimator Spec". n ≥ 365: own Fourier(3) + linear trend. 120 ≤ n < 365: group seasonal offset (Fourier(3) coefficients averaged over the group's other units, fit on their pre-origin 365 days) + own level + linear trend. n < 120: group seasonal offset + level, no trend. K_g by group profile SSR over 75–92 °F; cap = 10 °F. HAC(7) SEs.

**4. Arms.** A0 none; A1 own OLS; A2 pooled μ_g (LOO); A3 EB (DL τ², LOO); A4 oracle (bound only).

**5. Hedge.** Heat: `h_t = F_t·(−β_heat)` contracts per bracket weight g(r_b), bought (or sold if h < 0) at the 24 h YES ask (bid), with fees and the no-offer rule. Rain (NYC only at asks): `h^w_t = F_t·(1 − e^{β_wet})` KXRAINNYC YES at the 24 h ask. On days with no KXRAINNYC market listed (the series has gaps), the rain leg is 0 and the day is counted. Chicago rain: policy frame only. Contracts rounded to integers. Primary is uncapped depth; sensitivity caps at 20 contracts per bracket per day.

**6. Metrics.** HE_cover and HE_ladder (Pattern 5), daily and weekly, for the heat-only window (Jun–Sep) and heat+rain (all days). Realised cost per $ of payout. Ladder-transferable share. Unhedgeable-day count. Number of payout days.

**7. Inference.** Moving-block bootstrap over days (L = 7, 2,000 draws, seed 20260930), same indices for all units in a group. The statistic is the median across units. Report 5–95 % intervals.

**8. Tests and thresholds (draft priors; change only before numbers exist):**
- **T1 signal (sanity):** in the primary estimation window, the group priors μ_heat (G1, G2) and μ_wet (G1, G2) are nonzero at 95 %. If this fails, stop: the data or weather join is broken.
- **T2 cover quality (A3, primary split; daily is the test, weekly is reported alongside):** G1 and G2 median HE_cover(heat+rain) ≥ 0.20 with bootstrap LB > 0, and ≥ 70 % of units > 0. Heat-only median HE_cover > 0 with LB > 0. G3–G5 are reported with no threshold.
- **T3 at real asks (A3, G1 NYC heat+rain; G2 heat):** median HE_ladder > 0 with LB > 0, and realised cost over the hedge year (Σ premium + fees − Σ payout) ≤ 25 % of Σ payout.
- **T4 shrinkage (learning curve, pooled over origins):** for n ∈ {60, 90, 120, 180}, A3 − A1 median HE_cover ≥ 0.02 with LB > 0, and A3 has a lower share of units with HE < 0. At n = 365, A3 ≥ A1 − 0.01 (no harm).
- **T5 days of history (descriptive):** n* for A1 and A3 is the smallest grid n from which, for that n and all larger n, the median HE_cover > 0 with LB > 0 and ≥ 60 % of units > 0. If A2 alone passes, report "n* = 0 with a sector prior".
- **P1 placebo:** A3 fit on estimation-window sales with a different year's weather aligned by day of year (2019 weather for a 2024 window; any pre-origin year ≠ window year) gives group μ_heat and μ_wet insignificant at 95 % and a median out-of-sample HE_cover ≤ 0.02. A fail invalidates T2–T5 until explained.

**9. Sensitivities (reported, not tested).** cap 6; levels-model sizing; PPML for count units; binomial thinning to 150/day; decision times 30 h and 12 h; with and without service-suspension days; EB with Paule-Mandel.

**10. Kill / keep.**
- T2 fails for G1 and G2: the portal shows elasticity as advisory only, and the decks cannot say a learned hedge beats nothing.
- T2 passes and T3 fails: daily ladders cannot deliver the cover at asks. The default house-hedge path carries the forecast-level risk; hand the HE_cover − HE_ladder gap to Phase 4 capital.
- T4 fails: the portal uses own-OLS only after n*.
- T4 passes: the portal always shrinks, using priors.json.

**11. Deviations.** Log every change as "Deviation k: what / why / before or after seeing numbers" in reports/eval-06/RESULTS.md.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Monthly/seasonal degree-day regressions on aggregate sales | Daily store-level panels with calendar FE, nonlinear weather, multi-week dynamics | Roth Tran (MS 2023), Badorf & Hoberg (JRCS 2020) | Daily hedge design is defensible; check lags and weekly nets |
| Weather-derivative designs judged in-sample | Out-of-sample / holdout evaluation is expected; in-sample HE overstates | Vedenov & Barnett 2004 onward; recent index-insurance reviews stress holdout | Rolling origins, never in-sample HE in the report |
| Kalshi history limited to recent settled markets | `/historical/*` endpoints serve everything settled before the cutoff (2026-08-01) with hourly candles back to 2021 | verified today | Real asks for 2023–2025 hedge years |
| ins1 bracket mapping (bottom bracket at H(cap)) | Bottom bracket at H(cap − 1) | this research | Small; matters only when K is below the ladder's lowest cap |

**Deprecated/outdated:**
- The ins1 `candles.json` cache format (key `close_dollars`) does not match historical candles (key `close`).
- Old `HIGHNY-` tickers are served under series `KXHIGHNY` in `/historical/markets`; querying series `HIGHNY` returns 0. Verified for NY. For Chicago the `HIGHCHI-` events resolve by `event_ticker`, and series membership under `KXHIGHCHI` is assumed; Phase 1 confirms it.

## Open Questions

1. **Does a CLI trace count as rain for KXRAINNYC ("strictly greater than 0")?**
   - What we know: CLI reports `"T"`; the rule says "> 0 inches".
   - What's unclear: whether a trace settles YES.
   - Recommendation: Phase 2 counts settled results on trace days. Phase 5 pre-registers trace = dry and logs a deviation if Phase 2 shows otherwise.
2. **How far back do usable (two-sided, non-stale) asks go?**
   - What we know: candles exist for 2022–2025. One 2024 hour showed a 3c/20c bid/ask.
   - What's unclear: the share of days per year that pass the no-offer rule at 24 h.
   - Recommendation: report the unhedgeable-day share per year. The GFS MOS fallback fair price + median real overround is a sensitivity only, never the primary.
3. **Kalshi taker fee formula for the relevant years.**
   - What we know: series metadata says `quadratic`, multiplier 1.
   - What's unclear: several independent fee explainers cite `round_up(0.07 × C × P × (1−P))` for takers, and Kalshi's own fee-schedule PDF (July 2026 update) was rate-limited today. Whether the coefficient differed in 2023–2025, or whether weather series carry maker fees, is unverified.
   - Recommendation: Phase 2 pins it from the PDF and applies the same function here. If it can't be pinned, use 0.07 for all years and log it.
4. **How much of HE survives at single-business noise levels?**
   - Recommendation: the thinning sensitivity plus volume terciles. The real answer arrives with POS data (Phase 12).
5. **Climatology source for E_clim[g(T)].**
   - Recommendation: 30 years of station daily highs before the origin, from IEM CLI where archived, else IEM ASOS/COOP daily for the same site. Phase 1 confirms which archive reaches back 30 years for KNYC and KMDW.
6. **Depth history.** Candles carry no depth, so 2024–25 fill sizes are unknown. The 20-contract cap sensitivity uses ins1's 2026 book depth, which is optimistic for earlier years.

## Sources

### Primary (HIGH confidence)
- Kalshi public API (keyless, read-only), queried 2026-09-30: `/series/{KXHIGHNY,KXHIGHCHI,HIGHNY,HIGHCHI,KXRAIN,KXRAINNYC}`, `/markets?series_ticker=…&status=settled`, `/historical/cutoff`, `/historical/markets?series_ticker=…`, `/historical/markets?event_ticker=…`, `/historical/markets/{ticker}/candlesticks`
- IEM: `/json/cli.py?station=KNYC&year=2025`, `/json/cli.py?station=KMDW&year=2025`, `/cgi-bin/request/daily.py`, `/api/1/mos.json?station=KNYC&model=GFS`
- Data hosts: `s3.amazonaws.com/tripdata`, `divvy-tripdata.s3.amazonaws.com`, `d37ci6vzurychx.cloudfront.net/trip-data/`, Socrata `5neh-572f`, `wrvz-psew`, `ajtu-isnz`, `wujg-7c2s`, `5wq4-mkjj`
- Project venv import tests (statsmodels 0.15.0 `combine_effects`, `CalendarFourier`, `MixedLM`, patsy `cr`/`bs`); `prior/hl-mm-ins/reports/ins1/{analyze.py,rows.json,README.md}`; `prior/hl-mm-ins/reports/ins2/README.md`

### Secondary (MEDIUM confidence: abstracts/landing pages verified, full text not read)
- Roth Tran, B. (2023). Sellin' in the Rain: Weather, Climate, and Retail Sales. Management Science 69(12). https://pubsonline.informs.org/doi/abs/10.1287/mnsc.2023.4799 ; WP https://www.frbsf.org/wp-content/uploads/wp2022-02.pdf (WP text read for equations (1), (2) and (8))
- Badorf, F. & Hoberg, K. (2020). The impact of daily weather on retail sales: an empirical study in brick-and-mortar stores. JRCS. https://www.sciencedirect.com/science/article/abs/pii/S0969698919303236
- Štulec, I., Petljak, K. & Naletina, D. (2019). Weather impact on retail sales: How can weather derivatives help with adverse weather deviations? JRCS 49:1–10. https://www.sciencedirect.com/science/article/abs/pii/S0969698918311585
- Bertrand, J.-L., Brusset, X. & Fortin, M. (2015). Assessing and hedging the cost of unseasonal weather: case of the apparel sector. EJOR 244(1):261–276. https://www.sciencedirect.com/science/article/abs/pii/S0377221715000326
- An, R., Zahnow, R., Pojani, D. & Corcoran, J. (2019). Weather and cycling in New York: The case of Citibike. J. Transport Geography 77:97–112. https://www.sciencedirect.com/science/article/abs/pii/S0966692318307282
- Bean, R., Pojani, D. & Corcoran, J. (2021). How does weather affect bikeshare use? A comparative analysis of forty cities across climate zones. J. Transport Geography 95. https://ideas.repec.org/a/eee/jotrge/v95y2021ics0966692321002088.html
- Miranda-Moreno, L. & Nosal, T. (2011). Weather or Not to Cycle. TRR 2247:42–52. https://journals.sagepub.com/doi/10.3141/2247-06
- ASHRAE Guideline 14 / Kissock et al., Inverse Modeling Toolkit (RP-1050): change-point models. https://www.researchgate.net/publication/279717316_Inverse_modeling_toolkit_Numerical_algorithms
- Vedenov, D. & Barnett, B. (2004). Efficiency of weather derivatives as primary crop insurance instruments. JARE 29(3):387–403. https://www.researchgate.net/publication/23942349
- Woodard, J. & Garcia, P. (2008). Basis risk and weather hedging effectiveness. Agricultural Finance Review 68(1):99–117. https://www.emerald.com/afr/article/68/1/99/39795/Basis-risk-and-weather-hedging-effectiveness
- Conradt, S., Finger, R. & Bokusheva, R. (2015). Tailored to the extremes: quantile regression for index-based insurance contract design. https://www.researchgate.net/publication/275898363
- Pérez-González, F. & Yun, H. (2013). Risk Management and Firm Value: Evidence from Weather Derivatives. J. Finance 68(5):2143–2176. https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12061
- Montgomery, A. (1997). Creating micro-marketing pricing strategies using supermarket scanner data. Marketing Science 16(4):315–337. https://pubsonline.informs.org/doi/10.1287/mksc.16.4.315
- Walters, C. (2024). Empirical Bayes Methods in Labor Economics. NBER w33091. https://www.nber.org/papers/w33091
- Hinrichsen, Rehdanz & Tol (2025). Temperature Sensitivity of Residential Energy Demand on the Global Scale: A Bayesian Partial Pooling Model. arXiv 2506.22768. https://arxiv.org/abs/2506.22768
- Efron & Morris (1975), Data analysis using Stein's estimator and its generalizations (JASA); Efron, CASI ch. 7 (James–Stein and ridge): https://efron.ckirby.su.domains/other/CASI_Chap7_Nov2014.pdf
- Kalshi taker fee `round_up(0.07 × C × P × (1−P))`: https://whirligigbear.substack.com/p/makertaker-math-on-kalshi , https://www.allium.so/blog/kalshi-fees-why-the-cost-peaks-near-50-cents/ ; primary schedule (not fetched, 429): https://kalshi.com/docs/kalshi-fee-schedule.pdf
- NYC congestion pricing (CBD toll) started 2025-01-05, $0.75 per TLC taxi trip in the zone: https://www.nyc.gov/assets/tlc/downloads/pdf/industry-notices/industry_notice_24_10_english.pdf , https://en.wikipedia.org/wiki/Congestion_pricing_in_New_York_City

### Tertiary (LOW confidence: training knowledge, not re-verified today)
- Ederington (1979), J. Finance: HE = 1 − var(hedged)/var(unhedged), MV hedge ratio
- Bühlmann (1967) / Bühlmann–Straub (1970) credibility = EB linear shrinkage
- Santos Silva & Tenreyro (2006): PPML for multiplicative models with zeros
- Deschênes & Greenstone (2011): temperature-bin regressions
- NWS climate day in local standard time (consistent with Kalshi's 2026 05:00Z close)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (installed and exercised in the venv)
- Data access and Kalshi history: HIGH (live checks today); depth of usable asks per year: LOW (not measured)
- Regression form: MEDIUM (consensus across retail, cycling and energy literature from abstracts; the exact specs in each paper were not read)
- Shrinkage benefit at 100–365 days: LOW (theory plus analogs; no direct study found; Phase 5 measures it)
- Hedge mapping and evaluation frames: HIGH for the mechanics (verified bracket semantics, listing times, ins1 net-of-premium check); MEDIUM for fee details
- Thresholds: LOW by nature (priors to be frozen before numbers)

**Research date:** 2026-09-30
**Valid until:** 2026-10-30 for methods. Re-check Kalshi endpoints and data lags at plan time (fast-moving: new KXRAIN series, historical cutoff moves monthly).
