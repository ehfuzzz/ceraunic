# Phase 12: POS-connect - Research

**Researched:** 2026-09-30
**Domain:** Square Orders API adapter feeding the daily sales panel (TypeScript, server side of the Next.js portal); deterministic Square-shaped fixtures; flip to the sandbox by env var only
**Confidence:** HIGH on SDK and API mechanics (read from the `square@46.0.0` package source, type-checked with `tsc --strict`, and run offline on this Mac against an injected fixture fetch). MEDIUM on Developer Console click-path and the Shopify paragraph. LOW items are flagged inline.

## Summary

Researched: Square `SearchOrders` (request shape, filter rules, pagination, limits, money, time), the current Node SDK, sandbox setup and seeding, sandbox token vs OAuth, fixture design under the AGENTS.md testing rules, the Payments and Reporting APIs as alternatives, and Shopify as the later second adapter.

The standard approach: `square@46.0.0` (`SquareClient`), one `client.orders.search` loop per location with `state_filter: [COMPLETED]`, `date_time_filter.closed_at`, `sort CLOSED_AT ASC`, `limit 1000`, following `cursor` until it is absent. Each order's `closed_at` (UTC) is bucketed into the location's own IANA time zone date (from `Location.timezone`); gross sales are the sum of `line_items[].gross_sales_money.amount` (integer cents, `bigint` in the SDK); order count is the number of completed sale orders. The fixture path and the sandbox path run the same code: the SDK constructor takes a `fetch` option, and in fixture mode we inject a small function that answers `/v2/orders/search`, `/v2/locations` and `/v2/catalog/list` from a seeded generator. The only switch is whether `SQUARE_SANDBOX_ACCESS_TOKEN` is set. This was proven in a research spike: 3 locations x 5 days across the 2025-11-02 DST change, page size 37, one planted 429, SDK retry, exact match to an independent ledger. A second spike pushed 110,000 realistic orders (213 MB of wire JSON) through the SDK in 5.0 s.

Five facts change the plan. (1) The SDK defaults to **Production** when no environment is given, and falls back to a `SQUARE_TOKEN` env var when no token is passed (read in `BaseClient`/`BearerAuthProvider` source). Always pass both explicitly. (2) Amounts come back as `bigint`, and `JSON.stringify` throws on bigint (verified), so convert at the adapter boundary. (3) The SDK parses responses with `skipValidation: true`, so fixture drift from the real wire shape is invisible. 12-02 must diff a recorded sandbox page against the fixture shape. (4) `created_at`/`closed_at` are read-only, so the sandbox can only ever hold "today's" orders. The 400-day history in the demo always comes from fixtures. The sandbox check proves the wire works and that totals on seeded orders match exactly. (5) Five of the six lines in `~/.config/dev/secrets.env` have no `export`. A line without `export` does not reach child processes (verified in a clean zsh), so a pasted token would never reach the dev server and the portal would quietly stay on fixtures. The runbook says `export`, the dev script uses `set -a`, and the UI always shows the mode.

**Primary recommendation:** One `SalesSource` interface shared with the CSV path. Square implemented on `square@46.0.0` with an injected fixture `fetch`. Testing = one end-to-end fixture run whose panel must equal (a) a truth ledger the generator writes from local wall-clock days before any UTC conversion, and (b) the CSV path's panel for the same business.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `square` (npm) | **46.0.0** (published 2026-09-15; sends `Square-Version: 2026-09-16`) | Typed client: `client.orders.search`, `client.locations.list`, `client.catalog.list`, `client.orders.create`, `client.payments.create` | Official SDK (Fern-generated since v40). Built-in retries on 408/429/5xx with exponential backoff and `Retry-After` (default `maxRetries` 2). Bigint-safe JSON parser. `fetch` injection point. Runs on Node 18+ and Vercel (README "Runtime Compatibility") |
| Square Orders API | `POST /v2/orders/search`, scope `ORDERS_READ` | Completed orders per location and time window | The only Square endpoint that gives order-level line items (gross sales, categories) plus order counts |
| Square Locations API | `GET /v2/locations`, scope `MERCHANT_PROFILE_READ` | `id`, `name`, `timezone` (IANA), `coordinates`, `currency`, `address` | The time zone for day bucketing and the lat/lon for the weather-station join come from here |
| `Intl.DateTimeFormat` (built-in) | Node 22 (this Mac: v22.20.0) | UTC instant to local `YYYY-MM-DD` in the location's zone (`en-CA` locale formats as ISO date) | Uses the ICU tz database, so DST is handled. No tz library needed |
| `node:crypto` (built-in) | — | sha256 for per-(location, date) seeds, order ids, manifest hashes | Deterministic, no dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Square Catalog API | `client.catalog.list({ types: "ITEM,CATEGORY" })`, scope `ITEMS_READ` | Map `line_items[].catalog_object_id` (a variation id) to its item's `reporting_category` / `categories[0]` name | Only when `includeCategories` is requested (optional column) |
| Square Payments API | `client.payments.create`, sandbox only | Pay seeded sandbox orders with `source_id: "cnon:card-nonce-ok"` so they become `COMPLETED` | 12-02 seeding script only |
| Test runner | whatever Phase 10 scaffolds (Vitest or `node:test`) | e2e fixture run | Do not add a second runner |
| `tsx` | 4.x | Run `scripts/square/*.ts` directly | Generator, sandbox seed and record scripts |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Orders `SearchOrders` | Payments `ListPayments` (`GET /v2/payments`, `PAYMENTS_READ`) | **Not simpler.** It filters on `created_at` only, returns at most 100 per page (vs 1,000), takes one `location_id` per call, and a split-tender order has several payments, so the order count is wrong. It has no line items (no categories), `total_money` includes tips, and refunds sit in `refunded_money`. Reject |
| Orders `SearchOrders` | Reporting API (`https://connect.squareup.com/reporting`, `/v1/meta` + `/v1/load`; open beta announced 2026-04-23; `REPORTING_READ`) | Would return daily `Sales.net_sales` / `Sales.order_count` by location matching Dashboard figures, and needs no order paging. But the docs only give the production base URL, sandbox support is unconfirmed (a Square forum answer from 2026-08-25 says custom reports are production-only), and the beta says field names may change. Keep as a v2 option for real merchants, not for this phase |
| SDK | Raw `fetch` + hand-written snake_case types | No dependency and Edge-friendly, but we would re-implement retry/backoff, bigint parsing and types. The SDK's `fetch` injection already gives us one code path. Use the SDK |
| `Intl.DateTimeFormat` | `luxon` / `date-fns-tz` / `Temporal` | Not needed for "instant to local date". Do not add |
| inline `mulberry32` PRNG | `seedrandom` | Either is fine. Inline is 6 lines, and sub-seeds come from sha256 |

**Installation:**
```bash
# inside the portal app Phase 10 scaffolds (assumed apps/portal)
npm install square@46.0.0 --save-exact
npm install -D tsx
```

## Architecture Patterns

### Recommended Project Structure
Paths assume Phase 10 puts the Next.js app at `apps/portal/`. Adjust if its plan differs.
```
apps/portal/
├── src/lib/sales/
│   ├── types.ts               # shared SalesSource / SalesPanel / DailySalesRow (below) — CSV + Square + later Shopify
│   ├── validate.ts            # panel invariants used by every source (integer cents, unique keys, date format, category sums)
│   ├── dates.ts               # enumerate LocalDate ranges with UTC calendar math (never local Date objects)
│   ├── csv-source.ts          # Phase 10 (10-02) CSV path, implements SalesSource
│   └── square/
│       ├── source.ts          # squareSalesSource(): resolveSquareMode, client factory, listLocations, fetchDaily
│       ├── search.ts          # cursor loop over client.orders.search
│       ├── aggregate.ts       # pure: Order[] + Location -> DailySalesRow[] (+ provenance counters)
│       ├── categories.ts      # optional: catalog.list -> variationId -> category name
│       ├── fixture-fetch.ts   # emulates the 3 endpoints the adapter calls, from the generator
│       └── generate.ts        # deterministic Square-shaped order generator + truth ledger
├── fixtures/square/           # committed, ~100-200 KB total (see Fixture design)
└── (route) app/api/pos/square/... # server-only route handlers, runtime "nodejs"
scripts/square/
├── gen-fixtures.ts            # writes truth-daily.csv, csv-export.csv, sample-orders.json, MANIFEST.json
├── seed-sandbox.ts            # 12-02, refuses to run unless host is connect.squareupsandbox.com
└── record-sandbox.ts          # 12-02, records real sandbox pages (no tokens) + shape diff vs generator
var/pos/                       # gitignored e2e outputs (panel CSVs, run manifest)
```

### Pattern 1: One interface, many sources, one panel
**What:** CSV upload and Square (and later Shopify) each implement `SalesSource`. Everything downstream (elasticity view, coverage recommendation, Phase 5 estimator via CSV export) reads only `SalesPanel`. No `if (source === "square")` downstream.
**When to use:** Always. The panel is the contract.

### Pattern 2: Same code path, injected transport
**What:** The Square adapter always builds a `SquareClient` and calls the same SDK methods. In fixture mode the client gets `fetch: fixtureFetch`, which answers from the generator. In sandbox mode it gets no `fetch` override (global fetch) and a real token. The switch is `SQUARE_SANDBOX_ACCESS_TOKEN` being set, resolved once and carried on the panel as `mode`.
**Why:** "No code change" at flip time, and the fixture exercises the SDK's real request serialization, retry and response parsing.

### Pattern 3: Padded UTC window, bucket locally, keep an id set
**What:** For local dates `[start, end]`, query `closed_at` from `start - 2 days 00:00Z` to `end + 2 days 00:00Z` (covers every US offset). Bucket each order by `Intl` local date in `Location.timezone` and drop dates outside `[start, end]`. Track order ids and count duplicates.
**Why:** No DST math when building the query, no double counting from Square's inclusive `start_at`/`end_at`, and no per-day queries (which multiply pages and cursors).

### Pattern 4: Integer cents as bigint inside, safe number at the boundary
**What:** Sum `BigInt(amount)` per day. Convert once with a `Number.isSafeInteger` check when building `DailySalesRow`. Assert `currency === "USD"`.
**Why:** SDK amounts are `bigint`. Next.js route handlers and server actions cannot serialize bigint. Dividing by 100 before summing is the classic float drift.

### Pattern 5: Mode is resolved once, shown always, injected in tests
**What:** `resolveSquareMode(process.env)` runs only in the route handler. Tests construct `squareSalesSource({ mode: "fixture" })` explicitly. The UI shows a badge: "Demo data (recorded Square responses)" or "Square sandbox (test seller)".
**Why:** The token lives in a global secrets file. Once the owner pastes it, any test that resolved mode from env would silently start calling the sandbox.

### The shared adapter interface (CSV and POS)

```typescript
// apps/portal/src/lib/sales/types.ts  — shared by csv-source.ts, square/source.ts, later shopify/source.ts

/** Calendar date "YYYY-MM-DD" in the LOCATION's own IANA time zone. Never a UTC date. */
export type LocalDate = string & { readonly __brand: "LocalDate" };

export type SalesSourceKind = "csv" | "square" | "shopify";
export type SalesSourceMode = "upload" | "fixture" | "sandbox" | "production";

export interface SalesLocation {
  /** Source-qualified and stable: "square:L88917AVBK2S5", "csv:scoops-midtown". */
  id: string;
  name: string;
  /** IANA zone, required. Square: Location.timezone. CSV: chosen in the upload form. */
  timezone: string;
  /** Prototype is USD-only; any other currency is rejected, never converted. */
  currency: "USD";
  /** Square: Location.coordinates. CSV: geocoded postal code or entered. Used for the station join. */
  lat?: number;
  lon?: number;
  postalCode?: string;
}

export interface DailySalesRow {
  locationId: string;          // SalesLocation.id
  date: LocalDate;
  /** Integer US cents, >= 0. Definition in "Metric definitions" below. */
  grossSalesCents: number;
  /** Integer >= 0. Completed sale orders. */
  orderCount: number;
  /** Optional. Category name -> integer cents; values sum EXACTLY to grossSalesCents
   *  ("Uncategorized" absorbs custom amounts and unknown/deleted catalog ids). */
  categories?: Record<string, number>;
}

export interface SalesPanel {
  source: SalesSourceKind;
  mode: SalesSourceMode;
  locations: SalesLocation[];
  /** Sorted by (locationId, date); unique per (locationId, date).
   *  POS sources emit an explicit 0/0 row for every date in [start, end]; the CSV path does the same
   *  for dates inside its covered span (see Pitfall 11). */
  rows: DailySalesRow[];
  start: LocalDate;            // inclusive
  end: LocalDate;              // inclusive
  /** Rows on/after this date may still change (Square: offline POS orders can arrive up to 72 h late). */
  provisionalFrom?: LocalDate;
  /** UTC ISO-8601 with Z. */
  pulledAt: string;
  /** Provenance for the run manifest: api host or "fixture", Square-Version, pages, orders seen,
   *  duplicates, skipped counts by reason (returnOrders, giftCardLines, customAmountLines, nonUsd, ...). */
  provenance: Record<string, string | number>;
}

export interface FetchDailyRequest {
  locationIds: string[];       // SalesLocation.id values
  start: LocalDate;
  end: LocalDate;              // inclusive
  includeCategories?: boolean;
  signal?: AbortSignal;
}

export interface SalesSource {
  readonly kind: SalesSourceKind;
  readonly mode: SalesSourceMode;
  listLocations(): Promise<SalesLocation[]>;
  fetchDaily(req: FetchDailyRequest): Promise<SalesPanel>;
}

// Factories (signatures only; bodies in the plans)
export declare function csvSalesSource(csvText: string, opts: { locations: SalesLocation[] }): SalesSource;          // Phase 10
export declare function squareSalesSource(opts?: { mode?: "fixture" } | { mode: "sandbox"; token: string }): SalesSource; // Phase 12; no arg = resolve from env
export declare function validatePanel(p: SalesPanel): string[];  // [] = valid; every source calls it before returning
```

### Metric definitions (both paths must match; Phase 10's CSV help text uses the same words)
| Field | Square definition | Excluded |
|-------|-------------------|----------|
| `date` | Local calendar date of `order.closed_at` in `Location.timezone` | — |
| `grossSalesCents` | Sum of `line_items[].gross_sales_money.amount` over line items with `item_type` `ITEM` or `CUSTOM_AMOUNT`, on orders with `state = COMPLETED` | Sales tax (exclusive tax sits in `total_tax_money`; for US inclusive tax Square already deducts it from `gross_sales_money`), tips, service charges, discounts not netted (gross), gift-card loads (`item_type = GIFT_CARD`), returns (separate return orders; not netted) |
| `orderCount` | Completed orders with at least one counted line item | Pure return orders (no `line_items`), gift-card-only orders, `OPEN`/`CANCELED`/`DRAFT` |
| `categories` | Catalog variation -> item -> `reporting_category` (else `categories[0]`) -> category name; else "Uncategorized" | — |

Square's own field docs: `gross_sales_money` = "sum of the variation's total price and each modifier's total price. For inclusive tax items in the US, Canada, and Japan, tax is deducted" (SDK `OrderLineItem` type docs). Returns are modeled as separate return orders that link back to the sale order. Exchanges carry both new line items and a `returns[]` entry in one order (Square "Refunds and Exchanges" guide). Whether Square Dashboard's "Gross sales" also excludes gift-card loads is **LOW** confidence (from memory). Ours excludes them either way, by definition.

### Fixture design (question 5)

**Window and locations.** 2025-08-27 through 2026-09-30 inclusive = exactly 400 local dates per location (computed). The window contains DST end 2025-11-02, DST start 2026-03-08, Thanksgiving 2025-11-27, 2025-12-25, 2026-01-01 and 2026-07-04. One fixture merchant with three locations, which is also what the sandbox test seller will look like:

| Fixture location id | City / zone | Near station | Business | Planted weather effect |
|---|---|---|---|---|
| `LFIXNYC000001` | Manhattan, `America/New_York`, 40.7648, -73.9808 | Central Park (KXHIGHNY) | ice cream + coffee | long heat: beta = +0.012 per degF over Tref 70 |
| `LFIXCHI000002` | Chicago SW side, `America/Chicago`, 41.7868, -87.7522 | Midway (KXHIGHCHI) | coffee + bakery | short heat: beta = -0.006 per degF over Tref 60 |
| `LFIXMIA000003` | Miami, `America/New_York`, 25.7959, -80.2870 | MIA (KXHIGHMIA) | juice + cafe | mild short heat: beta = -0.004 per degF over Tref 84 |

These three can double as Phase 13's "one per city, opposite exposures" demo businesses.

**Demand model** (all parameters in `params.json`; the planted betas go in the manifest so the elasticity view and Phase 5 estimator can be checked against a known answer):
`lambda(loc, d) = base_loc x dow[weekday] x (1 + A_loc * sin(2*pi*(doy - 110)/365)) x exp(beta_loc * (tmax_F - Tref_loc)) x holiday x closure`
- base: NYC 95, CHI 80, MIA 85 orders/day. dow: Mon 0.85, Tue 0.88, Wed 0.92, Thu 0.98, Fri 1.12, Sat 1.35, Sun 1.25. A: 0.20 / 0.10 / 0.05.
- `orderCount ~ Poisson(lambda)`. Each order has 1-3 line items (P = 0.55 / 0.33 / 0.12), quantity 1-2, from a 9-item / 3-category catalog per location at fixed prices ($3.75-$9.75). Exclusive sales tax (NYC 8.875 %, CHI 10.25 %, MIA 7 %) goes in `total_tax_money`, tips on 35 % of orders in `total_tip_money`. Neither is in gross.
- `tmax_F` comes from `station-tmax.csv` (1,200 rows) copied from Phase 1's IEM ASOS table (plan 01-03) for NYC / MDW / MIA. If that table is not there at execution time, use a synthetic seasonal curve plus AR(1) noise and set `tmax_source: "synthetic"` in the manifest. The file is committed either way, so the output is deterministic.
- Expected volume is about 95 orders/day/location, roughly 110k orders total, about 213 MB of wire JSON at ~1.9 KB/order. The research spike pushed 110,000 orders of this shape through the SDK in **5.0 s** on this Mac.

**Planted edge cases** (each has a count in the manifest):
- `OPEN` 1.0 % and `CANCELED` 0.5 %. The fixture server's state filter removes them; the adapter must see 0.
- Return orders 0.4 %: `COMPLETED`, `returns[]` present, no `line_items`.
- Gift-card loads 0.3 % (`item_type: GIFT_CARD`) and custom-amount lines 2 % (`CUSTOM_AMOUNT`, no catalog id, so "Uncategorized").
- Edge-time orders every day at `00:00:00.000` and `23:59:59.999` local.
- Orders at 01:30 on 2025-11-02 (the repeated hour). No orders 02:00-03:00 on 2026-03-08 (that hour does not exist).
- All locations closed 2025-11-27 and 2025-12-25 (explicit 0/0 rows). CHI closed 2026-02-09..13 (renovation).

**Determinism.**
- Per-(location, date) sub-seed = first 4 bytes of `sha256("${seed}|${locationId}|${date}")`, fed to `mulberry32`. Changing one day or location reshuffles nothing else.
- No `Math.random`, no `Date.now()` in the generator.
- Order ids = 27-char base62 of `sha256(locationId|date|i)`, the same length as real Square order ids.
- Timestamps via `toISOString()` (ms + `Z`). The adapter must also accept offset forms, since `new Date()` parses both.
- Local-to-UTC conversion in the generator uses `Intl` offset lookup with a two-pass correction. The adapter uses `Intl.DateTimeFormat` formatting. Both rely on ICU, which is the source of truth.

**Why this is not a mirror test.** The generator writes `truth-daily.csv` inside its local-date loop, from the prices it draws, **before** converting times to UTC. The adapter only ever sees UTC `closed_at`, pages, cursors, states and wire money. The totals match only if bucketing, DST, pagination, dedupe, state filtering, bigint money and the gift-card/return exclusions are all correct.

**Storage** (committed unless noted):
```
apps/portal/fixtures/square/
  params.json          seed, window, locations, demand params, noise rates, generator version
  station-tmax.csv     1,200 rows: date,station,tmax_f  (+ source note)
  locations.json       ListLocations wire response (snake_case, as Square sends it)
  catalog.json         ListCatalog wire pages (ITEM + CATEGORY objects, cursor between pages)
  sample-orders.json   first 25 orders of LFIXNYC000001 as a SearchOrders wire page (human exemplar)
  truth-daily.csv      1,200 rows: location_id,date,gross_sales_cents,order_count,cat_<name>...  (generator-written)
  csv-export.csv       the same business in Phase 10's CSV upload format (parity input)
  MANIFEST.json        planted counts by kind, sha256 of the canonical order stream (JSONL, never committed),
                       sha256 of truth-daily.csv and csv-export.csv, Square-Version, generator git hash, tmax_source
  recorded/            (12-02) real sandbox pages: locations + one orders page, response bodies only, no headers
var/pos/               (gitignored) panel-square-fixture.csv, panel-csv.csv, run-manifest.json
```
The full order stream is never stored. The generator yields orders per (location, date) on demand, and the fixture fetch pages them. `gen-fixtures --dump` writes JSONL.gz to `var/` for inspection. If the generator changes, `MANIFEST.json`'s stream hash changes, which makes generator drift a visible diff in review.

**Fixture fetch semantics.** It emulates only what the adapter calls. Anything else returns 404, so an unexpected call fails loudly.
- `POST /v2/orders/search`:
  - `location_ids` (more than 10 gives 400). `state_filter.states`. `date_time_filter.closed_at` inclusive on both ends, compared as instants.
  - A `closed_at` filter requires `sort_field: CLOSED_AT`, and `CLOSED_AT` sort requires a `state_filter`; otherwise 400 (both rules are Square's).
  - `sort_order` ASC/DESC (default DESC). `limit` default 500, max 1000 (more gives 400).
  - `cursor` = base64url `{h: sha256(body minus cursor), o: offset}`. A cursor sent with a different body gives 400 (Square requires the original query).
  - Once per run it returns one short page before the end, which catches "stop when page < limit" bugs.
  - Once, on page 2 of the first location, it returns 429 with `Retry-After: 1`, which exercises the SDK's retry path.
- `GET /v2/locations`: `locations.json`.
- `GET /v2/catalog/list?types=ITEM,CATEGORY`: `catalog.json` pages.

### Pre-registered acceptance rules (AGENTS.md: written before any number exists)
- **A1 Fixture exactness.** The Square fixture-mode panel for all 3 locations x 400 days has exactly 1,200 rows. It must equal `truth-daily.csv` on every row: 0 cents difference, 0 order-count difference, and category cents equal when `includeCategories`. `provenance.duplicates == 0`. Any mismatch fails.
- **A2 CSV parity.** `csvSalesSource(csv-export.csv)` produces panel rows byte-identical (canonical CSV serialization) to the Square path's rows.
- **A3 Offline.** The fixture run completes with `globalThis.fetch` replaced by a stub that throws, which proves zero network calls. The run manifest records `mode: "fixture"` and `host: "fixture"`.
- **A4 Exclusions.** Provenance counts of return orders, gift-card lines and custom-amount lines equal the planted counts in `MANIFEST.json` exactly. `OPEN`/`CANCELED` orders seen by the adapter = 0.
- **A5 Sandbox exactness (12-02).** After seeding K orders per sandbox location today, each seeded location's row for today's local date equals the seed script's own ledger exactly (cents and count).
- **A6 Shape diff (12-02).** For every JSON path the adapter reads (`id`, `location_id`, `state`, `closed_at`, `line_items[].item_type`, `line_items[].catalog_object_id`, `line_items[].gross_sales_money.{amount,currency}`, `returns`, `cursor`, `locations[].{id,name,timezone,currency,coordinates}`), the recorded sandbox response and the generator output have the same presence and JSON type. 0 differences required.
- **Informational, not a gate:** full fixture pull time. The target is 15 s or less on this Mac (the spike measured 5.0 s for 110k orders).
- **Deviation rule:** any change to `params.json` after the first A1 run is logged with its reason in the phase report.

### Owner runbook: Square sandbox in 5 minutes (question 3)
Agents never create accounts. If the owner has no Square account, signing up is the owner's step.
1. Open https://developer.squareup.com/apps and sign in.
2. Create an application (the "+" / "Create your first application" tile). Name it `weather-insurance-pos` and save. Skip any optional survey.
3. Open the app. Switch the environment toggle at the top of the page to **Sandbox**.
4. In the left menu, open **Credentials** and copy the **Sandbox Access token** ("Show", then copy). Leave production credentials alone.
5. In Terminal, run `open -e ~/.config/dev/secrets.env` and add this line exactly, **with `export`**:
   `export SQUARE_SANDBOX_ACCESS_TOKEN=<paste>`
   Save and close. Without `export` the portal's dev server never sees it (checked on this machine: 5 of the 6 current lines lack `export`, and a clean shell does not pass them to child processes).
6. Optional: in the same app (Sandbox), open **Locations** to see the default location ID. You can skip this, because the adapter lists locations itself.
7. Optional: in the Developer Console open **Sandbox test accounts**, then the default test account, then open its **Sandbox Square Dashboard** to watch seeded orders appear. It must also be open in the same browser if we ever test OAuth in sandbox.
8. Tell the seat "Square token in." Nothing else: no OAuth setup, no webhooks, no production app review.

What happens next without the owner: 12-02 lists sandbox locations, creates up to 3 test locations (NYC / Chicago / Miami street addresses; Square fills `timezone` from the address), seeds K orders per location today, pulls the panel, and checks A5/A6. The public Vercel demo keeps showing fixture data until the token is also added to Vercel env (see Open Questions).

Location IDs without the console: `curl -s https://connect.squareupsandbox.com/v2/locations -H "Square-Version: 2026-09-16" -H "Authorization: Bearer $SQUARE_SANDBOX_ACCESS_TOKEN" | jq '.locations[] | {id,name,timezone}'`

### Auth: sandbox token now, OAuth later (question 4)
- **Now.** The Sandbox Access token belongs to the owner's default sandbox test account and has full access to it, like a personal access token (Square "Access tokens" doc: personal/sandbox tokens give "full access to the resources in a Square account and are generally used for testing").
  - Server-only env var. Never `NEXT_PUBLIC_`, never logged, never written into `recorded/`.
  - Route handlers use `export const runtime = "nodejs"`.
- **Later (real merchants).** Square says multi-seller production apps should use OAuth.
  - Use the **code flow**, since the server holds the client secret: authorize URL `https://connect.squareup.com/oauth2/authorize?client_id=...&scope=ORDERS_READ+MERCHANT_PROFILE_READ[+ITEMS_READ]&state=...`, then the callback with `code` (expires in 5 min), then `client.oAuth.obtainToken`.
  - Store `access_token` (expires after 30 days), `refresh_token` (code-flow refresh tokens do not expire; PKCE ones are single-use and expire after 90 days) and `merchant_id`, encrypted, in Upstash.
  - Refresh well before day 30. Revoke on disconnect.
  - Sandbox OAuth lives at `https://connect.squareupsandbox.com/oauth2`. It needs the Sandbox Square Dashboard open in another tab, and allows `http://localhost` redirects. Production redirects must be HTTPS.
- **What changes in code.** Only the factory: `squareSalesSource({ mode: "production", token: () => getMerchantToken(merchantId) })`. The SDK's `token` option accepts a supplier function, so refresh plugs in there. `SalesSource`, the aggregation, the panel and the fixtures do not change.
- **Scopes.** `ORDERS_READ` (SearchOrders) + `MERCHANT_PROFILE_READ` (ListLocations), plus `ITEMS_READ` only if the category column ships. `PAYMENTS_READ` is not needed.

### Shopify as the second adapter, later (question 6)
Use the GraphQL Admin API (currently versioned `2026-07`); REST Admin is legacy. The counterpart of SearchOrders is `orders(first: 250, after: $cursor, sortKey: PROCESSED_AT, query: "processed_at:>='…' processed_at:<'…' financial_status:paid")`, paged by `pageInfo { hasNextPage endCursor }`. Money comes as `MoneyBag` decimal **strings** (`currentSubtotalPriceSet.shopMoney.amount`), not integer minor units, so parse them to cents as strings. The time zone is shop-level (`shop { ianaTimezone }`), not per location, and POS orders carry `retailLocation`. Access: `read_orders` only covers orders from the last 60 days, so 400 days needs `read_all_orders`, which must be requested (Shopify access-scopes doc). Long histories should use `bulkOperationRunQuery` (JSONL). A daily aggregate shortcut exists as `shopifyqlQuery` (API 2025-10+, `read_reports`, e.g. `FROM sales SHOW total_sales TIMESERIES day SINCE -30d`). Rate limits are cost-based (calculated query cost with a leaky bucket; MEDIUM, from memory). It slots in as `kind: "shopify"` behind the same `SalesSource` interface, with the same metric table (Shopify "gross sales" must be mapped to the same exclusions).

### Anti-Patterns to Avoid
- **Bucketing by the UTC date** (`closed_at.slice(0,10)`). In the spike, a 23:59:59 ET order on 2025-11-01 has `closed_at = 2025-11-02T03:59:59.000Z` and would land on the wrong day, shifting every evening's sales into tomorrow's weather.
- **One query per local day with inclusive endpoints.** It double counts orders closed exactly at midnight and multiplies pages. Use Pattern 3.
- **`parseFloat(dollars)` then sum.** Sum integer cents. In the CSV path, parse "12.34" by string split, or `Math.round(x*100)` after a check that there are at most 2 decimals.
- **Falling back to fixtures when a present token fails (401).** That shows demo data as if it were live. A present token that fails is a hard error with a visible message.
- **Enumerating date ranges with local `Date` objects.** DST gives 23- and 25-hour days. Use UTC calendar math on `YYYY-MM-DD` strings.
- **Writing a general Square mock server.** Emulate exactly the three endpoints and the filter rules the adapter depends on.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP, retries on 429/5xx, `Retry-After`, bigint-safe JSON | a fetch wrapper with backoff | `square@46.0.0` (`maxRetries` per client/request) | Already handles 408/429/5xx with jitter, honors `Retry-After`, and parses integers to bigint |
| Time zones and DST | offset tables, "-5h" constants | `Intl.DateTimeFormat({ timeZone: Location.timezone })` | ICU handles DST and historical rules |
| Location time zone | a city-to-zone guess | `Location.timezone` from `client.locations.list()` (Square fills it from the address) | Authoritative per location |
| Category lookup | name-matching on `line_items[].name` | `client.catalog.list({ types: "ITEM,CATEGORY" })` plus variation-to-item mapping | Names change; ids do not |
| OAuth token exchange / refresh (later) | custom HTTP calls | `client.oAuth.obtainToken` | Correct grant types and error shapes |
| Webhook signatures (later) | custom HMAC | `WebhooksHelper.verifySignature` | Exact Square canonicalization |
| Money display | string concatenation | `Intl.NumberFormat("en-US", { style: "currency", currency: "USD" })` on cents/100 at render only | Keeps storage in integers |

**Key insight:** The hard parts of a POS adapter are not the HTTP calls. They are the day boundary, the metric definition and pagination completeness. Spend effort on the truth ledger and parity check, not on wrappers.

## Common Pitfalls

### Pitfall 1: The SDK silently targets Production or picks up a stray token
**What goes wrong:** With no `environment`/`baseUrl`, every call goes to `https://connect.squareup.com`. With no `token`, the SDK reads `process.env.SQUARE_TOKEN`.
**Why it happens:** Both defaults are in the generated client (`?? environments.SquareEnvironment.Production`; `ENV_TOKEN = "SQUARE_TOKEN"`).
**How to avoid:** Always pass `environment: SquareEnvironment.Sandbox` and an explicit `token` (a dummy string in fixture mode). Guard: sandbox mode throws unless the host is `connect.squareupsandbox.com`. Production mode does not exist until the OAuth work.
**Warning signs:** 401s mentioning production, or data appearing that the seed never created.

### Pitfall 2: Filter/sort mismatch on SearchOrders
**What goes wrong:** 400 errors, or unordered pages.
**Why:** A `closed_at` filter requires `sort_field: "CLOSED_AT"`, and `CLOSED_AT` sort requires a `state_filter` (COMPLETED and/or CANCELED).
**How to avoid:** Use the exact request in Code Examples. The fixture server enforces the same two rules, so a wrong request fails in fixture mode first.

### Pitfall 3: Cursor misuse
**What goes wrong:** Dropped or repeated pages.
**Why:** The cursor must be sent with the **identical** original query, and cursors expire after 5 minutes (Square pagination doc).
**How to avoid:** Build the request body once, including a fixed `endAt` (never recompute "now" per page), then loop on `cursor` until it is absent. Never stop early because a page came back short. Page each location sequentially.
**Warning signs:** `provenance.duplicates > 0`, or totals below the ledger in A1.

### Pitfall 4: bigint crashes the Next.js boundary
**What goes wrong:** `TypeError: Do not know how to serialize a BigInt` (reproduced).
**How to avoid:** Convert inside `aggregate.ts` with a safe-integer check. Never return raw SDK objects from route handlers or server actions.

### Pitfall 5: The SDK does not validate responses
**What goes wrong:** A fixture with `amount: "450"` (string) or a missing field passes straight through, and the fixture drifts from the real wire without anyone noticing.
**Why:** `parseOrThrow(..., { skipValidation: true })` in the generated client.
**How to avoid:** Coerce with `BigInt(x)` (it accepts number, string and bigint). Assert `currency`. Run the A6 shape diff against a recorded sandbox page in 12-02.

### Pitfall 6: Token pasted but never seen
**What goes wrong:** The owner pastes `SQUARE_SANDBOX_ACCESS_TOKEN=...` without `export`, and `next dev` never sees it. The portal stays on fixtures and looks "connected".
**How to avoid:** The runbook says `export`. The portal dev script is `set -a; . ~/.config/dev/secrets.env; set +a; next dev`, which works with either style. The mode badge is always visible. The route returns `mode` in every response.

### Pitfall 7: Tests flip to the sandbox once the token exists
**What goes wrong:** Fixture e2e tests start calling the network (or fail) after the owner pastes the token, because secrets are global.
**How to avoid:** Tests always pass `{ mode: "fixture" }` explicitly. Only the route handler resolves mode from env. A3 proves there is no network.

### Pitfall 8: COMPLETED-only undercounts some merchants and dates by completion time
**What goes wrong:** A paid order that has fulfillments (pickup/delivery) stays `OPEN` until the seller completes it, so it is missing, or it lands on the completion day rather than the payment day.
**Why:** Square auto-completes a paid order only if "the order doesn't include fulfillments" (Pay for Orders doc).
**How to avoid:** Prototype stays COMPLETED + `closed_at`. For real merchants, add a data-quality counter: `OPEN` orders in the window that carry tenders go into `provenance.openPaidOrders`, with a warning above 1 %. MEDIUM confidence that this matters for walk-in shops (it mostly hits online-ordering merchants).

### Pitfall 9: Late offline orders
**What goes wrong:** Square POS offline-mode orders may take up to 72 hours to reach Square (SearchOrders description), so the most recent days are low.
**How to avoid:** Set `provisionalFrom = today_local - 3 days` in sandbox/production. A daily refresh re-pulls the trailing 4 local days and replaces those rows. Fixture mode has no provisional days.

### Pitfall 10: Wrong things counted as sales
**What goes wrong:** Gift-card loads, tips, tax or return orders inflate or deflate gross sales. Return orders inflate the order count.
**How to avoid:** Follow the metric table exactly. The generator plants each case, and A4 checks the counts.

### Pitfall 11: Zero days differ between CSV and Square
**What goes wrong:** Square emits 0/0 rows for closed days, while CSV simply omits them (or the reverse), so the elasticity fit differs by source.
**How to avoid:** One rule in `validatePanel` and both sources: every date in `[start, end]` has a row, and missing CSV dates inside the uploaded span become explicit 0/0 rows, flagged in provenance. The estimator (Phase 5/10) decides whether to drop closure days. A2 enforces it.

### Pitfall 12: Null time zone or non-USD location
**What goes wrong:** Defaulting a null `Location.timezone` to UTC silently shifts days. Summing mixed currencies corrupts totals.
**How to avoid:** Reject the location with a visible reason. Never default.

### Pitfall 13: Expecting history in the sandbox
**What goes wrong:** The plan assumes 400 days of sandbox orders can be seeded.
**Why:** `created_at`/`closed_at` are read-only (Create Orders doc). Every seeded order closes "now".
**How to avoid:** The sandbox proves the wire and exactness on today's data (A5/A6). History in the demo is fixtures.

### Pitfall 14: Undocumented rate limits
**What goes wrong:** A large real backfill gets 429s mid-stream.
**Why:** Square documents no numbers ("dynamic rate limiting"). Its guidance is backoff with jitter.
**How to avoid:** Set `maxRetries: 5` for backfills and page each location sequentially. For real merchants later, chunk by month per location into Upstash with resume (a 400-day pull at 1,000 orders/page is roughly 100-250 requests). Not needed for sandbox or fixture.

### Pitfall 15: Sales day vs weather day
**What goes wrong:** Assuming the sales date and the Kalshi/NWS climate date are the same 24 hours.
**Why:** NWS daily climate values use local **standard** time, so during DST the climate day runs 01:00-01:00 local daylight time. MEDIUM confidence, from memory; Phase 1/7 own the weather side.
**How to avoid:** Bucket sales by local wall-clock date (what the owner sees in Square) and note the 1-hour offset in `docs/CONVENTIONS.md` via the seat. It does not matter for daily highs, which occur in the afternoon.

## Code Examples

All snippets below type-check against `square@46.0.0` with `tsc --strict --module nodenext`. The search/aggregate pattern and the fixture fetch were **run** in the research spike: 15/15 location-days exact across the DST change, 8 pages per location at limit 37, one planted 429 retried by the SDK, `amount` arriving as `bigint`.

### Client factory and mode
```typescript
// apps/portal/src/lib/sales/square/source.ts
import { SquareClient, SquareEnvironment } from "square";
import { fixtureFetch } from "./fixture-fetch";

export type SquareMode = { mode: "fixture" } | { mode: "sandbox"; token: string };

export function resolveSquareMode(env: Record<string, string | undefined> = process.env): SquareMode {
  const token = env.SQUARE_SANDBOX_ACCESS_TOKEN?.trim();
  return token ? { mode: "sandbox", token } : { mode: "fixture" };
}

export function squareClientFor(m: SquareMode): SquareClient {
  if (m.mode === "sandbox") {
    return new SquareClient({
      token: m.token,                            // explicit: never fall back to SQUARE_TOKEN
      environment: SquareEnvironment.Sandbox,    // explicit: SDK default is Production
      maxRetries: 5,
      timeoutInSeconds: 30,
    });
  }
  return new SquareClient({
    token: "fixture-not-a-token",
    environment: SquareEnvironment.Sandbox,      // only used as a URL prefix the fixture fetch matches on
    fetch: fixtureFetch,                         // serves generated Square-shaped responses; no network
  });
}
```

### SearchOrders with cursor pagination (one location)
```typescript
// apps/portal/src/lib/sales/square/search.ts
import type { SquareClient, Square } from "square";

export async function* completedOrders(
  client: SquareClient, squareLocationId: string, startAtUtc: string, endAtUtc: string,
): AsyncGenerator<Square.Order> {
  const base = {
    locationIds: [squareLocationId],
    query: {
      filter: {
        stateFilter: { states: ["COMPLETED"] as Square.OrderState[] },
        dateTimeFilter: { closedAt: { startAt: startAtUtc, endAt: endAtUtc } }, // fixed endAt, inclusive
      },
      sort: { sortField: "CLOSED_AT" as const, sortOrder: "ASC" as const },     // must match the filter field
    },
    limit: 1000,                                                                 // max; default 500
  };
  let cursor: string | undefined;
  do {
    const res = await client.orders.search({ ...base, cursor });                 // same body every page
    if (res.errors?.length) throw new Error(`SearchOrders: ${JSON.stringify(res.errors)}`);
    for (const o of res.orders ?? []) yield o;
    cursor = res.cursor ?? undefined;                                            // absent = last page
  } while (cursor);
}
```

### Aggregate to the panel (bucketing, bigint, exclusions)
```typescript
// apps/portal/src/lib/sales/square/aggregate.ts
import type { Square } from "square";
import type { DailySalesRow, LocalDate } from "../types";

export const localDateFn = (timeZone: string) => {
  const f = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" });
  return (iso: string) => f.format(new Date(iso)) as LocalDate;                  // "YYYY-MM-DD" in the location's zone
};
const big = (a: unknown) => (a == null ? 0n : BigInt(a as bigint | number | string)); // SDK skips validation
const safe = (b: bigint) => { const n = Number(b); if (!Number.isSafeInteger(n) || n < 0) throw new Error("cents out of range"); return n; };

export function aggregate(
  orders: Iterable<Square.Order>, loc: { id: string; squareId: string; timezone: string },
  dates: LocalDate[], prov: Record<string, number>, catOf?: (variationId?: string | null) => string,
): DailySalesRow[] {
  const day = localDateFn(loc.timezone);
  const acc = new Map<LocalDate, { c: bigint; n: number; cats: Map<string, bigint> }>();
  const seen = new Set<string>();
  for (const o of orders) {
    if (!o.id || seen.has(o.id)) { prov.duplicates = (prov.duplicates ?? 0) + 1; continue; }
    seen.add(o.id);
    if (o.state !== "COMPLETED" || !o.closedAt || o.locationId !== loc.squareId) { prov.skippedOther = (prov.skippedOther ?? 0) + 1; continue; }
    let c = 0n, counted = 0; const cats = new Map<string, bigint>();
    for (const li of o.lineItems ?? []) {
      if (li.itemType === "GIFT_CARD") { prov.giftCardLines = (prov.giftCardLines ?? 0) + 1; continue; }
      if (li.itemType === "CUSTOM_AMOUNT") prov.customAmountLines = (prov.customAmountLines ?? 0) + 1;
      const m = li.grossSalesMoney;
      if (m?.currency && m.currency !== "USD") throw new Error(`non-USD line on order ${o.id}`);
      const v = big(m?.amount); c += v; counted++;
      if (catOf) { const k = catOf(li.catalogObjectId); cats.set(k, (cats.get(k) ?? 0n) + v); }
    }
    if (counted === 0) { if (o.returns?.length) prov.returnOrders = (prov.returnOrders ?? 0) + 1; continue; }
    const d = day(o.closedAt);
    const a = acc.get(d) ?? { c: 0n, n: 0, cats: new Map() };
    a.c += c; a.n += 1; for (const [k, v] of cats) a.cats.set(k, (a.cats.get(k) ?? 0n) + v);
    acc.set(d, a);
  }
  return dates.map((date) => {                                                   // explicit 0/0 rows
    const a = acc.get(date);
    const row: DailySalesRow = { locationId: loc.id, date, grossSalesCents: a ? safe(a.c) : 0, orderCount: a?.n ?? 0 };
    if (catOf) row.categories = Object.fromEntries([...(a?.cats ?? [])].map(([k, v]) => [k, safe(v)]));
    return row;
  });
}
```

### Fixture fetch skeleton (the transport swap)
```typescript
// apps/portal/src/lib/sales/square/fixture-fetch.ts  — shape proven in the research spike
export const fixtureFetch: typeof fetch = async (input, init) => {
  const url = new URL(String(input));
  const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
  if (url.pathname === "/v2/locations") return json(200, LOCATIONS_JSON);
  if (url.pathname === "/v2/catalog/list") return json(200, catalogPage(url.searchParams.get("cursor")));
  if (url.pathname !== "/v2/orders/search" || init?.method !== "POST") return json(404, { errors: [{ code: "NOT_FOUND" }] });
  const body = JSON.parse(String(init.body));                     // snake_case wire body the SDK serialized
  // 1) enforce Square's rules: <=10 location_ids, CLOSED_AT sort with closed_at filter, state_filter with CLOSED_AT sort, limit<=1000
  // 2) cursor = base64url({ h: sha256(body minus cursor), o: offset }); mismatched h -> 400
  // 3) select generated orders: location_ids, states, start_at <= closed_at <= end_at (instants), sort, slice(offset, offset+limit)
  // 4) planted quirks: one 429 with Retry-After: 1; one short page before the end
  // 5) return json(200, next ? { orders: page, cursor: next } : { orders: page })
  return json(200, searchOrdersPage(body));
};
```

### Sandbox seeding (12-02; sandbox host only)
```typescript
// scripts/square/seed-sandbox.ts  (guard: refuse unless SquareEnvironment.Sandbox; count existing "wi-seed-" orders first)
import { randomUUID } from "node:crypto";
import { SquareClient, SquareEnvironment, Square } from "square";

const client = new SquareClient({ token: process.env.SQUARE_SANDBOX_ACCESS_TOKEN!, environment: SquareEnvironment.Sandbox, maxRetries: 5 });

export async function makeLocation(name: string, address: Square.Address) {
  return (await client.locations.create({ location: { name, address } })).location!; // timezone filled from address
}
export async function seedOne(locationId: string, i: number, cents: number) {
  const { order } = await client.orders.create({
    idempotencyKey: randomUUID(),
    order: { locationId, referenceId: `wi-seed-${i}`,
      lineItems: [{ name: "Seed cone", quantity: "1", basePriceMoney: { amount: BigInt(cents), currency: "USD" } }] },
  });
  await client.payments.create({                                  // no fulfillments + fully paid => COMPLETED
    sourceId: "cnon:card-nonce-ok", idempotencyKey: randomUUID(),
    amountMoney: { amount: order!.totalMoney!.amount!, currency: "USD" }, orderId: order!.id!, locationId, autocomplete: true,
  });
  return { id: order!.id!, cents };                               // seed ledger for A5
}
```

### Optional categories (ITEMS_READ)
```typescript
export async function categoryOf(client: SquareClient): Promise<(variationId?: string | null) => string> {
  const catName = new Map<string, string>(); const items: Array<[string[], string | undefined]> = [];
  for await (const obj of await client.catalog.list({ types: "ITEM,CATEGORY" })) {    // paged iterator
    if (obj.type === "CATEGORY" && obj.id) catName.set(obj.id, obj.categoryData?.name ?? obj.id);
    if (obj.type === "ITEM") items.push([(obj.itemData?.variations ?? []).flatMap((v) => (v.id ? [v.id] : [])),
      obj.itemData?.reportingCategory?.id ?? obj.itemData?.categories?.[0]?.id ?? undefined]);
  }
  const map = new Map<string, string>();
  for (const [vars, cat] of items) for (const v of vars) map.set(v, (cat && catName.get(cat)) || "Uncategorized");
  return (v) => (v && map.get(v)) || "Uncategorized";                             // deleted/custom -> Uncategorized
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `import { Client } from "square"`, `new Client({ bearerAuthCredentials: { accessToken } })`, `client.ordersApi.searchOrders(...)`, `result.orders` | `import { SquareClient } from "square"`, `new SquareClient({ token, environment })`, `await client.orders.search(...)` returns the response data directly (camelCase, bigint money) | v40.0.0, 2025-01-22 (Fern rewrite); now v46.0.0 | Old tutorials and model memory show the legacy API. The legacy client still ships as `square/legacy` (bundled `square@^39.1.1`), but do not use it |
| `CatalogItem.category_id` | `CatalogItem.categories[]` + `reporting_category` | deprecated 2023-12-13 | Category mapping uses `reportingCategory` first |
| Stitching Orders/Payments/Refunds for reports | Reporting API (`/v1/meta`, `/v1/load`) | open beta announced 2026-04-23 | Future path for real merchants' daily totals; production base URL only in docs |
| Shopify REST Admin `orders.json` | GraphQL Admin `orders` connection; `shopifyqlQuery` for aggregates | ShopifyQL in GraphQL Admin since API 2025-10 | Second adapter should be GraphQL-only |

**Deprecated/outdated:**
- `square-connect` npm package (pre-2020 SDK): do not use (LOW, from memory; irrelevant if we pin `square@46.0.0`).
- `square/legacy` import path: exists only for migration.

## Open Questions

1. **Can the seat seed the sandbox without pinging the owner?**
   - What we know: `.planning/config.json` has `always_confirm_external_services: true`. Seeding writes test orders and up to 3 locations into the owner's sandbox (no accounts, no keys, no money). 12-02 already names "verification against a seeded sandbox seller".
   - Recommendation: the seat runs `seed-sandbox.ts` after the token lands (sandbox-host guard, idempotent via `reference_id` prefix count) and sends one push notice. If the seat reads the config as needing an explicit OK, it asks in the same push as "token received".
2. **Hosted demo on sandbox data?**
   - What we know: the token lives on this Mac. The public Vercel demo (Phase 13) needs `vercel env add SQUARE_SANDBOX_ACCESS_TOKEN` to flip.
   - Recommendation: the hosted demo stays on fixtures (the badge says so). Flip it only with an owner OK, since it puts a credential into an external service.
3. **CSV format and zero-day rule belong to Phase 10.** This research proposes the shared types, the metric table and the zero-row rule. The 10-02 plan must adopt or amend them, then `csv-export.csv` is generated in that format.
4. **Temperature input for the generator.** Depends on Phase 1 plan 01-03's IEM table existing when 12-01 runs. There is a synthetic fallback (flagged in the manifest).
5. **Portal path.** `apps/portal/` is assumed. Phase 10's scaffold decides.
6. **Dashboard parity on gift cards / exchanges (LOW).** Our definition is explicit, but whether Square Dashboard "Gross sales" matches it exactly on gift cards and exchanges was not verified. It only matters if a real merchant compares numbers.
7. **Reporting API in sandbox.** Unconfirmed. Irrelevant to this phase; revisit for real merchants.

## Sources

### Primary (HIGH confidence)
- npm registry: `npm view square` gives latest 46.0.0 (2026-09-15) and the full release timeline (40.0.0 on 2025-01-22, etc.)
- `square@46.0.0` package source (unpacked locally): `README.md` (usage, legacy, environments, pagination, retries, runtime compatibility), `reference.md` (orders.search, reporting), `environments.d.ts` (Sandbox `https://connect.squareupsandbox.com`), `BaseClient.d.ts` (`fetch` option, `version: "2026-09-16"`), `api/resources/orders/client/Client.js` (Production default, `skipValidation: true`), `auth/BearerAuthProvider.js` (`SQUARE_TOKEN` fallback), `core/fetcher/requestWithRetries.js` (408/429/5xx, Retry-After, default 2), `api/types/*` (SearchOrdersRequest limits, Order, OrderLineItem, Money, Location, OrderReturn)
- Research spikes on this Mac (scratchpad, not committed): offline SDK + fixture fetch across DST 2025-11-02 (15/15 exact, 429 retried, bigint amounts, `JSON.stringify(bigint)` throws); 110k-order throughput (5.0 s, 213 MB); `tsc --strict` on every snippet above
- https://developer.squareup.com/reference/square/orders-api/search-orders — endpoint, `ORDERS_READ`, max 10 location ids, limit default 500 / max 1000, example body, API version 2026-09-16
- https://developer.squareup.com/docs/orders-api/manage-orders/search-orders — sort must match the date filter; `CLOSED_AT` sort requires a state filter
- https://developer.squareup.com/docs/build-basics/common-api-patterns/pagination — reuse the original query; cursor lifetime 5 minutes
- https://developer.squareup.com/docs/build-basics/working-with-monetary-amounts — smallest-denomination integers; floats rejected
- https://developer.squareup.com/docs/build-basics/general-considerations/handling-errors — 429 `RATE_LIMITED`, exponential backoff with jitter
- https://developer.squareup.com/docs/devtools/sandbox/overview — sandbox base URL, default test account, Sandbox Access token on Credentials, limited Sandbox Dashboard
- https://developer.squareup.com/docs/devtools/sandbox/payments — `cnon:card-nonce-ok` and other test source ids
- https://developer.squareup.com/docs/orders-api/create-orders — `created_at`/`closed_at` read-only; Dashboard visibility needs fulfillment + paid
- https://developer.squareup.com/docs/orders-api/pay-for-orders — auto-COMPLETED only when fully paid and no fulfillments
- https://developer.squareup.com/reference/square/objects/Order and https://developer.squareup.com/reference/square/objects/Location — field semantics; `timezone`/`coordinates` writable, `currency` read-only
- https://developer.squareup.com/reference/square/locations-api/create-location — `MERCHANT_PROFILE_WRITE`; timezone filled from address
- https://developer.squareup.com/docs/locations-api — location IDs in Developer Console > app > Locations; up to 300 locations
- https://developer.squareup.com/docs/build-basics/access-tokens — personal/sandbox tokens full access; OAuth for multi-seller production
- https://developer.squareup.com/docs/oauth-api/overview — code vs PKCE flows, 30-day access tokens, refresh-token lifetimes, sandbox OAuth caveats
- https://developer.squareup.com/docs/oauth-api/square-permissions — `ORDERS_READ`, `MERCHANT_PROFILE_READ`, `ITEMS_READ`, `PAYMENTS_READ` mapping
- https://developer.squareup.com/reference/square/payments-api/list-payments — `created_at` filter, max 100 per page, one location
- https://shopify.dev/docs/api/admin-graphql/latest/queries/orders — orders connection, filter syntax, version 2026-07
- https://shopify.dev/docs/api/usage/access-scopes — `read_orders` 60-day window, `read_all_orders` by request, `read_reports`

### Secondary (MEDIUM confidence)
- https://developer.squareup.com/docs/reporting-api/overview and https://developer.squareup.com/docs/reporting-api/getting-started — Reporting API shape, `REPORTING_READ`, production base URL
- https://developer.squareup.com/forums/t/reporting-api-open-beta/25897 — open beta 2026-04-23, "field names or schemas may evolve"
- https://developer.squareup.com/forums/t/enable-custom-reports-on-sandbox/27313 — custom reports production-only (staff, 2026-08-25)
- https://developer.squareup.com/docs/orders-api/order-returns-exchanges (via search summary) — returns as separate linked orders; exchanges carry both
- https://developer.squareup.com/forums/t/create-order-via-ui-on-the-sandbox-account-dashboard/10148 — Sandbox Dashboard "Create Order" button (2023), no fulfillments
- https://shopify.dev/changelog/shopifyqlquery-now-available-in-graphql-admin-api — `shopifyqlQuery` from API 2025-10
- https://github.com/square/square-nodejs-sdk/blob/master/tests/wire/orders.test.ts — wire (snake_case) request/response shape used by the SDK's own tests

### Tertiary (LOW confidence, flagged for validation)
- Developer Console exact button labels ("Create your first application", environment toggle placement): wording can drift; the owner follows what the page shows
- Square Dashboard "Gross sales" excluding gift-card loads
- NWS climate day in local standard time (Pitfall 15); Shopify cost-based rate limits; `square-connect` deprecation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH. Version from the npm registry, behavior read from the package source and exercised offline.
- Architecture (interface, injected transport, bucketing, fixture/ledger design): HIGH for the mechanics (the spike ran them). MEDIUM for fixture parameter realism (chosen, not measured from real merchants).
- Pitfalls: HIGH for 1-7, 9, 12-14 (docs or code verified). MEDIUM for 8 and 11. MEDIUM/LOW for 15.
- Runbook: MEDIUM. The steps come from Square docs, but the UI labels may differ slightly.
- Shopify: MEDIUM.

**Research date:** 2026-09-30
**Valid until:** 2026-10-30 for the Square API/SDK (the SDK ships monthly, so pin 46.0.0). Re-check the Reporting API beta and Shopify versions before any second-adapter work.
