"use client";

// Recommendation -> editable terms -> quotes on both paths side by side -> buy -> receipt.
import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type Business, type HedgePath, type Peril, type Recommendation } from "@/lib/api";
import { coreApi, explain } from "@/lib/core-api";
import { PERIL_LABEL, settlesAt, trigger, usdE6 } from "@/lib/core-format";
import { useCoreSession, useEngineMode } from "@/lib/core-session";
import { addDays, dayIndex } from "@/lib/sales/dates";
import { useStationName } from "./BusinessCard";
import { BuyPanel } from "./BuyPanel";
import { QuoteCompare } from "./QuoteCompare";
import { btn, btnPrimary, ErrorLine, input, label, Muted, Row, Step } from "./ui";

export function CoverageFlow() {
  const { business, world } = useCoreSession();
  if (!business) {
    return (
      <div className="mt-8 max-w-xl border border-rule p-5 text-sm">
        <p>We need your business first, so we know which weather station and which kind of weather matter to you.</p>
        <Link href="/app/onboard" className="mt-3 inline-block !text-accent">
          Go to onboarding
        </Link>
      </div>
    );
  }
  return <CoverageForBusiness key={`${world}|${business.businessId}`} business={business} />;
}

function CoverageForBusiness({ business }: { business: Business }) {
  const cfg = useEngineMode();
  const isSim = cfg.data?.mode === "sim";
  const rec = useQuery({ queryKey: ["recommendation", business.businessId], queryFn: () => api.recommendation(business.businessId) });
  const clock = useQuery({ queryKey: ["clock"], queryFn: () => coreApi.clock(), enabled: isSim });
  const today = isSim ? clock.data?.simTime.slice(0, 10) : cfg.data ? new Date().toISOString().slice(0, 10) : undefined;
  const station = useStationName(business.settlementStation);
  const where = station?.name ?? business.settlementStation;

  return (
    <>
      <Step n={1} title="What we suggest">
        {rec.data ? <RecommendCard r={rec.data} where={where} business={business} /> : <Muted>{rec.error ? explain(rec.error) : "Loading…"}</Muted>}
        {rec.data && rec.data.peril !== "rain" && business.rainStationName && (
          <p className="mt-3 text-sm text-muted">
            Rain cover is here too: pick &ldquo;Rainy days&rdquo; below for a payout on each wet day at {business.rainStationName}.
          </p>
        )}
      </Step>
      {rec.data && today && <Terms key={today} business={business} r={rec.data} today={today} where={where} isSim={isSim} />}
    </>
  );
}

function RecommendCard({ r, where, business }: { r: Recommendation; where: string; business?: Business }) {
  return (
    <div className="border border-rule bg-surface p-5" data-testid="recommend-card">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="font-display text-lg">{PERIL_LABEL[r.peril]} cover</h3>
        <span className="text-sm text-muted">
          {r.maxDailyPremiumE6 > 0
            ? `up to ${usdE6(r.maxDailyPremiumE6)} a day in premium`
            : `We can't price this line in this month; try a ${r.peril === "cold" ? "lower" : "higher"} line.`}
        </span>
      </div>
      <p className="mt-2 text-[15px]">{trigger(r.peril, r.strikeTenthsF, r.capTenthsF, settlesAt(r.peril, business, where), r.unitsPerDay)}</p>
      <div className="mt-3">
        <Row k={r.peril === "rain" ? "Dollars per wet day" : "Units per day (each pays up to $1)"} v={r.unitsPerDay} />
        <Row k="Expected hedge fit" v={`${Math.round(r.heEstimate * 100)}%`} />
      </div>
      <ul className="mt-3 list-disc pl-5 text-sm text-muted">
        {r.rationale.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">
        Hedge fit is the share of your weather-driven swings in sales this cover is expected to offset. It is an estimate from
        past data, not a promise.
      </p>
    </div>
  );
}

interface TermsState {
  peril: Peril;
  strike: string; // display units: °F, or inches for rain
  cap: string;
  units: string;
  start: string;
  end: string;
}

const toDisplay = (peril: Peril, v: number) => (peril === "rain" ? (v / 100).toFixed(2) : (v / 10).toFixed(1));
const toWire = (peril: Peril, s: string) => Math.round(Number(s) * (peril === "rain" ? 100 : 10));

function Terms({ business, r, today, where, isSim }: { business: Business; r: Recommendation; today: string; where: string; isSim: boolean }) {
  const first = addDays(today, 1);
  const initial: TermsState = {
    peril: r.peril,
    strike: toDisplay(r.peril, r.strikeTenthsF),
    cap: toDisplay(r.peril, r.capTenthsF),
    units: String(r.unitsPerDay),
    start: first,
    end: addDays(first, 6),
  };
  const [t, setT] = useState<TermsState>(initial);
  const [chosen, setChosen] = useState<HedgePath>("house-hedge");
  const set = <K extends keyof TermsState>(k: K, v: TermsState[K]) => setT((x) => ({ ...x, [k]: v }));
  const rainRec = useQuery({ queryKey: ["recommendation", business.businessId, "rain"], queryFn: () => api.recommendation(business.businessId, "rain") });
  const isRain = t.peril === "rain";
  const rainWhere = business.rainStationName ?? where;

  const nDays = /^\d{4}-\d{2}-\d{2}$/.test(t.start) && /^\d{4}-\d{2}-\d{2}$/.test(t.end) ? dayIndex(t.end) - dayIndex(t.start) + 1 : 0;
  const problems: string[] = [];
  if (!(Number(t.units) > 0) || !Number.isInteger(Number(t.units)))
    problems.push(isRain ? "Dollars per wet day must be a whole number above zero." : "Units must be a whole number above zero.");
  if (!isRain && !(Number(t.cap) > 0)) problems.push("The range must be above zero.");
  if (!isRain && (!Number.isFinite(Number(t.strike)) || t.strike.trim() === "")) problems.push("Set the line.");
  if (nDays < 1 || nDays > 31) problems.push("Pick 1 to 31 days, with the end on or after the start.");
  if (t.start <= today) problems.push(`The first covered day has to be after today (${today}).`);

  const quotes = useMutation({
    mutationFn: async () => {
      const base = {
        businessId: business.businessId,
        peril: t.peril,
        // rain has no line or range: the cover pays a fixed amount per wet day (the engine ignores these two)
        strikeTenthsF: t.peril === "rain" ? 0 : toWire(t.peril, t.strike),
        capTenthsF: t.peril === "rain" ? 1 : toWire(t.peril, t.cap),
        units: Number(t.units),
        startDay: t.start,
        endDay: t.end,
      };
      const [house, ladder] = await Promise.all([
        api.quote({ ...base, path: "house-hedge" }),
        api.quote({ ...base, path: "business-ladder" }),
      ]);
      return { house, ladder, terms: base };
    },
  });
  const unit = "°F";

  return (
    <>
      <Step n={2} title="Adjust the terms">
        <form
          className="grid gap-4 sm:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault();
            quotes.mutate();
          }}
        >
          <div>
            <label className={label} htmlFor="t-peril">
              Weather
            </label>
            <select
              id="t-peril"
              className={`${input} mt-1`}
              value={t.peril}
              onChange={(e) => {
                const p = e.target.value as Peril;
                setT((x) => ({
                  ...x,
                  peril: p,
                  strike: p === r.peril ? initial.strike : p === "heat" ? "88.0" : "78.0",
                  cap: p === r.peril ? initial.cap : "10.0",
                  units: p === "rain" ? String(rainRec.data?.unitsPerDay ?? 25) : p === r.peril ? initial.units : x.peril === "rain" ? initial.units : x.units,
                }));
              }}
            >
              <option value="heat">Hot days</option>
              <option value="cold">Cool days</option>
              <option value="rain">Rainy days</option>
            </select>
          </div>
          {isRain ? (
            <p className="text-sm text-muted sm:col-span-2 sm:self-end" data-testid="rain-rule">
              No line to set: it pays the same amount on every wet day in the National Weather Service daily report for{" "}
              {rainWhere}. Kalshi&apos;s rain contract counts a trace as no rain, and so does this cover: it pays on 0.01 in or more.
            </p>
          ) : (
            <>
              <div>
                <label className={label} htmlFor="t-strike">
                  Line ({unit})
                </label>
                <input id="t-strike" className={`${input} mt-1`} inputMode="decimal" value={t.strike} onChange={(e) => set("strike", e.target.value)} data-testid="terms-strike" />
              </div>
              <div>
                <label className={label} htmlFor="t-cap">
                  Range to full payout ({unit})
                </label>
                <input id="t-cap" className={`${input} mt-1`} inputMode="decimal" value={t.cap} onChange={(e) => set("cap", e.target.value)} />
              </div>
            </>
          )}
          <div>
            <label className={label} htmlFor="t-units">
              {isRain ? "Dollars per wet day" : "Units per day"}
            </label>
            <input id="t-units" className={`${input} mt-1`} inputMode="numeric" value={t.units} onChange={(e) => set("units", e.target.value)} data-testid="terms-units" />
          </div>
          <div>
            <label className={label} htmlFor="t-start">
              First day
            </label>
            <input id="t-start" type="date" className={`${input} mt-1`} value={t.start} min={first} onChange={(e) => set("start", e.target.value)} />
          </div>
          <div>
            <label className={label} htmlFor="t-end">
              Last day
            </label>
            <input id="t-end" type="date" className={`${input} mt-1`} value={t.end} min={t.start} onChange={(e) => set("end", e.target.value)} />
          </div>
          <p className="text-sm text-muted sm:col-span-3">
            {problems.length === 0 && isRain
              ? `${trigger("rain", 0, 1, rainWhere, Number(t.units))} If every day is wet it pays ${usdE6(Number(t.units) * nDays * 1_000_000)} over ${nDays} days; a dry week pays nothing.`
              : problems.length === 0 && toWire(t.peril, t.cap) > 0
                ? `${trigger(t.peril, toWire(t.peril, t.strike), toWire(t.peril, t.cap), where)} Each unit pays up to $1 a day, so the most this can pay is ${usdE6(Number(t.units) * nDays * 1_000_000)} over ${nDays} days.`
                : problems.join(" ")}
          </p>
          <div className="flex gap-3 sm:col-span-3">
            <button type="submit" className={btnPrimary} disabled={problems.length > 0 || quotes.isPending} data-testid="quote-button">
              {quotes.isPending ? "Pricing…" : "Get quotes"}
            </button>
            <button type="button" className={btn} onClick={() => setT(initial)}>
              Back to what we suggest
            </button>
          </div>
          <ErrorLine error={quotes.error ? explain(quotes.error) : null} />
        </form>
      </Step>

      {quotes.data && (
        <Step n={3} title="Two ways to buy it">
          <QuoteCompare
            house={quotes.data.house}
            ladder={quotes.data.ladder}
            chosen={chosen}
            onChoose={setChosen}
            peril={quotes.data.terms.peril}
            demoClock={isSim}
            where={quotes.data.terms.peril === "rain" ? rainWhere : where}
          />
        </Step>
      )}
      {quotes.data && chosen === "business-ladder" && quotes.data.ladder.perDayPremiumE6.length === 0 && (
        <Step n={4} title="Buy">
          <p className="max-w-2xl text-sm" data-testid="nothing-to-buy">
            There is nothing to buy from us on this path: place the Kalshi contracts listed above yourself, or choose &ldquo;We handle the
            hedge&rdquo; to buy the cover from us.
          </p>
        </Step>
      )}
      {quotes.data && !(chosen === "business-ladder" && quotes.data.ladder.perDayPremiumE6.length === 0) && (
        <Step n={4} title="Buy">
          <BuyPanel
            key={chosen === "house-hedge" ? quotes.data.house.quoteId : quotes.data.ladder.quoteId}
            quote={chosen === "house-hedge" ? quotes.data.house : quotes.data.ladder}
            path={chosen}
            where={quotes.data.terms.peril === "rain" ? rainWhere : where}
            onRequote={() => quotes.mutate()}
          />
        </Step>
      )}
    </>
  );
}
