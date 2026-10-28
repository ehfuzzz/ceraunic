// Display helpers for the trade, pool and admin pages.
// Money is integer USDC base units (E6). A residual unit pays 1 USDC at most, so a limit price of
// 300_000 is 30 cents, and cents are the "tick" (1..99) the engine accepts.

export const UNIT_E6 = 1_000_000;
export const TICK_E6 = 10_000;

export function usd(e6: number, digits = 2): string {
  return (e6 / UNIT_E6).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Scalar tick: the limit price in whole cents (1..99). */
export function tick(priceE6: number): number {
  return priceE6 / TICK_E6;
}

/**
 * Signed basis price in degrees F. A residual contract pays clamp((x - lo) / (hi - lo)) of one USDC
 * on the index x = metro temperature minus station temperature, with lo = -R and hi = +R
 * (R = rangeTenthsF / 10 degrees). So price p breaks even at x = -R + 2R * p.
 * 50 cents is a basis of 0.0 F; cheaper means the market expects the metro to run cooler than the station.
 */
export function basisF(priceE6: number, rangeTenthsF: number): number {
  return (-rangeTenthsF + (priceE6 / UNIT_E6) * 2 * rangeTenthsF) / 10;
}

export function signedF(v: number): string {
  const s = v.toFixed(1);
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${s.replace("-", "")} °F`;
}

/** "30¢ / basis −2.0 °F". */
export function priceBoth(priceE6: number | null, rangeTenthsF: number): string {
  if (priceE6 == null) return "none";
  return `${tick(priceE6)}¢ · ${signedF(basisF(priceE6, rangeTenthsF))}`;
}

export function utc(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.toLocaleString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}Z`;
}

export function short(s: string, head = 6, tail = 4): string {
  return s.length > head + tail + 1 ? `${s.slice(0, head)}…${s.slice(-tail)}` : s;
}

export function pct(bp: number): string {
  return `${(bp / 100).toFixed(2)}%`;
}
