// Deterministic Square-shaped order generator + truth ledger.
//
// The truth ledger (TruthDay) is accumulated inside the local-date loop from the prices drawn,
// BEFORE any local-to-UTC conversion. The adapter only ever sees UTC closed_at, pages, cursors,
// order states and wire money, so its totals match the ledger only if bucketing, DST, pagination,
// state filtering, bigint money and the gift-card / return exclusions are all correct.
//
// No Math.random, no Date.now(). Per-(location, date) sub-seed = first 4 bytes of
// sha256("seed|locationId|date") fed to mulberry32: changing one day reshuffles nothing else.
import { createHash } from "node:crypto";
import { addDays, dayIndex } from "../dates";

// ---------- params (written to fixtures/square/params.json, read back by the fixture fetch) ----------

export interface ItemParams { name: string; category: string; price_cents: number }
export interface LocationParams {
  id: string; // Square location id, e.g. LFIXNYC000001
  key: string; // short key used in ids: NYC, CHI, MIA
  name: string;
  business: string;
  timezone: string;
  lat: number;
  lon: number;
  postal_code: string;
  address_line_1: string;
  locality: string;
  state: string;
  station: string; // station-tmax.csv station code
  base: number; // orders/day
  amp: number; // seasonal amplitude
  beta: number; // per degF over tref
  tref: number;
  tax_rate: number;
  items: ItemParams[]; // 9 items, 3 categories
  closed_ranges: Array<[string, string]>; // inclusive local dates
}
export interface Params {
  generator_version: number;
  seed: number;
  square_version: string;
  window: { start: string; end: string };
  dow_sun0: number[]; // multiplier by weekday, Sunday = 0
  holidays: Record<string, number>; // local date -> demand multiplier
  closed_all: string[]; // local dates every location is closed
  ambiguous_date: string; // DST-end date: orders planted in the repeated 01:30 hour
  noise: {
    open: number; canceled: number; returns: number;
    gift_only: number; gift_line: number; custom_amount: number;
    tip_prob: number; discount_prob: number;
  };
  line_count_p: number[]; // P(1,2,3 lines)
  qty2_p: number;
  locations: LocationParams[];
}

const items = (cats: [string, string, string], rows: Array<[string, number]>): ItemParams[] =>
  rows.map(([name, price_cents], i) => ({ name, category: cats[Math.floor(i / 3)], price_cents }));

export const DEFAULT_PARAMS: Params = {
  generator_version: 1,
  seed: 20260930,
  square_version: "2026-09-16",
  window: { start: "2025-08-27", end: "2026-09-30" },
  dow_sun0: [1.25, 0.85, 0.88, 0.92, 0.98, 1.12, 1.35],
  holidays: { "2026-01-01": 0.6, "2026-07-04": 1.3, "2025-12-24": 0.7 },
  closed_all: ["2025-11-27", "2025-12-25"],
  ambiguous_date: "2025-11-02",
  noise: { open: 0.01, canceled: 0.005, returns: 0.004, gift_only: 0.0015, gift_line: 0.0015, custom_amount: 0.02, tip_prob: 0.35, discount_prob: 0.1 },
  line_count_p: [0.55, 0.33, 0.12],
  qty2_p: 0.3,
  locations: [
    {
      id: "LFIXNYC000001", key: "NYC", name: "Fixture Scoops Midtown", business: "ice cream + coffee",
      timezone: "America/New_York", lat: 40.7648, lon: -73.9808, postal_code: "10019",
      address_line_1: "1 Fixture Ave", locality: "New York", state: "NY", station: "NYC",
      base: 95, amp: 0.2, beta: 0.012, tref: 70, tax_rate: 0.08875, closed_ranges: [],
      items: items(["Scoops", "Coffee", "Extras"], [
        ["Single scoop", 475], ["Double scoop", 675], ["Sundae", 975],
        ["Drip coffee", 375], ["Latte", 575], ["Iced coffee", 525],
        ["Affogato", 825], ["Cookie", 395], ["Milkshake", 925],
      ]),
    },
    {
      id: "LFIXCHI000002", key: "CHI", name: "Fixture Bakehouse Midway", business: "coffee + bakery",
      timezone: "America/Chicago", lat: 41.7868, lon: -87.7522, postal_code: "60629",
      address_line_1: "2 Fixture St", locality: "Chicago", state: "IL", station: "MDW",
      base: 80, amp: 0.1, beta: -0.006, tref: 60, tax_rate: 0.1025, closed_ranges: [["2026-02-09", "2026-02-13"]],
      items: items(["Coffee", "Bakery", "Breakfast"], [
        ["Drip coffee", 375], ["Latte", 550], ["Cold brew", 525],
        ["Croissant", 450], ["Muffin", 425], ["Scone", 475],
        ["Egg sandwich", 875], ["Bagel", 525], ["Breakfast burrito", 975],
      ]),
    },
    {
      id: "LFIXMIA000003", key: "MIA", name: "Fixture Juice Bar Miami", business: "juice + cafe",
      timezone: "America/New_York", lat: 25.7959, lon: -80.287, postal_code: "33126",
      address_line_1: "3 Fixture Blvd", locality: "Miami", state: "FL", station: "MIA",
      base: 85, amp: 0.05, beta: -0.004, tref: 84, tax_rate: 0.07, closed_ranges: [],
      items: items(["Juice", "Cafe", "Smoothie"], [
        ["Orange juice", 600], ["Green juice", 850], ["Acai bowl", 975],
        ["Cortadito", 375], ["Cafe con leche", 475], ["Empanada", 525],
        ["Mango smoothie", 750], ["Berry smoothie", 775], ["Protein smoothie", 925],
      ]),
    },
  ],
};

// ---------- deterministic randomness ----------

export function mulberry32(a: number): () => number {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const sha = (s: string) => createHash("sha256").update(s).digest();
const subSeed = (seed: number, loc: string, date: string) => sha(`${seed}|${loc}|${date}`).readUInt32BE(0);

const B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
/** 27-char base62 id from sha256(locationId|date|i): same length as real Square order ids. */
export function orderId(loc: string, date: string, i: number): string {
  let n = BigInt("0x" + sha(`${loc}|${date}|${i}`).subarray(0, 20).toString("hex"));
  let out = "";
  const base = BigInt(62);
  while (n > BigInt(0)) { out = B62[Number(n % base)] + out; n /= base; }
  return out.padStart(27, "0");
}

function knuth(rng: () => number, lam: number): number {
  const L = Math.exp(-lam);
  let k = 0, p = 1;
  do { k++; p *= rng(); } while (p > L);
  return k - 1;
}
function poisson(rng: () => number, lam: number): number {
  let n = 0;
  while (lam > 30) { n += knuth(rng, 30); lam -= 30; }
  return n + (lam > 0 ? knuth(rng, lam) : 0);
}

// ---------- local wall-clock -> UTC, independent of the adapter's bucketing ----------

const fmtCache = new Map<string, Intl.DateTimeFormat>();
function wallMs(tz: string, utcMs: number): number {
  let f = fmtCache.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
    fmtCache.set(tz, f);
  }
  const g: Record<string, number> = {};
  for (const p of f.formatToParts(new Date(utcMs))) if (p.type !== "literal") g[p.type] = +p.value;
  const ms = ((utcMs % 1000) + 1000) % 1000;
  return Date.UTC(g.year, g.month - 1, g.day, g.hour, g.minute, g.second, ms);
}
/** All UTC instants whose wall clock in `tz` equals `naiveMs` (read as UTC fields). 0 in a gap, 2 in a repeated hour. */
export function localToUtcCandidates(tz: string, naiveMs: number): number[] {
  const out = new Set<number>();
  for (const probe of [naiveMs - 86_400_000, naiveMs + 86_400_000]) {
    const off = wallMs(tz, probe) - probe;
    const cand = naiveMs - off;
    if (wallMs(tz, cand) === naiveMs) out.add(cand);
  }
  return [...out].sort((a, b) => a - b);
}
const dateMs = (d: string) => dayIndex(d) * 86_400_000;

// ---------- wire shapes (snake_case, exactly as Square sends them; money amounts are JSON numbers) ----------

export interface WireMoney { amount: number; currency: "USD" }
export interface WireLine {
  uid: string; catalog_object_id?: string; name: string; variation_name?: string; quantity: string;
  item_type: "ITEM" | "CUSTOM_AMOUNT" | "GIFT_CARD";
  base_price_money: WireMoney; gross_sales_money: WireMoney; total_money: WireMoney;
}
export interface WireOrder {
  id: string; location_id: string; created_at: string; updated_at: string; closed_at?: string;
  state: "OPEN" | "COMPLETED" | "CANCELED";
  version: number; source: { name: string };
  line_items?: WireLine[];
  returns?: Array<{ uid: string; source_order_id: string; return_line_items: Array<{ uid: string; name: string; quantity: string; gross_return_money: WireMoney }> }>;
  total_money: WireMoney; total_tax_money: WireMoney; total_tip_money: WireMoney; total_discount_money: WireMoney;
}
const usd = (amount: number): WireMoney => ({ amount, currency: "USD" });

export interface Planted {
  saleOrders: number; open: number; canceled: number; returnOrders: number;
  giftCardLines: number; giftCardOnlyOrders: number; customAmountLines: number;
  edgeTimeOrders: number; ambiguousHourOrders: number;
}
export const zeroPlanted = (): Planted => ({ saleOrders: 0, open: 0, canceled: 0, returnOrders: 0, giftCardLines: 0, giftCardOnlyOrders: 0, customAmountLines: 0, edgeTimeOrders: 0, ambiguousHourOrders: 0 });
export interface TruthDay { gross: number; count: number; cats: Record<string, number> }

const HOUR_W = [0, 0, 0, 0, 0, 0, 0, 2, 4, 5, 4, 3, 3, 4, 4, 3, 3, 3, 3, 2, 1, 1, 0, 0]; // hours 7..21 carry traffic

function isClosed(p: Params, loc: LocationParams, date: string): boolean {
  if (p.closed_all.includes(date)) return true;
  return loc.closed_ranges.some(([a, b]) => date >= a && date <= b);
}

export interface DayResult { orders: WireOrder[]; truth: TruthDay; planted: Planted; closed: boolean; lambda: number }

export function generateDay(p: Params, loc: LocationParams, date: string, tmaxF: number): DayResult {
  const truth: TruthDay = { gross: 0, count: 0, cats: {} };
  const planted = zeroPlanted();
  if (isClosed(p, loc, date)) return { orders: [], truth, planted, closed: true, lambda: 0 };

  const rng = mulberry32(subSeed(p.seed, loc.id, date));
  const dow = new Date(dateMs(date)).getUTCDay();
  const year = date.slice(0, 4);
  const doy = dayIndex(date) - dayIndex(`${year}-01-01`) + 1;
  const lambda =
    loc.base * p.dow_sun0[dow] * (1 + loc.amp * Math.sin((2 * Math.PI * (doy - 110)) / 365)) *
    Math.exp(loc.beta * (tmaxF - loc.tref)) * (p.holidays[date] ?? 1);
  // floor of 8 so the planted edge/ambiguous-hour orders always exist
  const n = Math.max(8, poisson(rng, lambda));

  const catalog = loc.items;
  const itemIdx = (k: number) => k + 1;
  const varId = (k: number) => `VAR${loc.key}${String(itemIdx(k)).padStart(4, "0")}`;
  let seq = 0;
  const orders: WireOrder[] = [];

  const pickTime = (): number => {
    const tot = HOUR_W.reduce((a, b) => a + b, 0);
    let r = rng() * tot, h = 7;
    for (let i = 0; i < 24; i++) { r -= HOUR_W[i]; if (r < 0) { h = i; break; } }
    return h * 3_600_000 + Math.floor(rng() * 3_600_000);
  };
  const toUtc = (ms: number, fold: 0 | 1 = 0): number => {
    let c = localToUtcCandidates(loc.timezone, dateMs(date) + ms);
    if (c.length === 0) c = localToUtcCandidates(loc.timezone, dateMs(date) + ms + 3_600_000); // skipped hour: push past the gap
    if (c.length === 0) throw new Error(`no UTC instant for ${loc.id} ${date} +${ms}`);
    return fold === 1 ? c[c.length - 1] : c[0];
  };
  const base = (id: string, state: WireOrder["state"], utcMs: number): WireOrder => {
    const closed = new Date(utcMs).toISOString();
    const created = new Date(utcMs - (60 + Math.floor(rng() * 240)) * 1000).toISOString();
    const o: WireOrder = {
      id, location_id: loc.id, created_at: created, updated_at: closed, state, version: 4, source: { name: "Square POS" },
      total_money: usd(0), total_tax_money: usd(0), total_tip_money: usd(0), total_discount_money: usd(0),
    };
    if (state !== "OPEN") o.closed_at = closed;
    return o;
  };
  const money = (o: WireOrder, gross: number) => {
    const disc = rng() < p.noise.discount_prob ? Math.round(gross * 0.1) : 0;
    const tax = Math.round((gross - disc) * loc.tax_rate);
    const tip = rng() < p.noise.tip_prob ? Math.round((gross - disc) * (0.1 + 0.05 * Math.floor(rng() * 4))) : 0;
    o.total_discount_money = usd(disc); o.total_tax_money = usd(tax); o.total_tip_money = usd(tip);
    o.total_money = usd(gross - disc + tax);
  };
  const itemLine = (oid: string, li: number): { line: WireLine; cents: number; cat: string } => {
    const k = Math.floor(rng() * catalog.length);
    const it = catalog[k];
    const qty = rng() < p.qty2_p ? 2 : 1;
    const gross = it.price_cents * qty;
    return {
      cents: gross, cat: it.category,
      line: { uid: `${oid.slice(0, 8)}${li}`, catalog_object_id: varId(k), name: it.name, variation_name: "Regular", quantity: String(qty), item_type: "ITEM",
        base_price_money: usd(it.price_cents), gross_sales_money: usd(gross), total_money: usd(gross) },
    };
  };

  // --- counted sale orders ---
  for (let i = 0; i < n; i++) {
    const id = orderId(loc.id, date, seq++);
    let ms: number, fold: 0 | 1 = 0;
    if (i === 0) { ms = 0; planted.edgeTimeOrders++; }
    else if (i === 1) { ms = 86_399_999; planted.edgeTimeOrders++; }
    else if (date === p.ambiguous_date && i >= 2 && i <= 5) { ms = 5_400_000; fold = i >= 4 ? 1 : 0; planted.ambiguousHourOrders++; }
    else ms = pickTime();
    const o = base(id, "COMPLETED", toUtc(ms, fold));
    const r = rng();
    const nl = r < p.line_count_p[0] ? 1 : r < p.line_count_p[0] + p.line_count_p[1] ? 2 : 3;
    const lines: WireLine[] = [];
    let gross = 0;
    for (let l = 0; l < nl; l++) {
      if (rng() < p.noise.custom_amount) {
        const c = 300 + Math.floor(rng() * 2200);
        lines.push({ uid: `${id.slice(0, 8)}${l}`, name: "Custom Amount", quantity: "1", item_type: "CUSTOM_AMOUNT", base_price_money: usd(c), gross_sales_money: usd(c), total_money: usd(c) });
        gross += c; truth.cats.Uncategorized = (truth.cats.Uncategorized ?? 0) + c; planted.customAmountLines++;
      } else {
        const { line, cents, cat } = itemLine(id, l);
        lines.push(line); gross += cents; truth.cats[cat] = (truth.cats[cat] ?? 0) + cents;
      }
    }
    if (rng() < p.noise.gift_line) {
      const c = rng() < 0.5 ? 2500 : 5000;
      lines.push({ uid: `${id.slice(0, 8)}g`, name: "Gift card", quantity: "1", item_type: "GIFT_CARD", base_price_money: usd(c), gross_sales_money: usd(c), total_money: usd(c) });
      planted.giftCardLines++; // not in truth
    }
    o.line_items = lines;
    money(o, gross + lines.filter((x) => x.item_type === "GIFT_CARD").reduce((a, x) => a + x.gross_sales_money.amount, 0));
    truth.gross += gross; truth.count++; planted.saleOrders++;
    orders.push(o);
  }
  const srcOrderId = orders[0].id;

  // --- planted non-sales noise ---
  for (const [state, rate] of [["OPEN", p.noise.open], ["CANCELED", p.noise.canceled]] as const) {
    const c = poisson(rng, n * rate);
    for (let j = 0; j < c; j++) {
      const id = orderId(loc.id, date, seq++);
      const o = base(id, state, toUtc(pickTime()));
      const { line, cents } = itemLine(id, 0);
      o.line_items = [line]; money(o, cents);
      orders.push(o);
      if (state === "OPEN") planted.open++; else planted.canceled++;
    }
  }
  const nret = poisson(rng, n * p.noise.returns);
  for (let j = 0; j < nret; j++) {
    const id = orderId(loc.id, date, seq++);
    const o = base(id, "COMPLETED", toUtc(pickTime()));
    const k = Math.floor(rng() * catalog.length);
    o.returns = [{ uid: `${id.slice(0, 8)}r`, source_order_id: srcOrderId,
      return_line_items: [{ uid: `${id.slice(0, 8)}ri`, name: catalog[k].name, quantity: "1", gross_return_money: usd(catalog[k].price_cents) }] }];
    o.total_money = usd(-catalog[k].price_cents);
    orders.push(o); planted.returnOrders++;
  }
  const ngift = poisson(rng, n * p.noise.gift_only);
  for (let j = 0; j < ngift; j++) {
    const id = orderId(loc.id, date, seq++);
    const o = base(id, "COMPLETED", toUtc(pickTime()));
    const c = rng() < 0.5 ? 2500 : 5000;
    o.line_items = [{ uid: `${id.slice(0, 8)}g`, name: "Gift card", quantity: "1", item_type: "GIFT_CARD", base_price_money: usd(c), gross_sales_money: usd(c), total_money: usd(c) }];
    o.total_money = usd(c);
    orders.push(o); planted.giftCardOnlyOrders++; planted.giftCardLines++;
  }
  return { orders, truth, planted, closed: false, lambda };
}

// ---------- static wire pieces (locations, catalog) ----------

export function buildLocationsWire(p: Params) {
  return {
    locations: p.locations.map((l) => ({
      id: l.id, name: l.name, business_name: l.name,
      address: { address_line_1: l.address_line_1, locality: l.locality, administrative_district_level_1: l.state, postal_code: l.postal_code, country: "US" },
      timezone: l.timezone, capabilities: ["CREDIT_CARD_PROCESSING"], status: "ACTIVE", country: "US", language_code: "en-US", currency: "USD",
      merchant_id: "MLFIXTURE000001", type: "PHYSICAL", coordinates: { latitude: l.lat, longitude: l.lon },
    })),
  };
}

/** Catalog as two ListCatalog wire pages (cursor between pages). */
export function buildCatalogWire(p: Params): { objects: unknown[]; cursor?: string }[] {
  const objs: unknown[] = [];
  for (const l of p.locations) {
    const cats = [...new Set(l.items.map((i) => i.category))];
    const catId = (c: string) => `CAT${l.key}${String(cats.indexOf(c) + 1).padStart(4, "0")}`;
    for (const c of cats) objs.push({ type: "CATEGORY", id: catId(c), category_data: { name: c } });
    l.items.forEach((it, k) => {
      const n = String(k + 1).padStart(4, "0");
      objs.push({
        type: "ITEM", id: `ITEM${l.key}${n}`,
        item_data: {
          name: it.name, reporting_category: { id: catId(it.category) }, categories: [{ id: catId(it.category) }],
          variations: [{ type: "ITEM_VARIATION", id: `VAR${l.key}${n}`, item_variation_data: { item_id: `ITEM${l.key}${n}`, name: "Regular", pricing_type: "FIXED_PRICING", price_money: { amount: it.price_cents, currency: "USD" } } }],
        },
      });
    });
  }
  const half = Math.ceil(objs.length / 2);
  return [{ objects: objs.slice(0, half), cursor: "CATALOGPAGE2" }, { objects: objs.slice(half) }];
}

export const localDatesOfWindow = (p: Params) => {
  const out: string[] = [];
  const n = dayIndex(p.window.end) - dayIndex(p.window.start);
  for (let i = 0; i <= n; i++) out.push(addDays(p.window.start, i));
  return out;
};
