# Phase 4: Netting + Pool Economics - Research

**Researched:** 2026-09-30
**Domain:** synthetic business-exposure netting (Census ZBP × sector weather elasticities), uniform-price batch auction simulation, capital sizing for a capped signed weather book, house-MM quoting and markouts, settlement revision policy
**Confidence:** MEDIUM overall. Data paths, auction rules, fee precedents and revision precedents are HIGH (verified against primary sources today). Sector elasticity priors are LOW to MEDIUM (few US daily studies; most rows rest on one study or on industry claims).

## Summary

This phase has to answer two questions with pre-registered rules: how much of the businesses' weather exposure cancels inside the protocol (EVAL-04), and what the pool must hold to carry the rest (EVAL-05). Research covered the prior literature on sector weather sensitivity, the Census files that give a business population by ZIP, the clearing rules of existing batch auctions (Budish–Cramton–Shim, Gnosis Auction, CoW Protocol), capital rules used by insurers and on-chain cover pools, market-maker quoting with inventory risk, and how other weather products handle preliminary vs final data. Several data paths were tested live on 2026-09-30.

The standard approach that falls out: build the population from the **ZBP 2023 detail bulk file** (establishments by 6-digit NAICS × ZIP × size class; the Census API now refuses keyless calls) and **SUSB 2022 receipts per employee** for revenue scale; put ZIPs on the 2024 ZCTA gazetteer points and assign each to its **nearest** settlement station within 40 km (the NYC and EWR discs overlap almost completely). Apply a frozen table of sector elasticities (below), project each business's prior exposure onto the tradable $1/°F capped heat payout to get signed hedge units, and measure netting as matched share of gross units per station-day. Clear one uniform-price call auction per station per day (max volume → min imbalance → nearest the house fair value → midpoint; price priority then pro-rata at the marginal level). The house quotes the residual at actuarial expectation plus cost of capital times its marginal expected-shortfall contribution. Size capital by **revaluing the current book on 1951–2025 weather** (GHCN-Daily station records + nClimGrid-Daily county averages), not on the 68–1,600 Kalshi-era days, which are used for prices, costs and an out-of-sample capital backtest. Settle on a pinned file vintage at T+N and ignore later revisions, as Kalshi does.

Two findings should change how the numbers are framed. First, the best US daily evidence says most sectors move the **same** way with temperature (Deryugina 2021, ~20 billion SafeGraph visits: "remarkably little heterogeneity" across establishment types; warm-day effects vanish within 7 days) and that many weather effects are timing shifts (Starr-McCluer 2000; Addoum, Ng and Ortiz-Bobea 2020 find no temperature effect on establishment sales). Opposite-sign pairs exist (ice cream, liquor, delivery, HVAC vs outdoor recreation, apparel, landscaping), but netting may be much smaller than the pitch implies, so the pre-registration reports netting under a prior ensemble **and** a "shrink-to-common" null. Second, aggregate hedge demand will dwarf Kalshi depth (ins1: 5–20 $1/°F units per city-day within 3c), so internalizing the station leg and carrying capital is the business, not a side detail (rough arithmetic: ~10k small full-service restaurants near Central Park and EWR × 2 % × ~3 units ≈ several hundred units before any other sector). Kalshi taker fees (0.07·P·(1−P) per contract) were not in the ins1 cost numbers and must be added.

**Primary recommendation:** Freeze the elasticity table and pre-registration in 04-01; compute netting on signed units per station-day under central priors, a 1,000-draw prior ensemble and the shrink-to-common null; size capital as min(full collateral, max(ES99 of the H-day pool loss from joint-date block bootstrap on detrended 1951–2020 history, worst historical H-day window)), backtest it on the Kalshi-era days, and report the gap between that number and full collateralization as the leverage the pool would need.

### Baselines carried in (read-only, from hl-mm ins1/ins2)

| item | NYC | CHI (MDW) | MIA | EWR / TTN | source |
|---|---|---|---|---|---|
| sell-side markout, post at 24 h ask, hold to settlement, per $1/°F unit-day (≈19.5 contracts) | +$0.293 (+1.5c/contract) | +$0.210 (+1.1c) | +$0.001 (0c) | +$6.3 / +$6.4 (fills at 2.4–2.7× overround asks: not a usable baseline) | ins1 results.txt V1 |
| worst day / p10 / win rate | −2.575 / −1.340 / 71 % | −3.920 / −1.330 / 56 % | −1.905 / −1.305 / 43 % | −0.69 / −1.54 worst | ins1 V1 (68 days; 34 for EWR/TTN) |
| worst day ÷ mean day | ~9× | ~19× | n/a (mean ≈ 0) | | ins1 README |
| overround at 24 h | 17 % | 7 % | 0 % | 241 % / 266 % | ins1 T1 |
| spread cost per unit at 24 h | 0.12 | 0.12 | 0.14 | 3.69 / 3.75 | ins1 T1 |
| depth within 3c of best ask | 80–450 contracts per rung ≈ 5–20 units → ~$30–120 max payout per city-day | | | | ins1 README |
| residual common-mode correlation around one station | 0.77 | 0.80 | 0.76 | 0.83 / 0.74 | ins2 (cell−station residuals) |

Implication: a sell-side book earns roughly the overround on liquid ladders with a left tail 9–19× the mean day; ins1 already showed a 100-unit book breaching a $150 window cap. Capital, not expected P&L, is the binding constraint.

## Standard Stack

### Core data (all free, keyless, verified reachable 2026-09-30)
| Source | Version / file | Purpose | Why standard |
|---|---|---|---|
| Census ZIP Code Business Patterns detail | `https://www2.census.gov/programs-surveys/cbp/datasets/2023/zbp23detail.zip` (15.7 MB zip, 291 MB txt, 2,974,116 rows, NAICS **2017** codes) | establishments by ZIP × 6-digit NAICS × 9 employment-size classes | the only public NAICS × ZIP establishment count; CBP 2023 is the latest (files dated 2025-06-26; `datasets/2024/` returns 404) |
| ZBP totals | `.../2023/zbp23totals.zip` | ZIP employment + payroll (all industries) | calibration of size-class midpoints |
| CBP county | `.../2023/cbp23co.zip` (12.9 MB) | county EMP and payroll by NAICS | cross-check establishment-size midpoints per county |
| SUSB 2022 | `https://www2.census.gov/programs-surveys/susb/tables/2022/us_state_6digitnaics_2022.txt` (56 MB) | receipts (RCPT, $1,000), employment, establishments by state × 6-digit NAICS (2017 codes) × enterprise size | receipts per employee → revenue scale per establishment; census-year receipts |
| 2024 ZCTA gazetteer | `https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip` | ZCTA internal point (INTPTLAT/INTPTLONG) | official centroid-like point per ZIP area |
| GHCN-Daily station CSV | `https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{ID}.csv` | long daily TMAX/PRCP for capital scenarios | NCEI archive of the same ASOS stations Kalshi settles on |
| nClimGrid-Daily area averages | `https://www.ncei.noaa.gov/data/nclimgrid-daily/access/averages/{YYYY}/tmax-YYYYMM-cty-scaled.csv` (also `prcp`, `tmin`; `div`, `wfo`, `ste` levels; 1951–2026, ~1 MB per file) | county / climate-division daily means = a regional-factor history for the residual | avoids pulling 50 GB of 1/24° grids to get 75 years of metro means |
| NCEI USDA 1/4° daily precipitation | `https://www.ncei.noaa.gov/pub/data/cirs/usda/daily/{initial-unsynced,initial-synced,final}/` | rain revision vintages (see Pattern 7) | derived from nClimGrid-Daily; keeps a rolling 40-day archive of first-publication files |
| IEM NWS text archive + CLI JSON | `https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=CLINYC...`, `https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2026` | every issuance of the NWS Daily Climate Report (CLI), incl. corrections | station-level revision measurement |
| Kalshi keyless API | `/trade-api/v2/series/{T}`, `/markets?series_ticker=...` | settlement rules, fee type, candles (Phase 1) | primary source for the hedge leg |

Station IDs and record starts (GHCN-D inventory, checked today): Central Park USW00094728 TMAX 1869–; EWR USW00014734 1843–; TTN USW00014792 1945–; **Midway USW00014819 only 1997–**; MIA USW00012839 1948–; ORD USW00094846 1958–; LGA 1939–; JFK 1948–; FLL 1945–; OPF 1998–.

### Core libraries (already in `pyproject.toml` / `.venv`)
| Library | Version (installed) | Purpose |
|---|---|---|
| numpy | 2.5.3 | vectorised haversine, clearing grid, scenario matrices |
| pandas | 3.0.6 | ZBP/SUSB joins, panels |
| scipy | 1.18.1 | binomial tail for the Kupiec backtest, distributions for the prior ensemble |
| statsmodels | 0.15.0 | detrending regressions if needed |
| duckdb | 1.5.6 | fast filter of the 291 MB ZBP text without loading it all |

### Supporting
| Library | Version | Purpose | When to use |
|---|---|---|---|
| arch | 8.0.0 (PyPI, Python ≥3.10) | `arch.bootstrap.optimal_block_length`, `CircularBlockBootstrap`, `StationaryBootstrap` | block length choice and CIs on Kalshi-era markout series; add with `uv add arch` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|---|---|---|
| ZBP bulk file | Census API `cbp` dataset (has `zip code` geography, `NAICS2017`, `EMPSZES`) | API now 302-redirects to `missing_key.html` without a key (tested 2026-09-30); agents may not create keys |
| SUSB receipts/employee | Economic Census 2022 receipts per establishment | EC tables are richer but reached through the keyed API or manual data.census.gov exports; SUSB is one flat file |
| nClimGrid-Daily county averages | full 1/24° monthly grids 1951– | ~900 files × ~57 MB; only needed if Phase 3 keeps a per-cell design |
| nearest-station assignment | ZIP→ZCTA crosswalk (HUD) | HUD API needs a token; ZIPs without a ZCTA hold 0–2.3 % of establishments in seven core counties checked (Manhattan 2.3 %, Mercer 1.1 %, others ≤ 0.4 %) — drop and report |

**Installation:**
```bash
cd ~/weather-insurance && uv add arch
```

## Sector Elasticity Priors (freeze in 04-01 before any netting number)

**Units.** `e_T` = % change in same-day revenue per °F of daily station Tmax above the sector threshold `T0` (warm season, May–Sep). `e_R` = % change in same-day revenue on a wet day (≥ 0.10 in / 2.5 mm) vs a dry day, same season. Each range is the min and max of a triangular distribution (mode = central) that the ensemble samples: a plausible span, not a confidence interval. "Persistence" says whether the lost/gained sales come back within ~3 weeks (low persistence = timing shift = weaker real hedging need). Sign convention: `e_T > 0` = long heat (earns more when hot) → hedges by selling heat cover / buying cool cover.

| NAICS 2017 (ZBP code) | group | e_T central (range) | T0 °F | e_R central (range) | persistence | confidence | basis |
|---|---|---|---|---|---|---|---|
| 722515 | snack & nonalcoholic beverage bars (ice cream, frozen yogurt, coffee, juice) — code mixes coffee shops, so muted | +0.5 (0 to +1.5) | 70 | −8 (−20 to −2) | high (perishable) | LOW | Agnew & Thornes 1995 (ice cream up, qualitative); Planalytics: c-store cold categories rise above 65 °F daily mean |
| demo ice-cream shop (single business, not a ZBP row) | ice cream parlour | +2.0 (+0.8 to +4.0) | 70 | −15 (−30 to −5) | high | LOW | same; no peer-reviewed US daily elasticity found |
| 445310 | beer, wine & liquor stores | +0.6 (+0.3 to +1.0) | 60 | −2 (−5 to 0) | medium | MEDIUM (T) / LOW (R) | Hirche, Haensch & Lockshin 2021: +10.2 % weekly beer volume per +10 °C, 37,346 US stores, 2013–15 (≈ +0.57 %/°F) |
| 445120, 447110 | convenience stores, gas stations with stores | +0.3 (0 to +0.8) | 75 | −3 (−8 to 0) | medium | LOW | Planalytics (c-store categories: sports drinks, fountain, beer, ice) |
| 722511 | full-service restaurants | −0.2 (−0.6 to +0.3) | 85 | −4 (−10 to −1) | high (seat capacity lost) | LOW | Bujisic, Bogicevic & Parsa 2017 (non-linear temperature, item mix); outdoor-seating logic; Deryugina 2021 null |
| 722513 | limited-service restaurants | 0 (−0.3 to +0.3) | 85 | −2 (−6 to +2) | high | LOW | as above; drive-thru and delivery offset |
| 722410 | drinking places | +0.2 (−0.3 to +0.6) | 80 | −5 (−12 to −1) | high | LOW | patio logic; no quantitative US source found |
| 448110–448190, 448210, 451110 | clothing, shoes, sporting goods | −0.3 (−0.5 to −0.1) | 88 | −3 (−7.4 to +5.2) | low–medium (negative shocks persist) | MEDIUM | Roth Tran 2023 (Mgmt Sci; 100+ US stores of one apparel/sporting brand, daily 2010–13): TAVG ≥ 80 °F −2.0 %, ≥ 90 °F −4.3 %, precip −1.9 %/in, PRCP ≥ 1 in −3.9 %, 1-sd bad-weather shock loses ~10 % of a day's sales net after 3 weeks; Martínez-de-Albéniz & Belkaid 2021: rain −7.4 % street stores, +5.2 % mall stores |
| 444110, 444130, 444220 | home centers, hardware, nursery/garden | −0.2 (−0.5 to +0.2) | 90 | −5 (−10 to −2) | medium | LOW | Viscacha Data (commercial blog) on Home Depot: rain days −4.8 % sales; Lowe's CEO: weather "the biggest driver" (seasonal) |
| 445110 | grocery (supermarkets) | 0 (−0.1 to +0.1) | — | −1 (−3 to +1) | low (substitution) | LOW | Penn State "Weather sensitivity analysis on grocery shopping": rain cuts trips, raises basket |
| 492210 | local messengers & delivery | +0.3 (0 to +1.0) | 90 | +10 (+3 to +25) | high | LOW | Chinese platform studies (extreme weather +40–60 % delivery demand); US anecdotes (Grubhub storm spikes) |
| 713110, 713910, 713930, 713990, 712130 | outdoor recreation (amusement parks, golf, marinas, other rec, zoos) | −0.8 (−2.0 to −0.3) | 82 | −30 (−50 to −10) | medium (visits partly rescheduled) | LOW–MEDIUM | Aylen, Albertson & Cavan 2014 (Chester Zoo, UK, daily; Climatic Change 127:183–197): visits rise with temperature to a threshold near 21 °C and drop on hotter days; even light rain (0–2 mm) lowers visits, and some visits are redistributed to later days. Toronto Zoo work (Hewer & Gough) puts the hot-day decline above ~26–28 °C. The −30 % rain prior is a judgment, not a published estimate |
| 713940 | fitness & recreational sports centers (indoor) | 0 (−0.2 to +0.2) | — | 0 (−3 to +3) | — | LOW | no source; indoor |
| 512131 | motion picture theaters | +0.3 (0 to +0.8) | 88 | +5 (0 to +12) | medium | LOW | trade-press claim +12 % theater visits on rainy days; Chinese cinema study: extreme heat −3.4 % audiences (sign conflict) |
| 811192 | car washes | −0.1 (−0.5 to +0.3) | — | −40 (−70 to −20) | low (washes deferred) | LOW | no source found (expert prior) |
| 238220 | plumbing / HVAC contractors | +1.0 (+0.3 to +2.5) | 88 | 0 (−5 to +5) | high (repair calls) | LOW | no source found (expert prior) |
| 561730 | landscaping services | −0.2 (−0.6 to 0) | 92 | −20 (−40 to −5) | low (crew days rescheduled) | LOW | no source found (expert prior) |

**Cross-sector evidence the table must respect (not rows, but constraints):**
- Deryugina (2021, SafeGraph, ~20 bn visits, ZIP-day, Jan 2017–Jul 2019): days above 30 °C raise same-day visits ~4 % vs 0–3 °C; the effect is gone within 7 days; "remarkably little heterogeneity in the temperature-demand relationship across different types of establishment" (medical the exception). → justifies the **shrink-to-common null**: `e_null = 0.75·c + 0.25·e_central`, `c` = revenue-weighted mean of central `e_T`.
- Addoum, Ng & Ortiz-Bobea (2020, RFS; establishment data 1990–2015): no significant temperature effect on establishment sales or productivity, "including among industries traditionally classified as heat sensitive" → daily effects largely wash out over quarters.
- Starr-McCluer (2000, FEDS 2000-08; monthly): weather effects modest, often offset by lags, "tend to wash out at a quarterly frequency"; deferrable goods (furniture, apparel) hit hardest.
- Lazo, Lawson, Larsen & Waldman (2011, BAMS 92:709–720; state GSP by sector, 24 years): weather variability ≈ 3.4 % of 2008 US GDP ($485 bn); retail and wholesale trade ~2 %, services ~3 %, mining 14 %, agriculture 12 %. Annual and state-level: a sanity cap on annual aggregates, **not** a daily elasticity. (The brief names Morss as fourth author; the BAMS listing found in two sources is Lazo, Lawson, Larsen & Waldman.)
- Roth Tran (2023): sensitivity to rain, snow and cold falls with local experience (e.g. the drop from ≥ 2 in precipitation is ~80 % smaller in stores with above-median experience); **no adaptation to extreme heat**. Miami's heat priors should not be shrunk for "they are used to it".

**How the table is used.** (1) Central run. (2) Ensemble: 1,000 draws, sectors independent, triangular(low, central, high), seed 20260930, draws held fixed across days. (3) Shrink-to-common null. (4) Rain priors only if Phase 2 finds a tradable rain ladder (KXRAINNYC daily binary 2021-09→2026-07 exists; KXRAINNYCM monthly); otherwise rain netting is reported descriptively.

## Architecture Patterns

### Recommended Project Structure
```
src/wi/
├── population/          # ZBP + SUSB + gazetteer → business table (zip, naics, size class, est, daily_rev, station, dist_km)
│   ├── zbp.py           # load + "N" imputation + small-business filter
│   ├── revenue.py       # SUSB receipts/employee × size-class midpoints
│   └── stations.py      # nearest-station assignment (haversine, 40 km cap)
├── exposure/
│   ├── priors.py        # frozen prior table (loaded from priors_2026-09-30.csv, git-hashed in the prereg)
│   └── hedge.py         # project prior exposure onto the tradable payoff → signed units per business
├── auction/
│   └── clear.py         # ONE uniform-price clearing function, shared with Phase 7 engine (see Open Q1)
├── pool/
│   ├── scenarios.py     # current book revalued on 1951–2025 joint weather (station + county-average residual)
│   ├── capital.py       # ES99, worst window, full collateral, tranche split
│   ├── quote.py         # house quote = fair + CoC × marginal ES + fee
│   └── markout.py       # fill-level and daily markout series
└── oracle/
    └── revision.py      # vintage snapshots + revision share (station CLI, USDA 1/4° rain, nClimGrid prelim)
reports/eval-04-05/      # tables, figures, results.json, PREREG.md copy, deviations log
data/raw/{census,ghcnd,nclimgrid_avg,usda_vintages}/   # manifested like Phase 1
```

### Pattern 1: Population → exposure map
**What:** One row per (ZIP, NAICS6, size class) with establishment count, daily revenue per establishment, nearest station and distance.
**When to use:** 04-01, once; the table is an input artifact with a row count and md5 in the manifest.
**Steps:**
1. Filter ZBP detail to the NAICS codes in the prior table (duckdb over the unzipped text).
2. Size classes: the nine columns `n<5 … n1000`; `"N"` marks suppressed cells (observed pattern: cells with 1–2 establishments). Impute `gap = est − Σ reported` and spread it over the N cells (cap 2 per cell, remainder to the smallest N class).
3. Keep small businesses: classes 1–4, 5–9, 10–19, 20–49 employees (midpoints 2.5, 7, 14.5, 34.5). Report the share of estabs and revenue dropped.
4. Revenue: ZBP detail has establishment counts only (no employment, payroll or receipts by NAICS), so `daily_rev = RCPT/EMPL (SUSB 2022, state × NAICS6, ENTRSIZE 01 total) × midpoint / 365`. SUSB also publishes `us_6digitnaics_rcptsize_2022.xlsx` (national establishments by receipts-size class per NAICS6) to sanity-check the implied revenue distribution. National examples from the file: full-service restaurants $73k receipts/employee ($1.48M/establishment), snack & beverage bars $73k, liquor stores $371k, family clothing $177k, hardware $249k, car washes $90k, HVAC/plumbing $260k.
5. Station: ZCTA internal point → nearest of the five settlement stations; drop if > 40 km. **Nearest only** — a 40 km disc test counts NYC-area businesses twice (405k establishments within 40 km of Central Park, 379k within 40 km of EWR).
6. Descriptive check already run (all industries, 40 km, before nearest assignment): NYC 405,115; EWR 378,815; TTN 70,181; MDW 168,855; MIA 128,643 establishments. Full-service restaurants within 40 km: NYC 14,865; MDW 5,101; MIA 3,270; TTN 1,883.

### Pattern 2: Prior exposure → signed hedge units
**What:** A business's revenue exposure under the prior is `daily_rev × e_T × max(T − T0, 0)`; the tradable payoff is the ins1 heat cover `H(T) = min(max(T − K, 0), 6)` with `K` = the ladder's second-bracket floor. Because `T0 ≠ K`, regress the prior exposure on `H` over the station's warm-season history to get min-variance units `h_i` (negative of the slope). Sign of `h_i` = side.
**Why:** keeps every business on the same instrument, so netting within a station is exact unit arithmetic; the leftover basis `exposure − h_i·H` is reported, not hidden.
**Complementary covers (important for design and for collateral):** with a cap `c = 6`, a cool cover `C(T) = c − H(T)`. A short-heat business buys `H`, a long-heat business buys `C`; the pool's combined liability is the constant `c` per matched pair, fully funded by the two premiums (`p_H + p_C = c` at no-arbitrage). This is Kalshi's YES/NO structure. So "buy C at `c − p`" ≡ "sell H at `p` with collateral `c − p`"; the auction can clear one contract (`H`) and let the UI present the long-heat side as buying cool cover.

### Pattern 3: One uniform-price call auction per station per day
**What:** Sealed orders `(side, qty, limit)` for the station's contract for day D, collected until the cutoff (default T−24 h, variant T−2 h), cleared once, published: price, volume, aggregate demand and supply curves; each order owner gets a private fill message (BCS 2014 reporting). Unfilled orders expire (daily contract; no carry-over).
**Price rule (lexicographic):**
1. maximise executed volume `min(D(p), S(p))` over the tick grid `p ∈ {0, 0.01, …, X_max}`;
2. then minimise imbalance `|D(p) − S(p)|`;
3. then the grid price nearest the reference price (house fair mid `μ`) — equity closing-cross practice;
4. then the midpoint of the remaining interval (BCS "vertical intersection" case); lower tick on an exact tie.
**Allocation:** the short side fills fully; the long side fills by price priority (best limits first) and **pro-rata within the marginal price level** (BCS: pro-rata, no time priority inside a batch). Gnosis Auction instead breaks ties by (price, amount, userId) — deterministic but it favours whoever sorts first; pro-rata is fairer to many small businesses.
**Reserve price:** the house MM's quotes act as the reserve: it posts a sell schedule above `μ` and a buy schedule below `μ` sized by its capital limit, so the clearing price is bounded by the house's inner quotes whenever it has capacity. Also: a minimum order size (Gnosis `minimumBiddingAmountPerOrder` analogue) and a hard band `[0, X_max]`.
**Who gets the spread:** with a buy imbalance, `p*` lands on the house ask; the matched minority sellers (long-heat businesses) receive the house ask, i.e. better than fair. The house earns `p* − μ` only on the imbalance it absorbs. Report this transfer explicitly.
**Fees (sweep, pick in Phase 7):** (a) protocol fee in bps of notional (qty × X_max) on every hedger fill: 0 / 10 / 25 / 50 bps; (b) CoW-style share of price improvement vs the order's limit (50 %, capped); (c) no protocol fee, house spread only. Precedents: CoW Protocol 2 bps volume fee on standard assets (0.3 bps correlated) plus 50 % of surplus / quote improvement capped at 0.98 % of volume; Gnosis Auction fee ≤ 1.5 % of the auctioned amount (`feeNumerator ≤ 15`, denominator 1000).
**Station leg vs residual:** run the same auction for (i) the station contract (internalization before Kalshi) and (ii) the residual contract (one regional residual per station, pending Phase 3). Internalized station units save the Kalshi ask-minus-fair plus Kalshi fees; that saving is a first-class output.

### Pattern 4: Capital by revaluing today's book on long weather history
**What:** The pool's P&L for any day is a deterministic function of weather at the five stations (and the residual index) given positions and prices. So revalue the **current** book on every historical warm-season day 1951–2025, with all stations taken from the **same calendar date** (keeps common shocks: NYC/EWR/TTN heat waves are one event).
**Scenario sets:** (a) historical overlapping H-day windows per year (≈ 75 years × ~150 start days); (b) joint-date block bootstrap: blocks of `b` consecutive days (default 7, check with `optimal_block_length`) drawn from random (year, start) inside the same seasonal window, concatenated to H days, 10,000 paths, seed 20260930.
**Detrending:** shift each station-year's warm-season Tmax by the linear trend in the seasonal mean, fitted on 1951–2020 only for the backtest (1951–2025 for the deployable number). Standard weather-derivative burn-analysis practice.
**Capital rule (prototype):**
`C_H = min( FC , max( ES99(bootstrap H-day loss) , max(historical H-day window loss) ) )`
where `FC` = full collateral: Σ over the pool's open positions of the worst-case loss (qty × X_max − premium received for cover the pool sold; premium paid for cover it bought) and `H` = the recapitalisation horizon: the number of days the pool must survive a rolled daily book with no new capital and no re-pricing (default 30; for policies priced at inception use max(30, tenor)). Report H ∈ {1, 5, 30}.

**Capital precedents and why the hybrid:**

| regime | rule | fit for this pool |
|---|---|---|
| Solvency II | VaR 99.5 % of own funds over one year (Directive 2009/138/EC Art. 101) | wrong horizon for daily contracts; VaR ignores tail size |
| Swiss Solvency Test | expected shortfall 99 % over one year (training knowledge) | ES is the right tail measure; horizon replaced by H |
| Lloyd's | 1-in-200 SCR plus a 35 % uplift for member capital (training knowledge) | shows capital regimes load model output for model error |
| Nexus Mutual | MCR = active cover / 4.8 (≈ 20.8 % of cover), full model off-chain | the on-chain comparator for "capital per $ of cover" (M5 threshold) |
| ILS / cat bonds, Kalshi sellers | fully collateralised to the limit (Kalshi seller locks 1 − p) | the safe on-chain default and the upper bound `FC` |
| stress-day rule | capital = loss on the worst named or historical day/window | transparent, but one number from one event; used here as the floor |

The hybrid takes ES99 as the model number, floors it with the worst historical window (a model-error guard, in the spirit of the Lloyd's uplift), and caps it at full collateral. With 68–1,600 Kalshi-era days the sample for weather tails is too small, so the tail comes from 75 years of weather; the Kalshi-era days size costs and test the rule (M6).

**Tranches:** junior (token) = first loss up to ES95 of the H-day loss (the mean of the worst 1-in-20 outcomes); senior (stablecoin) = `C_H − junior`. Report P(loss > junior), P(loss > C_H) under both scenario sets.
**Chicago:** Midway's GHCN-D record starts 1997. Use ORD (1958–) plus the MDW−ORD offset (ins1: mean Tmax difference 0.00 °F, raw HE 0.64) for pre-1997 scenarios and flag Chicago's capital as lower confidence.

### Pattern 5: House quote = actuarial expectation + capital charge
`ask = μ + λ·ΔES_sell + fee`, `bid = μ − λ·ΔES_buy − fee`, clipped to `[0, X_max]`, with
- `μ = E[X | info at cutoff]`: station leg from the Kalshi mid at the cutoff (candle close at T−24 h); residual from month-conditional climatology of the regional factor through year D−1;
- `ΔES` = Euler (co-ES) marginal contribution of one unit to the book's ES99, read straight off the scenario matrix (mean loss of that unit in the book's worst 1 % scenarios); negative when the trade reduces risk, which skews quotes toward inventory-reducing flow (the Avellaneda–Stoikov / Guéant idea, done with a scenario matrix instead of a closed form);
- `λ = CoC / 365` per unit-day, CoC swept at 6 % (Solvency II risk-margin rate), 15 % and 30 % (junior-token hurdle). The pool holds `C_H` continuously for a rolling book, so the yearly cost is `CoC × C_H`; each unit-day is charged its marginal share of that, with `ΔES` taken from the **H-day rolling-book** scenario matrix (a unit-day enters one day of the H-day window). With `H = 1` the charge would be near zero and wrong: a heat wave is five losing days in a row for a rolled book.
The house also paper-hedges its net station inventory on Kalshi at the recorded ask at the cutoff (Phase 2 method), subject to depth (ins1: ~5–20 units within 3c) and Kalshi's $25,000 position-accountability level per strike per member.

### Pattern 6: Markout series (what to report)
Per house fill: `mo_settle = side × (payout − price) × qty` (side +1 = house bought X). Also `mo_2h = side × (μ_2h − price) × qty` (fair at T−2 h: adverse-selection proxy) and `mo_hedged` (fill plus its Kalshi hedge at asks, fees included). Aggregate to daily per station and pooled; report mean (c/contract and $/unit-day), median, p10, p1, worst day, worst 5-day and 30-day, win rate, max drawdown vs `C_H`, share of total P&L from the 5 worst days, and the cross-station correlation matrix of daily markouts. CIs by moving-block bootstrap (block 7 days, 2,000 draws). Compare with the ins1 V1 baseline table above.

### Pattern 7: Revision policy (stated rule + measurement)
**Rule for Phase 7 (draft):** every contract names one settlement source and a settlement time `T+N` (UTC). The oracle reads the source as published at `T+N`, stores URL, retrieval time, file version string and SHA-256, and settles on that value. Revisions after `T+N` are ignored. If the value is missing at `T+N`, retry daily to `T+N_max`, then the named fallback source, then void with premiums refunded (a smart contract has no "last fair price" judgment).

| source | N | N_max | why |
|---|---|---|---|
| NWS Daily Climate Report (CLI) for the station | 1 day (e.g. 14:00Z on D+1) | 7 days | mirrors Kalshi: first non-preliminary report, expiry at the first 7–8 AM ET after release, 1-week cap |
| NCEI USDA 1/4° daily precip, `initial-unsynced` | 5 days | 10 days | 3-day processing delay; each daily tarball holds the 5 most recent days |
| nClimGrid-Daily prelim (1/24° or county average) | 3–5 days | 10 days | the prelim monthly file is overwritten in place, so the oracle must snapshot and hash it on the day |

**Measurement (04-03):** revision share = fraction of settlement units whose payout moves by ≥ $0.50 per $1/°F unit (temperature) or whose wet-day flag flips (rain) between the `T+N` vintage and the latest vintage available. Sources: (i) station — all CLI issuances in the IEM AFOS archive (corrections are separate products) and the CLI value vs the later GHCN-D value; (ii) rain — the 39 `initial-unsynced` tarballs on the server now (2026-08-21 → 2026-09-28) vs `initial-synced` (Aug, posted 2026-09-09) and `final` (Jul, posted 2026-09-05); (iii) temperature grid — start a daily snapshot job of the nClimGrid prelim file now; Sep prelim (created 09-28) vs Sep scaled (expected ~2026-10-06).

### Anti-Patterns to Avoid
- **Capital from Kalshi-era P&L alone:** 68 days (or even ~1,600) do not contain a 1-in-100 heat wave for every station; use them for prices, costs and the backtest only.
- **Bootstrapping stations independently:** destroys the NYC/EWR/TTN common shock and understates capital. Always resample dates jointly.
- **Counting overlapping windows as independent:** 75 years give ~75 independent warm seasons, not 11,000 windows. Say so next to every tail number.
- **Assigning a ZIP to every station within 40 km:** double-counts the NYC–EWR overlap.
- **Tuning priors after seeing netting:** the table is frozen with a git hash in 04-01; changes go to the deviations log with the before/after numbers.
- **"Last fair price" fallbacks:** fine for Kalshi, impossible to audit on-chain; void and refund instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Business counts by ZIP and industry | scraped business listings, Yelp, OSM | ZBP 2023 detail bulk file | official, complete for employer establishments, keyless |
| Revenue per establishment | invented revenue tables | SUSB 2022 receipts per employee × size-class midpoint | census-year receipts by state × NAICS6 |
| ZIP location | geocoding APIs | 2024 ZCTA gazetteer internal points | free, no rate limits, reproducible |
| Long station weather | stitching IEM pulls back to 1951 | GHCN-Daily per-station CSV | same stations, QC flags, one file each |
| Metro-mean residual history | averaging 1/24° grids yourself | nClimGrid-Daily area averages (county / climate division / WFO) | NCEI computes them from the same grid; 1951–present, ~1 MB/month |
| Block length choice | eyeballing | `arch.bootstrap.optimal_block_length` | standard (Politis–White) |
| Clearing algorithm, twice | a separate simulator auction and engine auction | one `clear()` in `wi.auction`, used by Phase 4 and Phase 7 (Phase 8 ports it) | tie and rounding rules are where the bugs are; two copies drift |
| Rain revision vintages | a scraper that waits months | NCEI USDA `initial-unsynced` archive (rolling 40 days of first-publication files) | vintages already exist for the last 40 days |
| Weather generator for tails | stochastic weather model | historical revaluation + joint-date block bootstrap | a generator adds model risk the prototype cannot validate |

**Key insight:** every hard number in this phase (establishments, receipts, 75 years of weather, vintages) already exists as a free flat file. The custom code is small: imputation, projection onto the payoff, one clearing function, one scenario matrix. Spend the effort on the pre-registration and on tie/rounding rules, not on data plumbing.

## Common Pitfalls

### Pitfall 1: Census API calls fail silently
**What goes wrong:** `api.census.gov/data/2023/cbp?...` returns HTTP 302 to `missing_key.html` (header `X-DataWebAPI-KeyError: 1`), which `requests` follows to an HTML page.
**How to avoid:** use the bulk files; if anything touches the API, assert JSON content type.
**Warning signs:** HTML where JSON was expected; empty frames.

### Pitfall 2: Treating ZBP "N" as zero
**What goes wrong:** establishment counts in suppressed size cells vanish; small-business totals come out low.
**How to avoid:** impute from `est − Σ reported` (Pattern 1). Log totals before/after.

### Pitfall 3: NAICS vintage mismatch
**What goes wrong:** ZBP 2023 and SUSB 2022 both use NAICS **2017** (e.g. family clothing 448140; the 2022 code 458110 does not appear in SUSB 2022). A prior table keyed on 2022 codes silently drops apparel.
**How to avoid:** key the prior table on 2017 codes; assert every prior row matches ≥ 1 ZBP row.

### Pitfall 4: Double counting overlapping station discs
See Pattern 1 step 5. **Warning sign:** station totals summing to more than the metro.

### Pitfall 5: NCEI area-average codes are not FIPS
**What goes wrong:** nClimGrid-Daily county files use NCEI's own state numbering (observed: `08086 FL: Miami-Dade`, `11031 IL: Cook`), so a FIPS join (FL = 12, IL = 17) picks the wrong county.
**How to avoid:** join on the name column or build an explicit crosswalk for the handful of counties used.

### Pitfall 6: Day conventions
**What goes wrong:** nClimGrid-Daily label D = calendar day D+1 relative to ASOS calendar-day max (ins2 nearest cell vs ASOS: RMSE 2.3–5.2 °F unaligned vs 1.1–1.7 °F aligned); the area averages come from the same grids, so assume the same until checked. NWS climate data run midnight to midnight local standard time (CME's degree-day rules define the day as 0000–2359 LST), so during daylight time the CLI day is 1 am–1 am local clock time; Kalshi uses the CLI day.
**How to avoid:** reproduce the ins2 alignment check on the county averages before using them; store every series with its day definition.

### Pitfall 7: Kalshi fees missing from hedge costs
**What goes wrong:** ins1 premiums are at asks without fees. KXHIGH* series report `fee_type: quadratic`, `fee_multiplier: 1`; Kalshi's docs work an example where a $0.055 buy carries a model fee of $0.00363825 = 0.07 × 0.055 × 0.945, i.e. **fee = 0.07·P·(1−P) per contract** (max 1.75c at P = 0.5). Because P(1−P) ≤ P, the fee on a replicating ladder is at most 7 % of its premium: ≤ $0.12 / $0.22 / $0.34 per $1/°F unit-day at the ins1 24 h premiums (NYC 1.73, CHI 3.14, MIA 4.79), the same order as the 0.12–0.14 spread cost. Non-direct members also pay cent rounding per order.
**How to avoid:** add the fee per rung in every hedge-cost and markout calculation; check the series' `fee_type` at run time (some series use `quadratic_with_maker_fees`).

### Pitfall 8: Hedge demand larger than the hedge venue
**What goes wrong:** the simulation assumes the house can lay off its net station exposure on Kalshi. ins1 depth is ~5–20 units per city-day within 3c; Kalshi's position accountability level is $25,000 per strike per member.
**How to avoid:** cap Kalshi hedges at recorded depth (Phase 2/recorder books) and carry the excess in the pool; report the unhedged share.

### Pitfall 9: Over-stating hedging need with daily elasticities
**What goes wrong:** if a hot day's lost sales come back within a week (Deryugina: warm effects gone in 7 days; Starr-McCluer: wash out quarterly), a daily hedge over-insures and real demand is smaller.
**How to avoid:** carry the persistence column into the participation model (perishable, capacity-bound sectors more likely to hedge); report netting with and without that weighting.

### Pitfall 10: Climate trend in burn analysis
**What goes wrong:** undetrended 1951–2025 history under-prices heat and under-sizes capital.
**How to avoid:** detrend (Pattern 4); show capital with and without detrending.

### Pitfall 11: Midway history is short
GHCN-D USW00014819 TMAX starts 1997. See Pattern 4.

### Pitfall 12: Look-ahead through the fair value
**What goes wrong:** using the settlement-time candle, or climatology that includes day D, as the fair value at the cutoff inflates markouts.
**How to avoid:** fair value uses the candle close at the cutoff and climatology through year D−1; property test: shuffling post-cutoff data leaves every order and price unchanged.

### Pitfall 13: Auction value leak
**What goes wrong:** pro-rata rounding creates or destroys units or cash; fills above a buyer's limit or below a seller's limit.
**How to avoid:** money-failure tests on `clear()` only: Σ buy fills = Σ sell fills = V; each fill ≤ qty; no buy filled with limit < p*; no sell filled with limit > p*; cash in = cash out + fees exactly (integer micro-units).

### Pitfall 14: Backtest with no power
**What goes wrong:** claiming the capital rule "passed" on 68 days. Expected 99 % exceedances: 0.68 in 68 days.
**How to avoid:** state the Kupiec rejection counts up front (pre-registration); call the backtest weak where it is weak.

## Code Examples

### ZBP load, "N" imputation, small-business filter
```python
# Layout: www2.census.gov/programs-surveys/cbp/technical-documentation/records-layouts/full-layout/zip_detail_layout.txt
# Columns seen in zbp23detail.txt: zip,name,naics,est,n<5,n5_9,n10_19,n20_49,n50_99,n100_249,n250_499,n500_999,n1000,city,stabbr,cty_name
import zipfile
import numpy as np
import pandas as pd

SIZE = ["n<5", "n5_9", "n10_19", "n20_49", "n50_99", "n100_249", "n250_499", "n500_999", "n1000"]
MID = np.array([2.5, 7, 14.5, 34.5, 74.5, 174.5, 374.5, 749.5, 1500.0])
SMALL = 4  # keep the first four classes (< 50 employees)

def load_zbp(path: str, naics6: set[str]) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        df = pd.read_csv(z.open("zbp23detail.txt"), dtype=str, encoding="latin-1")
    df = df[df["naics"].isin(naics6)].copy()
    est = df["est"].astype(int)
    size = df[SIZE].replace("N", np.nan).astype(float)
    hidden = size.isna()
    gap = (est - size.fillna(0).sum(axis=1)).clip(lower=0)
    # spread the gap over suppressed cells, at most 2 per cell, remainder to the smallest suppressed class
    per = np.minimum(2.0, gap / hidden.sum(axis=1).replace(0, np.nan)).fillna(0.0)
    size = size.fillna(0.0) + hidden.mul(per, axis=0)
    rest = (est - size.sum(axis=1)).clip(lower=0)
    first_hidden = hidden.values.argmax(axis=1)
    has_hidden = hidden.any(axis=1).values
    vals = size.values
    vals[np.arange(len(vals))[has_hidden], first_hidden[has_hidden]] += rest.values[has_hidden]
    out = df[["zip", "naics", "stabbr"]].reset_index(drop=True)
    small = pd.DataFrame(vals[:, :SMALL], columns=SIZE[:SMALL])
    long = out.join(small).melt(id_vars=["zip", "naics", "stabbr"], var_name="size", value_name="est")
    long["employees"] = long["size"].map(dict(zip(SIZE, MID)))
    return long[long["est"] > 0]
```

### Nearest settlement station (haversine), 40 km cap
```python
# Station coordinates from the GHCN-Daily inventory (checked 2026-09-30)
STATIONS = {"NYC": (40.7789, -73.9692), "EWR": (40.6828, -74.1692), "TTN": (40.2769, -74.8158),
            "MDW": (41.7842, -87.7553), "MIA": (25.7881, -80.3169)}

def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))

def assign_station(zcta: pd.DataFrame, max_km: float = 40.0) -> pd.DataFrame:
    names = list(STATIONS)
    lat = np.array([STATIONS[s][0] for s in names]); lon = np.array([STATIONS[s][1] for s in names])
    d = haversine_km(zcta["lat"].values[:, None], zcta["lon"].values[:, None], lat[None, :], lon[None, :])
    k = d.argmin(axis=1)
    out = zcta.assign(station=np.array(names)[k], dist_km=d[np.arange(len(d)), k])
    return out[out["dist_km"] <= max_km]
```

### Signed hedge units by projecting the prior exposure onto H(T)
```python
def hedge_units(daily_rev: float, e_T_pct: float, T0: float, t_hist: np.ndarray, K: float, cap: float = 6.0) -> float:
    """Min-variance units of the $1/°F capped heat cover H = clip(T-K, 0, cap) offsetting
    daily_rev * (e_T_pct/100) * max(T - T0, 0). Positive = buys heat cover (short heat)."""
    expo = daily_rev * (e_T_pct / 100.0) * np.maximum(t_hist - T0, 0.0)
    H = np.clip(t_hist - K, 0.0, cap)
    slope = np.cov(expo, H, ddof=1)[0, 1] / H.var(ddof=1)
    return -slope
```

### Uniform-price clearing on a tick grid (the one shared implementation)
```python
from collections import defaultdict
from dataclasses import dataclass

@dataclass(frozen=True)
class Order:
    oid: str
    side: int      # +1 buy X, -1 sell X
    qty: float     # units
    limit: float   # $ per unit, in [0, xmax]

def clear(orders: list[Order], ref: float | None, xmax: float = 6.0, tick: float = 0.01):
    """Rules: max volume -> min |imbalance| -> grid price nearest ref -> midpoint (BCS 2014).
    Long side filled by price priority, pro-rata within the marginal price level (BCS 2014)."""
    grid = np.round(np.arange(0.0, xmax + tick / 2, tick), 6)
    buys = [o for o in orders if o.side > 0]
    sells = [o for o in orders if o.side < 0]
    bl = np.array([o.limit for o in buys]); bq = np.array([o.qty for o in buys])
    sl = np.array([o.limit for o in sells]); sq = np.array([o.qty for o in sells])
    D = (bq[None, :] * (bl[None, :] >= grid[:, None] - 1e-9)).sum(axis=1) if buys else np.zeros_like(grid)
    S = (sq[None, :] * (sl[None, :] <= grid[:, None] + 1e-9)).sum(axis=1) if sells else np.zeros_like(grid)
    vol = np.minimum(D, S)
    if vol.max() <= 0:
        return None, {}
    ok = np.isclose(vol, vol.max())
    imb = np.where(ok, np.abs(D - S), np.inf)
    ok &= np.isclose(imb, imb.min())
    idx = np.flatnonzero(ok)
    target = ref if ref is not None else (grid[idx].min() + grid[idx].max()) / 2
    i = idx[np.argmin(np.abs(grid[idx] - target))]          # first (lower) price on an exact tie
    p, V = float(grid[i]), float(vol[i])
    fills: dict[str, float] = {}
    for side_orders, better_first in ((buys, True), (sells, False)):
        elig = [o for o in side_orders if (o.limit >= p - 1e-9 if o.side > 0 else o.limit <= p + 1e-9)]
        levels = defaultdict(list)
        for o in elig:
            levels[o.limit].append(o)
        left = V
        for lim in sorted(levels, reverse=better_first):
            lvl = levels[lim]
            q = sum(o.qty for o in lvl)
            take = min(q, left)
            for o in lvl:
                fills[o.oid] = take * o.qty / q
            left -= take
    return p, fills
```
Money-failure properties to test (and only these): Σ buy fills = Σ sell fills = V; every fill ≤ qty; no fill outside a limit; for Phase 8, integer micro-unit rounding leaves dust unfilled, never minted.

### ES, H-day scenario losses, capital, marginal ES
```python
def es(losses: np.ndarray, alpha: float = 0.99) -> float:
    """Expected shortfall (CTE) of a loss sample: mean of the worst (1-alpha) share, fractional tail weight."""
    x = np.sort(np.asarray(losses, dtype=float))[::-1]
    k = len(x) * (1 - alpha)
    m = int(np.floor(k))
    if k <= 0:
        return float(x[0])
    tail = x[:m].sum() + (k - m) * (x[m] if m < len(x) else 0.0)
    return float(tail / k)

def h_day_losses(pnl: np.ndarray, H: int, block: int, reps: int, rng: np.random.Generator):
    """pnl: (n_years, n_days_in_window) pool P&L of the CURRENT book on each historical day, all stations
    from the same calendar date. Returns (historical overlapping-window losses, joint-date block-bootstrap losses)."""
    ny, nd = pnl.shape
    hist = -np.stack([pnl[:, s:s + H].sum(axis=1) for s in range(nd - H + 1)], axis=1).ravel()
    nb = -(-H // block)
    y = rng.integers(0, ny, size=(reps, nb))
    s = rng.integers(0, nd - block + 1, size=(reps, nb))
    paths = np.stack([pnl[y[:, b, None], s[:, b, None] + np.arange(block)] for b in range(nb)], axis=1)
    boot = -paths.reshape(reps, -1)[:, :H].sum(axis=1)
    return hist, boot

def capital(pnl: np.ndarray, H: int, full_collateral: float, block: int = 7, reps: int = 10_000, seed: int = 20260930):
    hist, boot = h_day_losses(pnl, H, block, reps, np.random.default_rng(seed))
    return min(full_collateral, max(es(boot, 0.99), float(hist.max()), 0.0))

def marginal_es(unit_pnl: np.ndarray, book_pnl: np.ndarray, alpha: float = 0.99) -> np.ndarray:
    """Euler / co-ES: mean loss of +1 unit of each contract in the book's worst (1-alpha) scenarios.
    unit_pnl: (n_scen, n_contracts); book_pnl: (n_scen,)."""
    n_tail = max(1, int(len(book_pnl) * (1 - alpha)))
    tail = np.argsort(book_pnl)[:n_tail]
    return -unit_pnl[tail].mean(axis=0)
```

### House quote and markouts
```python
def quote(mu: float, des_if_sell: float, des_if_buy: float, coc: float, fee: float, xmax: float = 6.0):
    """des_*: marginal H-day rolling-book ES of one unit-day (from marginal_es on the H-day scenario matrix)."""
    lam = coc / 365.0                                         # capital held continuously, charged per unit-day
    ask = np.clip(mu + lam * des_if_sell + fee, 0.0, xmax)   # des < 0 when the trade reduces book risk
    bid = np.clip(mu - lam * des_if_buy - fee, 0.0, xmax)
    return float(bid), float(ask)

def add_markouts(fills: pd.DataFrame) -> pd.DataFrame:
    """fills: day, station, side (+1 house bought X), qty, price, payout, mu_2h, hedge_pnl (Kalshi leg incl. fees)."""
    mo = fills["side"] * (fills["payout"] - fills["price"]) * fills["qty"]
    return fills.assign(mo_settle=mo,
                        mo_2h=fills["side"] * (fills["mu_2h"] - fills["price"]) * fills["qty"],
                        mo_hedged=mo + fills["hedge_pnl"])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| USDA PRF settled on the NOAA CPC gauge grid | PRF settles on NCEI **nClimGrid monthly final**, averaged to 0.25°, history from 1951 | crop year 2027 (RMA processing note posted 2026-06) | the largest US parametric program now uses the same NOAA family we use, and settles on **final** data (posted ~2 months after the month) |
| Census data API keyless for light use | API returns 302 → `missing_key.html` without a key | observed 2026-09-30 (change date unknown) | bulk files only for agents |
| CBP 2022 | CBP/ZBP 2023 is latest (files dated 2025-06-26); 2024 not posted | 2025 | NAICS 2017 codes |
| CoW Protocol surplus-only fees | 2 bps volume fee (0.3 bps correlated assets) + 50 % of surplus / quote improvement, capped 0.98 % of volume | current docs, 2026 | precedent for "small bps on volume + share of price improvement" |
| Nexus Mutual MCR% from a full capital model on-chain | `MCR = active cover / gearing factor`, gearing 4.8 (capital ≈ 20.8 % of active cover); full model run off-chain, factor changed by governance | post Nov-2023 tokenomics, current docs | auditable one-parameter capital rule precedent for an on-chain pool |
| Kalshi weather settled on NWS CLI with ad hoc handling | series metadata: settle on the first non-preliminary publication (The Weather Company feed; NWS as source agency); hold on material error until a corrected publication or the expiration date; revisions after expiration ignored; last fair price if no data | series metadata updated 2026-09 | direct precedent for our revision rule |

**Deprecated/outdated:**
- Using Lazo et al. (2011) as a daily business elasticity: it is annual, state-level GSP; keep it as a cap only.
- NOAA CPC as the PRF index: replaced by nClimGrid from crop year 2027.
- NAICS 2017 codes may switch to 2022 codes in a later CBP release (clothing 448 → 458); check the code list when CBP 2024 appears and re-key the prior table if needed.

## Open Questions

1. **Who owns the clearing function?**
   - What we know: Phase 7 (07-03) builds the engine's batch auction; Phase 4 (04-02) needs the same rules on history.
   - What's unclear: which lands first.
   - Recommendation: one `wi.auction.clear` per Pattern 3; whichever phase gets there first writes it, the other imports it; Phase 8 ports it and reuses the money-failure properties.
2. **Residual design (Phase 3 verdict pending).**
   - What we know: per-cell nClimGrid failed (ins2); regional factor and station pairs untested.
   - Recommendation: run Phase 4 with a placeholder residual = county-average H minus station H (nClimGrid-Daily county means, 1951–), swap in the Phase 3 contract when it is frozen, log as a deviation.
3. **Hedging demand and asymmetry.** No data on who would actually participate or at what loading. Sensitivity grid only; state it as an assumption in every headline number.
4. **Kalshi candle depth before 2026-07.** Phase 1 manifest lists settled markets since 2021-08 (NY, CHI) and 2023-05 (MIA); whether hourly candles exist that far back is for Phase 1 to confirm. If not, the test set is 68/34 days and the backtest can only reject at ≥ 3 exceedances.
5. **CME and Arbol revision rules not verified.** CME weather indexes are built from NWS observations processed by Speedwell Settlement Services (search result quoting the CME rulebook); the rulebook's data-correction clause could not be fetched (cmegroup.com blocked or timed out). No public Arbol/dClimate revision policy was found. WRMA/ISDA practice: data correction vs payment date is one of the most disputed confirmation terms, sometimes solved with a second settlement date. The recommended rule leans on Kalshi and USDA PRF, which are verified.
6. **Cost-of-capital rate.** Solvency II's risk margin used 6 % (Delegated Regulation 2015/35 Art. 39); the 2024–25 Solvency II review lowers it (4.75 % per training knowledge, not re-verified). The CoC sweep (6/15/30 %) covers this.
7. **Small-firm receipts per employee.** SUSB also has enterprise-size rows (`<20`, `20–99`); using them instead of the all-size ratio may lower revenue for small restaurants. Planner's call; report which was used.
8. **Rain.** Only NYC has a daily rain ladder (KXRAINNYC binary, 2021-09 → 2026-07) and monthly ladders exist for NYC/CHI/MIA. Rain netting is descriptive unless Phase 2 finds a tradable daily rain hedge.

## Pre-registration Draft (EVAL-04 / EVAL-05)

_Status: DRAFT, written 2026-09-30 before any netting, auction, capital or markout number exists. 04-01 copies it to `reports/eval-04-05/PREREG.md`, fills only the items marked [04-01] from inputs that do not use Phase 4 outcomes, commits it with the prior CSV, and records the commit hash. After that every change goes to the deviations log with the before and after numbers._

### Questions
- Q4a How much opposite-sign small-business weather exposure cancels at ZIP, station and metro level?
- Q4b What does one uniform-price auction per station-day leave for the pool, and at what prices?
- Q5a How much capital does the pool need per $ of cover, and does the rule survive an out-of-sample backtest?
- Q5b What do the house MM's fills earn after Kalshi hedging costs including fees?
- Q5c How often does the stated revision policy settle on a value that later changes the payout?

### Sample
- **Population:** ZBP 2023 detail × SUSB 2022 × 2024 ZCTA gazetteer; the NAICS rows of the frozen prior table; establishments with < 50 employees; each ZIP assigned to the nearest of Central Park (NYC), EWR, TTN, Midway (MDW), MIA within 40 km.
- **Hedge days:** every settled day of KXHIGHNY, KXHIGHCHI, KXHIGHMIA, KXHIGHTEWR, KXHIGHTTTN in Phase 2's frozen sample with a candle at the cutoff; per-station counts recorded [04-01]. Primary result on May 1–Sep 30 days; all months secondary.
- **Weather history (capital):** GHCN-D TMAX 1951–2025 for the five stations (ORD + MDW−ORD offset before 1997 for MDW); nClimGrid-Daily county averages 1951–2025 for the residual (county set [04-01] from the Phase 3 definition; default: counties whose internal point is within 40 km of the station).
- **Split:** capital model calibrated on 1951–2020; tested on the Kalshi-era days. Deployable capital re-fit on 1951–2025 and reported separately.

### Fixed choices
- Instrument: `H(T) = min(max(T − K, 0), 6)` $ per $1/°F unit, `K` = ladder second-bracket floor at the cutoff. Residual = Phase 3 contract, else the placeholder in Open Question 2, shifted to `[0, 12]`.
- Hedge units per business from Pattern 2 using 1951–2020 station history; hedge ratio 1.
- Participation: 0.5 %, 2 % (primary), 10 % of small establishments, independent draws, seed 20260930. Secondary: participation weighted by persistence (high 1.5×, medium 1×, low 0.5×, renormalised to the same total).
- Hedger limits: loading `ℓ_i ~ U[0, 0.25]` of the expected payout of the cover the business buys. Short-heat (buys H): limit `μ(1 + ℓ_i)`. Long-heat (buys cool cover = sells H): limit `μ − ℓ_i(6 − μ)`.
- House: quotes per Pattern 5, CoC 15 % primary (6 %, 30 % secondary); absorbs imbalance up to a pool seed of [04-01, default $250,000]; orders beyond capacity stay unfilled and are counted.
- Cutoff T−24 h primary, T−2 h secondary. Kalshi hedge at the candle ask at the cutoff, capped at recorded depth (default 10 units per city-day where no book exists, the middle of ins1's 5–20), fee `0.07·P·(1−P)` per contract.
- Protocol fee 10 bps of notional primary; 0/25/50 bps secondary.
- Capital: Pattern 4, ES99, H = 30 primary (1, 5 secondary), block 7 days, 10,000 paths.
- Revision: N per the Pattern 7 table.

### Metrics and verdict rules (fixed now)
| ID | Metric | Verdict rule |
|---|---|---|
| M1 | Netting ratio at station level `NR = Σ_t 2·min(L_t, S_t) / Σ_t (L_t + S_t)` (hedger units only; house excluded), per station and pooled; also ZIP and metro (NYC+EWR+TTN as one metro, MDW, MIA) | **MATERIAL** if pooled NR ≥ 0.30 under central priors AND ensemble 10th percentile ≥ 0.15; **WEAK** if 0.10 ≤ central < 0.30 or ensemble p10 < 0.15; **FAILS** if central < 0.10. Always report NR under the shrink-to-common null; if null NR < 0.10, the write-up must say the result rests on the priors' sign spread |
| M2 | Leftover exposure `abs(L − S)` (units, $ max payout, σ of daily payout) per station-day | descriptive |
| M3 | Station-leg internalisation (matched station units ÷ gross) and Kalshi cost avoided = matched units × (ask − μ + fee) at the cutoff | descriptive, shown next to fee income |
| M4 | Clearing price − μ; no-trade share; house fill share; unfilled share from capacity | descriptive |
| M5 | Capital per $ of cover `CPC = C_30 / gross cover`, gross cover = Σ over participating businesses and the 30 days of (units held × $6), both sides counted, so netting shows up as lower capital; `C_30` is for the pool's net book. Also `C_30` per $ expected payout and per $ annual premium; full-collateral requirement and `FC / C_30` | **PASS** if CPC ≤ 0.21 (≈ Nexus Mutual's 1/4.8) with the station leg hedged at capped depth; **FAIL** if CPC > 0.50 |
| M6 | Backtest on test days: exceedances of 1-day VaR99 (Kupiec) and any realised 30-day loss above `C_30` | reject the VaR at ≥ 3 exceedances (n = 68), ≥ 4 (120), ≥ 9 (400), ≥ 24 (1,600) (binomial tail p < 0.05 at 1 %); **any** `C_30` breach = FAIL |
| M7 | Pool return = annualised (protocol fees + Σ `mo_hedged`) ÷ `C_30` | **PASS** if ≥ 15 % at 2 % participation and central priors with the 90 % block-bootstrap lower bound > 0; **FAIL** if the point estimate < 0 |
| M8 | Markouts: mean `mo_settle`, `mo_2h`, `mo_hedged` (c/contract, $/unit-day) with 95 % block-bootstrap CIs; worst day / 5-day / 30-day; worst day ÷ mean day; share of P&L from the 5 worst days; cross-station daily correlation; ins1 V1 as benchmark | **KEEP** house quoting if mean `mo_hedged` > 0 with CI lower bound > 0 AND worst 30-day loss ≤ `C_30`; **NOT KEEP** if mean `mo_hedged` < 0; else **INCONCLUSIVE** |
| M9 | Revision share per source (Pattern 7) | **ACCEPTABLE** ≤ 2 % of units change payout by ≥ $0.50/unit (or flip the wet-day flag); **WINDOW REQUIRED** 2–5 %; **REJECT AT N** > 5 %; "not measurable" if < 20 vintage-days exist by the report date |

### Method (order)
1. Commit PREREG + `priors_2026-09-30.csv`; record hash.
2. Build the population artifact (row count + md5 in the manifest).
3. Hedge units per business from 1951–2020 station history.
4. For each test day: orders at the cutoff; `μ` from the candle at the cutoff; clear the station and residual auctions; house fills; Kalshi hedge at the cutoff ask capped at depth; settle on Phase 2's settlement truth and the residual index.
5. M1–M4, M7, M8.
6. Scenario matrices on 1951–2020 for each day's book (backtest) and the average book (headline); M5, M6.
7. M9 from vintages.
8. Ensemble, null and the sensitivity grid.
9. Write-up with deviations to `reports/eval-04-05/`.

### Look-ahead controls
- Priors frozen (hash) before step 2; hedge units use no Kalshi-era weather.
- `μ` uses only data at or before the cutoff; climatology through year D−1; detrending fit on 1951–2020 for the backtest.
- Participation and loading draws seeded and independent of weather.
- Money-failure tests only (AGENTS.md): shuffling post-cutoff weather leaves every order, price and fill unchanged; clearing conserves units and cash; settlement never reads a vintage newer than `T+N`.

### Sensitivity grid (reported, not part of verdicts)
participation {0.5, 2, 10 %} × cutoff {24 h, 2 h} × fee {0, 10, 25, 50 bps} × CoC {6, 15, 30 %} × H {1, 5, 30} × priors {central, ensemble p10/p50/p90, null} × residual {placeholder, Phase 3 design(s)}.

## Sources

### Primary (HIGH confidence; fetched or downloaded 2026-09-30)
- Census ZBP 2023 detail + record layout — `https://www2.census.gov/programs-surveys/cbp/datasets/2023/zbp23detail.zip`, `.../technical-documentation/records-layouts/full-layout/zip_detail_layout.txt` (downloaded, parsed, row count and "N" pattern checked)
- Census API key requirement — `https://api.census.gov/data/2023/cbp?...` (302 to `missing_key.html`, header `X-DataWebAPI-KeyError: 1`)
- SUSB 2022 — `https://www2.census.gov/programs-surveys/susb/tables/2022/us_state_6digitnaics_2022.txt` (downloaded; NAICS 2017 codes; receipts per employee computed)
- 2024 ZCTA gazetteer — `https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip` (downloaded; used for the establishment counts above)
- GHCN-Daily inventory — `https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-inventory.txt` (station record starts)
- nClimGrid-Daily area averages — `https://www.ncei.noaa.gov/data/nclimgrid-daily/access/averages/` (1951–2026; county file format checked)
- NCEI USDA gridded data consumer guide and directories — `https://www.ncei.noaa.gov/pub/data/cirs/usda/Readme.docx`, `.../daily/initial-unsynced/` (39 tarballs 2026-08-21 → 09-28), `.../daily/initial-synced/`, `.../daily/final/`, `.../monthly/{initial,final}/`
- USDA RMA, "Rainfall Index – Data … 2027 and Beyond" — `https://www.rma.usda.gov/sites/default/files/2026-06/Rainfall%20Indexa%20Data%202027%20and%20Beyond%20Rainfall%20Index%20Processing.pdf`
- Kalshi series and market rules (keyless API) — `/trade-api/v2/series/KXHIGHNY`, `/markets?series_ticker=KXHIGHNY&status=settled`; contract terms `https://assets.kalshi.com/contract_terms/GLOBALTEMPERATURE.pdf`; fee worked example in `https://docs.kalshi.com/llms-full.txt` (Fee Rounding)
- IEM CLI JSON and AFOS archive — `https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2026`, `https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=CLINYC...`
- Budish, Cramton & Shim (2014), "Implementation Details for Frequent Batch Auctions", AER P&P 104(5):418–424 — `http://www.cramton.umd.edu/papers2010-2014/budish-cramton-shim-frequent-batch-auctions-aerpp.pdf` (clearing cases, pro-rata rule, reporting)
- Gnosis Auction (EasyAuction) — `https://github.com/gnosis/ido-contracts` README, `contracts/EasyAuction.sol` (fee ≤ 15/1000, `minFundingThreshold`, `minimumBiddingAmountPerOrder`), `contracts/libraries/IterableOrderedOrderSet.sol` (tie-break order)
- CoW Protocol docs — `https://docs.cow.fi/cow-protocol/concepts/introduction/batch-auctions`, `https://docs.cow.fi/governance/fees`
- Nexus Mutual docs — `https://docs.nexusmutual.io/protocol/capital-pool/mcr` (MCR = active cover / 4.8), `.../protocol/staking/staking-pools`
- Solvency II Directive 2009/138/EC Art. 101(3) (VaR 99.5 %, one year) — `https://www.legislation.gov.uk/eudr/2009/138/article/101`
- Roth Tran (2022 WP / 2023 Mgmt Sci), "Sellin' in the Rain" — `https://www.frbsf.org/wp-content/uploads/wp2022-02.pdf` (Tables 3–4, Section 5); FRBSF Economic Letter 2022-23 `https://www.frbsf.org/research-and-insights/publications/economic-letter/2022/08/impact-of-weather-on-retail-sales/`
- Deryugina (2021), "Climate Change and the Economy: The Role of Consumer Demand" — `https://ormir.giesbusiness.illinois.edu/docs/librariesprovider9/pdf/climate-change-and-the-economy_-the-role-of-consumer-demand.pdf`
- hl-mm ins1 / ins2 (read-only) — `~/hl-mm-wt/corpus-fix/reports/ins1/README.md`, `prior/hl-mm-ins/reports/ins1/results.txt`, `prior/hl-mm-ins/reports/ins2/README.md`

### Secondary (MEDIUM confidence)
- Lazo, Lawson, Larsen & Waldman (2011), BAMS 92:709–720, DOI 10.1175/2011BAMS2928.1 — via UCAR release `https://news.ucar.edu/4810/economic-cost-weather-may-total-485-billion-us` (full text blocked)
- Hirche, Haensch & Lockshin (2021), Int. J. Wine Business Research 33(3):432 — abstract-level figures via search
- Martínez-de-Albéniz & Belkaid (2021), EJOR 294(3):820–830 — abstract-level figures via RePEc/search
- Addoum, Ng & Ortiz-Bobea (2020), RFS 33(3):1331 — abstract via SSRN/OUP
- Starr-McCluer (2000), FEDS 2000-08 — abstract via RePEc
- Aylen, Albertson & Cavan (2014), Climatic Change 127:183–197 — abstract via search
- CME degree-day index data (NWS observations processed by Speedwell Settlement Services) — search snippet of CME rulebook ch. 403; not fetched
- WRMA/ISDA data-correction practice — GlobalCapital, "Documenting Weather Derivatives Transactions"
- Training knowledge, not re-verified today: Swiss Solvency Test uses expected shortfall at 99 % over one year; Lloyd's adds a 35 % uplift to the 1-in-200 SCR for member capital; ILS/cat bonds are typically fully collateralised to the limit; Avellaneda & Stoikov (2008), Guéant, Lehalle & Fernandez-Tapia (2013), Guéant (2017) on inventory-skewed quoting with correlated assets; Froot & Stein (1998) on hurdle rates for non-hedgeable risk; Euler / co-TVaR capital allocation (Tasche); burn analysis with detrending (Jewson & Brix 2005)

### Tertiary (LOW confidence; flag in any write-up)
- Planalytics claims (2–5 % of top-line sales weather-driven; c-store categories rise above 65 °F daily mean) — trade press
- Viscacha Data blog on Home Depot (rain days −4.8 %)
- Food-delivery weather effects (Chinese platform studies; US storm anecdotes)
- Cinema rain effect (+12 % trade-press claim) and Chinese cinema heat study
- Agnew & Thornes (1995) and Bujisic et al. (2017) — qualitative only in what was reachable
- Rows marked "no source found" in the prior table (car washes, HVAC contractors, landscaping, fitness): expert priors

## Metadata

**Confidence breakdown:**
- Standard stack (data files, libraries): HIGH — every file downloaded or listed today; versions read from `.venv` and PyPI.
- Architecture (auction rules, capital method, revision rule): HIGH for the mechanism precedents (BCS, Gnosis, CoW, Nexus, Kalshi, USDA), MEDIUM for the capital rule itself (a defensible synthesis, not an industry standard for this product).
- Elasticity priors: LOW–MEDIUM — two MEDIUM rows (apparel/sporting goods, liquor stores); the rest LOW; the cross-sector evidence argues for small netting, which is why the null scenario is mandatory.
- Pitfalls: HIGH — most were observed directly (API key, "N" cells, NAICS vintage, overlapping discs, NCEI county codes, Midway record start, Kalshi fee formula).

**Research date:** 2026-09-30
**Valid until:** 2026-10-30 for data paths and fees (Census, Kalshi and CoW change without notice); elasticity literature stable for longer.
