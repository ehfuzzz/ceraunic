// Display helpers for the onboard / coverage / policies pages. Wire units (Phase 7): money is integer
// USDC base units (E6), temperature is tenths of a degree F, rain is hundredths of an inch.
import type { Peril } from "./api";

const usd2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

/** Integer USDC base units -> "$1,234.56". Exact for any safe integer. */
export function usdE6(e6: number): string {
  const cents = Math.round(e6 / 10_000);
  return usd2.format(cents / 100);
}
export const usdCents = (c: number) => usd2.format(c / 100);
export const usdCentsWhole = (c: number) => usd0.format(Math.round(c / 100));

export function tenthsF(t: number): string {
  return `${(t / 10).toFixed(1)}°F`;
}
export function hundredthsIn(h: number): string {
  return `${(h / 100).toFixed(2)} in`;
}
/** The strike field is tenths of °F for heat/cold and hundredths of an inch for rain. */
export function level(peril: Peril, v: number): string {
  return peril === "rain" ? hundredthsIn(v) : tenthsF(v);
}
export function settlementValue(unit: string, v: number): string {
  if (unit === "wetDay") return v >= 1 ? "Wet day" : "Dry day";
  return unit === "hundredthsIn" ? hundredthsIn(v) : tenthsF(v);
}

export const PERIL_LABEL: Record<Peril, string> = { heat: "Hot days", cold: "Cool days", rain: "Rainy days" };

/** One plain sentence saying when the cover pays. For rain, `where` is the rain station and `units` the dollars per wet day. */
export function trigger(peril: Peril, strike: number, cap: number, where: string, units?: number): string {
  if (peril === "heat") return `Pays when the high at ${where} goes above ${tenthsF(strike)}, in full at ${tenthsF(strike + cap)} or hotter.`;
  if (peril === "cold") return `Pays when the high at ${where} stays below ${tenthsF(strike)}, in full at ${tenthsF(strike - cap)} or cooler.`;
  return `Pays ${units ? usd0.format(units) : "a fixed amount"} for each covered day the National Weather Service daily report for ${where} shows rain. Kalshi's rain contract counts a trace as no rain, and so does this cover: it pays on 0.01 in or more.`;
}

/** Where a cover settles: the temperature station, or for rain the metro's rain station (O'Hare for Chicago). */
export function settlesAt(peril: Peril, business: { rainStationName?: string | null } | undefined, tempStation: string): string {
  return peril === "rain" && business?.rainStationName ? business.rainStationName : tempStation;
}

export function pct(x: number, digits = 1): string {
  return `${(x * 100).toFixed(digits)}%`;
}
export function signedPct(x: number, digits = 1): string {
  const s = (x * 100).toFixed(digits);
  return x > 0 ? `+${s}%` : `${s}%`;
}

export function shortAddr(a: string): string {
  return `${a.slice(0, 6)}…${a.slice(-4)}`;
}

/** "2025-07-14T12:00:00Z" -> "Jul 14, 12:00 UTC". */
export function utc(ts: string): string {
  const d = new Date(ts);
  const mon = d.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
  return `${mon} ${d.getUTCDate()}, ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")} UTC`;
}

export function dayRange(days: string[]): string {
  if (days.length === 0) return "no days";
  return days.length === 1 ? days[0] : `${days[0]} to ${days[days.length - 1]} (${days.length} days)`;
}
