import { dayIndex, enumerateDates, isLocalDate } from "./dates";
import type { SalesPanel } from "./types";

const isCents = (n: unknown): n is number => typeof n === "number" && Number.isSafeInteger(n) && n >= 0;

/** Panel invariants every source must satisfy before returning. [] = valid. */
export function validatePanel(p: SalesPanel): string[] {
  const errs: string[] = [];
  if (!isLocalDate(p.start) || !isLocalDate(p.end)) return ["start/end must be YYYY-MM-DD"];
  if (dayIndex(p.end) < dayIndex(p.start)) return ["end before start"];
  if (!/^\d{4}-\d{2}-\d{2}T[\d:.]+Z$/.test(p.pulledAt)) errs.push("pulledAt must be UTC ISO-8601 with Z");
  const locIds = new Set<string>();
  for (const l of p.locations) {
    if (locIds.has(l.id)) errs.push(`duplicate location ${l.id}`);
    locIds.add(l.id);
    if (l.currency !== "USD") errs.push(`${l.id}: non-USD currency`);
    try {
      new Intl.DateTimeFormat("en-CA", { timeZone: l.timezone });
    } catch {
      errs.push(`${l.id}: invalid timezone ${JSON.stringify(l.timezone)}`);
    }
  }
  const seen = new Set<string>();
  let prev: [string, string] | null = null;
  for (const r of p.rows) {
    const key = `${r.locationId}|${r.date}`;
    if (!locIds.has(r.locationId)) errs.push(`row for unknown location ${r.locationId}`);
    if (!isLocalDate(r.date)) { errs.push(`bad date ${key}`); continue; }
    if (r.date < p.start || r.date > p.end) errs.push(`date outside [start,end]: ${key}`);
    if (seen.has(key)) errs.push(`duplicate row ${key}`);
    seen.add(key);
    if (prev && (r.locationId < prev[0] || (r.locationId === prev[0] && r.date < prev[1]))) errs.push(`rows not sorted at ${key}`);
    prev = [r.locationId, r.date];
    if (!isCents(r.grossSalesCents)) errs.push(`${key}: grossSalesCents not a non-negative integer`);
    if (!isCents(r.orderCount)) errs.push(`${key}: orderCount not a non-negative integer`);
    if (r.categories) {
      let s = 0;
      for (const [k, v] of Object.entries(r.categories)) {
        if (!isCents(v)) errs.push(`${key}: category ${k} not a non-negative integer`);
        else s += v;
      }
      if (s !== r.grossSalesCents) errs.push(`${key}: categories sum ${s} != gross ${r.grossSalesCents}`);
    }
  }
  for (const l of p.locations)
    for (const d of enumerateDates(p.start, p.end))
      if (!seen.has(`${l.id}|${d}`)) errs.push(`missing row ${l.id}|${d}`);
  return errs.slice(0, 50);
}
