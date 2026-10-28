import type { PoolState } from "@/lib/api";
import { utc } from "@/lib/trading-format";

type Point = PoolState["navHistory"][number];

/** NAV per share over time for both tranches. A dependency-free SVG line chart. */
export function PoolNavChart({ points }: { points: Point[] }) {
  if (points.length < 2) return <p className="text-sm text-muted">Not enough history to draw yet.</p>;
  const W = 640;
  const H = 180;
  const PAD = { l: 48, r: 12, t: 12, b: 24 };
  const vals = points.flatMap((p) => [p.seniorNavE6, p.juniorNavE6]).map((v) => v / 1e6);
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  if (hi - lo < 0.02) {
    // Flat history: show a band around the value so a flat line reads as flat, not as a broken chart.
    const mid = (hi + lo) / 2;
    lo = mid - 0.05;
    hi = mid + 0.05;
  }
  const x = (i: number) => PAD.l + (i / (points.length - 1)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
  const line = (pick: (p: Point) => number) =>
    points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(pick(p) / 1e6).toFixed(1)}`).join(" ");
  const ticks = [lo, (lo + hi) / 2, hi];
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="NAV per share over time, senior and junior" className="w-full max-w-2xl">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke="var(--rule)" />
            <text x={PAD.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--muted)" fontFamily="var(--mono)">
              {t.toFixed(3)}
            </text>
          </g>
        ))}
        <path d={line((p) => p.juniorNavE6)} fill="none" stroke="var(--muted)" strokeWidth="2" strokeDasharray="5 4" />
        <path d={line((p) => p.seniorNavE6)} fill="none" stroke="var(--accent)" strokeWidth="2" />
        <text x={PAD.l} y={H - 6} fontSize="11" fill="var(--muted)" fontFamily="var(--mono)">
          {utc(points[0].ts)}
        </text>
        <text x={W - PAD.r} y={H - 6} textAnchor="end" fontSize="11" fill="var(--muted)" fontFamily="var(--mono)">
          {utc(points[points.length - 1].ts)}
        </text>
      </svg>
      <figcaption className="mt-1 flex gap-6 text-xs text-muted">
        <span><span className="text-accent">&mdash;</span> senior, per share</span>
        <span>- - junior, per share</span>
      </figcaption>
    </figure>
  );
}
