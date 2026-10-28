// Calendar math on "YYYY-MM-DD" strings using UTC arithmetic only. Never local Date objects:
// DST gives 23- and 25-hour days.
import type { LocalDate } from "./types";

const RE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function isLocalDate(s: unknown): s is LocalDate {
  if (typeof s !== "string") return false;
  const m = RE.exec(s);
  if (!m) return false;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return d.toISOString().slice(0, 10) === s;
}

export function asLocalDate(s: string): LocalDate {
  if (!isLocalDate(s)) throw new Error(`not a YYYY-MM-DD date: ${JSON.stringify(s)}`);
  return s;
}

export function addDays(d: string, n: number): LocalDate {
  const m = RE.exec(d);
  if (!m) throw new Error(`bad date ${d}`);
  const t = Date.UTC(+m[1], +m[2] - 1, +m[3]) + n * 86_400_000;
  return new Date(t).toISOString().slice(0, 10) as LocalDate;
}

export function dayIndex(d: string): number {
  const m = RE.exec(d);
  if (!m) throw new Error(`bad date ${d}`);
  return Math.round(Date.UTC(+m[1], +m[2] - 1, +m[3]) / 86_400_000);
}

/** Inclusive range of dates. */
export function enumerateDates(start: string, end: string): LocalDate[] {
  const out: LocalDate[] = [];
  const n = dayIndex(end) - dayIndex(start);
  for (let i = 0; i <= n; i++) out.push(addDays(start, i));
  return out;
}

/** Local "YYYY-MM-DD" of a UTC instant in an IANA zone (ICU handles DST). */
export function localDateFn(timeZone: string): (isoOrMs: string | number) => LocalDate {
  const f = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" });
  return (x) => f.format(new Date(x)) as LocalDate;
}
