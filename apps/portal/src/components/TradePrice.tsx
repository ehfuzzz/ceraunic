import { basisF, signedF, tick } from "@/lib/trading-format";

/** A price shown both ways: the scalar tick in cents, and the signed basis in degrees F. */
export function TradePrice({ priceE6, range, align = "left" }: { priceE6: number | null; range: number; align?: "left" | "right" }) {
  if (priceE6 == null) return <span className="text-muted">none</span>;
  return (
    <span className={`inline-block leading-tight ${align === "right" ? "text-right" : ""}`}>
      <span className="font-mono">{tick(priceE6)}&cent;</span>
      <span className="block font-mono text-xs text-muted">{signedF(basisF(priceE6, range))}</span>
    </span>
  );
}
