// Pure: Square orders + one location -> explicit daily rows (+ provenance counters).
// Sums integer cents as bigint; converts to number once, with a safe-integer check, at the boundary.
import type { Square } from "square";
import { localDateFn } from "../dates";
import type { DailySalesRow, LocalDate } from "../types";

export interface AggLocation { id: string; squareId: string; timezone: string }
export type Prov = Record<string, number>;

export const PROV_KEYS = [
  "pages", "ordersSeen", "duplicates", "nonCompletedSeen", "otherLocationSeen",
  "returnOrders", "giftCardLines", "customAmountLines", "noSaleLineOrders", "outsideRange",
] as const;
export const newProv = (): Prov => Object.fromEntries(PROV_KEYS.map((k) => [k, 0]));

const ZERO = BigInt(0);
// The SDK skips response validation, so coerce instead of trusting the type.
const big = (a: unknown): bigint => (a == null ? ZERO : BigInt(a as bigint | number | string));
const safe = (b: bigint): number => {
  const n = Number(b);
  if (!Number.isSafeInteger(n) || n < 0) throw new Error("cents out of range");
  return n;
};
const inc = (p: Prov, k: string) => { p[k] = (p[k] ?? 0) + 1; };

export function aggregate(
  orders: Iterable<Square.Order>,
  loc: AggLocation,
  dates: LocalDate[],
  prov: Prov,
  catOf?: (variationId?: string | null) => string,
): DailySalesRow[] {
  const day = localDateFn(loc.timezone);
  const want = new Set<string>(dates);
  const acc = new Map<string, { c: bigint; n: number; cats: Map<string, bigint> }>();
  const seen = new Set<string>();
  for (const o of orders) {
    inc(prov, "ordersSeen");
    if (!o.id || seen.has(o.id)) { inc(prov, "duplicates"); continue; }
    seen.add(o.id);
    if (o.state !== "COMPLETED") { inc(prov, "nonCompletedSeen"); continue; }
    if (o.locationId !== loc.squareId) { inc(prov, "otherLocationSeen"); continue; }
    if (!o.closedAt) { inc(prov, "nonCompletedSeen"); continue; }
    let cents = ZERO, counted = 0;
    const cats = new Map<string, bigint>();
    for (const li of o.lineItems ?? []) {
      if (li.itemType === "GIFT_CARD") { inc(prov, "giftCardLines"); continue; }
      if (li.itemType === "CUSTOM_AMOUNT") inc(prov, "customAmountLines");
      const m = li.grossSalesMoney;
      if (m?.currency && m.currency !== "USD") throw new Error(`non-USD line on order ${o.id}`);
      const v = big(m?.amount);
      cents += v; counted++;
      if (catOf) { const k = catOf(li.catalogObjectId); cats.set(k, (cats.get(k) ?? ZERO) + v); }
    }
    if (counted === 0) {
      if (o.returns?.length) inc(prov, "returnOrders"); else inc(prov, "noSaleLineOrders");
      continue;
    }
    const d = day(o.closedAt);
    if (!want.has(d)) { inc(prov, "outsideRange"); continue; }
    const a = acc.get(d) ?? { c: ZERO, n: 0, cats: new Map<string, bigint>() };
    a.c += cents; a.n += 1;
    for (const [k, v] of cats) a.cats.set(k, (a.cats.get(k) ?? ZERO) + v);
    acc.set(d, a);
  }
  return dates.map((date) => {
    const a = acc.get(date);
    const row: DailySalesRow = { locationId: loc.id, date, grossSalesCents: a ? safe(a.c) : 0, orderCount: a?.n ?? 0 };
    if (catOf) row.categories = Object.fromEntries([...(a?.cats ?? [])].filter(([, v]) => v > ZERO).map(([k, v]) => [k, safe(v)]));
    return row;
  });
}
