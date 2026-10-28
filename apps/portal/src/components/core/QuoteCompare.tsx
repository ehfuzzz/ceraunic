"use client";

// Both hedge paths side by side, with the full cost breakdown.
//  house-hedge:     we buy the station ladder at Kalshi for you (station leg) + the local difference contract.
//  business-ladder: you place the Kalshi rungs yourself; our price is only the local difference contract + fees.
// Rain (13-RAIN): the station leg is one Kalshi "> 0 in" contract per dollar per wet day, one row per covered day; no rain
// local-difference contract is sold (it would settle weekly on PRISM rainfall cells; by request only).
import type { HedgePath, Peril, Quote, Rung } from "@/lib/api";
import { usdCents, usdE6, utc } from "@/lib/core-format";
import { Row } from "./ui";

export function QuoteCompare({
  house,
  ladder,
  chosen,
  onChoose,
  peril,
  demoClock,
  where,
}: {
  demoClock: boolean;
  house: Quote;
  ladder: Quote;
  chosen: HedgePath;
  onChoose: (p: HedgePath) => void;
  peril: Peril;
  where?: string;
}) {
  return (
    <div>
      <div className="grid gap-5 md:grid-cols-2">
        <QuoteColumn q={house} path="house-hedge" chosen={chosen === "house-hedge"} onChoose={onChoose} peril={peril} where={where} />
        <QuoteColumn q={ladder} path="business-ladder" chosen={chosen === "business-ladder"} onChoose={onChoose} peril={peril} where={where} />
      </div>
      <p className="mt-4 max-w-2xl text-xs text-muted">
        Prices hold until {utc(house.expiresAt)}
        {demoClock ? " on the demo clock" : ""}. Kalshi asks are as of {utc(house.stationLeg.asOf)}.
      </p>
    </div>
  );
}

function ladderCostCents(q: Quote) {
  return (q.ladderForBusiness ?? q.stationLeg.rungs).reduce((s, r) => s + r.qty * r.askCents, 0);
}

function QuoteColumn({
  q,
  path,
  chosen,
  onChoose,
  peril,
  where,
}: {
  q: Quote;
  path: HedgePath;
  chosen: boolean;
  onChoose: (p: HedgePath) => void;
  peril: Peril;
  where?: string;
}) {
  const isHouse = path === "house-hedge";
  const isRain = peril === "rain";
  const rungs = q.ladderForBusiness ?? q.stationLeg.rungs;
  const sellsNothing = q.perDayPremiumE6.length === 0;
  const firstDay = rungs[0]?.ticker.split("-")[1];
  return (
    <label
      className={`block border p-5 transition-colors ${sellsNothing ? "cursor-default" : "cursor-pointer"} ${chosen ? "border-accent" : "border-rule hover:border-ink"}`}
      data-testid={`quote-${path}`}
    >
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-2">
          <input type="radio" className="accent-accent" name="path" checked={chosen} onChange={() => onChoose(path)} data-testid={`choose-${path}`} />
          <span className="font-display text-lg">{isHouse ? "We handle the hedge" : "You place the Kalshi part"}</span>
        </span>
      </div>
      <p className="mt-2 text-sm text-muted">
        {isRain
          ? isHouse
            ? `One price. We buy one Kalshi "rain today" contract per dollar for each covered day to back your cover. Kalshi's rain contract counts a trace as no rain, and so does this cover: it pays on 0.01 in or more.`
            : `The Kalshi rain contracts settle on the same ${where ?? "station"} report, so they are the whole hedge. You buy them yourself; we sell nothing on this path. Kalshi's rain contract counts a trace as no rain, and so does this cover: it pays on 0.01 in or more.`
          : isHouse
            ? "One price. We buy the station-temperature ladder at Kalshi to back your cover, and the local difference contract covers the gap to your block."
            : "Cheaper here, but you buy the station ladder at Kalshi yourself. We only sell the local difference contract."}
      </p>

      <div className="mt-4">
        <Row
          k={isRain ? "Station leg (Kalshi rain contracts)" : q.stationLeg.series ? `Station leg (Kalshi ${q.stationLeg.series})` : "Station leg (Kalshi)"}
          v={isHouse ? usdE6(q.stationLegE6) : "you pay Kalshi directly"}
        />
        {isRain ? (
          <Row k="Local difference leg (rain)" v="by request; settles weekly on PRISM rainfall cells" />
        ) : q.residualLeg.contractId ? (
          <Row k={`Local difference leg (${q.residualLeg.contractId}, ${q.residualLeg.qty} units)`} v={usdE6(q.residualLegE6)} />
        ) : (
          <Row k="Local difference leg" v="none: you are at the station" />
        )}
        <Row k="Fees" v={usdE6(q.feesE6)} />
        <div className="flex justify-between gap-4 py-2 text-base">
          <span>You pay us</span>
          <span data-testid={isHouse ? "quote-total" : "quote-total-ladder"}>{sellsNothing ? "nothing" : usdE6(q.premiumE6)}</span>
        </div>
        {!sellsNothing && <Row k={isRain ? "Most it can pay out (every day wet)" : "Most it can pay out"} v={usdE6(q.maxPayoutE6)} />}
        <Row k="Expected hedge fit" v={`${Math.round(q.heEstimate * 100)}%`} />
        {!isRain && q.residualLeg.contractId && (
          <Row k="Local contract fair price / half spread" v={`${usdE6(q.residualLeg.fairPriceE6)} / ${usdE6(q.residualLeg.halfSpreadE6)}`} />
        )}
        {isRain && isHouse && (
          <Row k="First day: fair price / half spread per contract" v={`${usdE6(q.residualLeg.fairPriceE6)} / ${usdE6(q.residualLeg.halfSpreadE6)}`} />
        )}
        {isHouse && !isRain && <Row k="Kalshi overround" v={`${(q.stationLeg.overroundBp / 100).toFixed(1)}%`} />}
      </div>

      <div className="mt-4">
        <div className="text-xs text-muted">
          {isRain
            ? isHouse
              ? "Kalshi rain contracts we buy for you, one per dollar per covered day"
              : "Kalshi rain contracts for you to place, one per dollar per covered day"
            : isHouse
              ? "Kalshi rungs we buy for you"
              : "Kalshi rungs for you to place"}
          {!isRain && firstDay ? ` (shown for the first day, ${firstDay}; the same pattern repeats each day)` : ""}
        </div>
        {isRain ? <RainTable rungs={rungs} testId={isHouse ? "rungs-house" : "rungs-ladder"} /> : <RungTable rungs={rungs} testId={isHouse ? "rungs-house" : "rungs-ladder"} />}
        {!isHouse && !isRain && (
          <p className="mt-3 border-l-2 border-accent pl-3 text-sm" data-testid="ladder-note">
            You place these at Kalshi yourself; we never place them. At today&apos;s asks the first day costs about {usdCents(ladderCostCents(q))} there,
            before Kalshi&apos;s fees. If you skip them, only the local difference is covered.
          </p>
        )}
        {!isHouse && isRain && (
          <p className="mt-3 border-l-2 border-accent pl-3 text-sm" data-testid="ladder-note">
            You place these at Kalshi yourself; we never place them. Each market opens the morning before its day; the ask shown is
            today&apos;s where the market is already open.
          </p>
        )}
        {isRain && q.note && <p className="mt-3 text-xs text-muted" data-testid={isHouse ? "rain-note" : "rain-note-ladder"}>{q.note}</p>}
      </div>
    </label>
  );
}

function RungTable({ rungs, testId }: { rungs: Rung[]; testId: string }) {
  return (
    <table className="mt-1 w-full text-sm" data-testid={testId}>
      <thead>
        <tr className="border-b border-rule text-left text-muted">
          <th className="py-1 font-normal">Ticker</th>
          <th className="py-1 text-right font-normal">Contracts</th>
          <th className="py-1 text-right font-normal">Ask</th>
        </tr>
      </thead>
      <tbody>
        {rungs.map((r) => (
          <tr key={r.ticker} className="border-b border-rule/60">
            <td className="py-1 font-mono text-xs">{r.ticker}</td>
            <td className="py-1 text-right">{r.qty}</td>
            <td className="py-1 text-right">{r.askCents}¢</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const RAIN_PRICE: Record<string, (c: number) => string> = {
  "kalshi-ask": (c) => `${c}¢ Kalshi ask`,
  "wet-day-rate": (c) => `${c}¢ from the wet-day rate`,
  "not-open": () => "opens the morning before",
};

function RainTable({ rungs, testId }: { rungs: Rung[]; testId: string }) {
  return (
    <table className="mt-1 w-full text-sm" data-testid={testId}>
      <thead>
        <tr className="border-b border-rule text-left text-muted">
          <th className="py-1 font-normal">Day</th>
          <th className="py-1 font-normal">Kalshi contract</th>
          <th className="py-1 text-right font-normal">Contracts</th>
          <th className="py-1 text-right font-normal">Price</th>
        </tr>
      </thead>
      <tbody>
        {rungs.map((r) => (
          <tr key={r.ticker} className="border-b border-rule/60" data-testid="rain-contract-row">
            <td className="py-1 font-mono text-xs">{r.forDay ?? ""}</td>
            <td className="py-1 font-mono text-xs">{r.ticker}</td>
            <td className="py-1 text-right">{r.qty}</td>
            <td className="py-1 text-right">{(RAIN_PRICE[r.source ?? "kalshi-ask"] ?? RAIN_PRICE["kalshi-ask"])(r.askCents)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
