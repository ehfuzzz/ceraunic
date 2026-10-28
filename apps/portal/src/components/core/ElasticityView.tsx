"use client";

// How weather moves this business's sales, from POST /businesses/{id}/elasticity.
// heat.beta: change in log daily sales per °F above the cover threshold (about a percent per degree).
// wet.beta: change in log daily sales on a wet day. shrinkWeight: how much we trust the business's own
// estimate versus the sector prior (beta_used = mu + w * (beta_own - mu)).
import Link from "next/link";
import type { Business, Elasticity } from "@/lib/api";
import { pct, signedPct } from "@/lib/core-format";
import { naicsLabel } from "./BusinessCard";
import { Stat } from "./ui";

const Z95 = 1.96;

export function ElasticityView({ business, e }: { business: Business; e: Elasticity }) {
  const heatLo = e.heat.beta - Z95 * e.heat.se;
  const heatHi = e.heat.beta + Z95 * e.heat.se;
  const heatClear = heatLo > 0 || heatHi < 0;
  const priorSd = Math.sqrt(e.prior.tau2);
  const used = e.prior.mu + e.shrinkWeight * (e.heat.beta - e.prior.mu);
  const kind = naicsLabel(business.naics);
  const hotHelps = used > 0;

  return (
    <div data-testid="elasticity-view">
      <div className="grid grid-cols-2 gap-5 sm:grid-cols-3">
        <Stat
          label="Hot days, per °F over the line"
          value={`${signedPct(e.heat.beta, 1)}`}
          note={`give or take ${pct(Z95 * e.heat.se, 1)}`}
          testId="elasticity-beta"
        />
        <Stat label="Rainy days" value={signedPct(e.wet.beta, 1)} note={`give or take ${pct(Z95 * e.wet.se, 1)}`} />
        <Stat label="Days of your sales used" value={e.heat.n} />
        <Stat label="Weight on your own numbers" value={pct(e.shrinkWeight, 0)} note={`${pct(1 - e.shrinkWeight, 0)} on the sector average`} testId="elasticity-shrink" />
        <Stat
          label={`Sector average (NAICS ${e.prior.sector})`}
          value={`${signedPct(e.prior.mu, 1)} per °F`}
          note={`spread between businesses ${pct(priorSd, 1)}`}
        />
        <Stat
          label="Where the average comes from"
          value={e.prior.learned ? "Learned" : "Set by hand"}
          note={e.prior.learned ? "fitted on other businesses of this kind" : "a starting guess, not yet learned from data"}
          testId="elasticity-learned"
        />
      </div>

      <div className="mt-6 max-w-2xl space-y-3 text-[15px] leading-relaxed">
        <p>
          The number we use is <strong>{signedPct(used, 1)} of daily sales per °F</strong> once the day gets past the cover&apos;s
          temperature line. {hotHelps
            ? "So heat helps your sales, and a cool day is what costs you money."
            : "So heat hurts your sales, and a hot day is what costs you money."}
        </p>
        <p>
          {e.heat.n === 0
            ? `We haven't seen any of your sales yet, so this is the average for businesses like yours (${kind.toLowerCase()}).`
            : `We blend your own ${e.heat.n} days with the average for businesses like yours: ${pct(e.shrinkWeight, 0)} yours, ${pct(1 - e.shrinkWeight, 0)} the average. `}
          {e.heat.n > 0 &&
            (heatClear
              ? `On their own, your days put the effect between ${signedPct(heatLo, 1)} and ${signedPct(heatHi, 1)}, so the direction is clear.`
              : `On their own, your days put the effect anywhere from ${signedPct(heatLo, 1)} to ${signedPct(heatHi, 1)}, which still includes zero. More history narrows that and moves the weight toward your numbers.`)}
        </p>
        <p className="text-sm text-muted">
          How it was worked out: {e.origin === "prior" ? "sector average only" : "your history, pulled toward the sector average"}.
          Method: {e.method}.
        </p>
      </div>

      <Link href="/app/coverage" className="mt-6 inline-block border border-accent px-4 py-2 text-sm !text-accent no-underline" data-testid="to-coverage">
        See the cover we suggest
      </Link>
    </div>
  );
}
