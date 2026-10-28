"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Business } from "@/lib/api";
import { explain } from "@/lib/core-api";
import { NAICS } from "@/lib/geocode";
import { freshWorld, useEngineMode } from "@/lib/core-session";
import { btn, ErrorLine, Row } from "./ui";

export function useStationName(stationId: string | undefined) {
  const cfg = useEngineMode();
  const s = cfg.data?.stations.find((x) => x.stationId === stationId);
  return s ? { name: s.name, id: s.stationId, source: s.settlementSource, series: s.kalshiSeries } : null;
}

export function naicsLabel(code: string | null | undefined): string {
  if (!code) return "Not given";
  const exact = NAICS.find((n) => n.code === code);
  if (exact) return exact.label;
  const sector = NAICS.find((n) => n.code.startsWith(code));
  return sector ? `${sector.label} and similar` : `NAICS ${code}`;
}

export function BusinessCard({ business }: { business: Business }) {
  const station = useStationName(business.settlementStation);
  const cfg = useEngineMode();
  const qc = useQueryClient();
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isSim = cfg.data?.mode === "sim";

  return (
    <div className="border border-rule bg-surface p-5" data-testid="business-card">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="font-display text-lg">{business.name}</h3>
        <span className="font-mono text-xs text-muted">{business.businessId}</span>
      </div>
      <div className="mt-3">
        <Row k="Kind" v={naicsLabel(business.naics)} />
        <Row k="Location" v={`${business.lat.toFixed(4)}, ${business.lon.toFixed(4)}${business.zip ? ` (ZIP ${business.zip})` : ""}`} />
        <Row k="Weather station" v={station ? `${station.name} (${station.id})` : business.settlementStation} />
        <Row k="Local difference contract" v={business.residualContractId} mono />
      </div>
      <p className="mt-3 text-sm text-muted">
        Your cover settles on the daily high at {station?.name ?? business.settlementStation}, from the National Weather Service
        daily climate report. Because your shop isn&apos;t standing on the station, a second small contract covers the gap
        between the station and your part of town.
      </p>
      {isSim && (
        <div className="mt-4">
          <button
            type="button"
            className={btn}
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setErr(null);
              try {
                await freshWorld();
                qc.invalidateQueries();
              } catch (e) {
                setErr(explain(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            Start over with a fresh demo
          </button>
          <ErrorLine error={err} />
        </div>
      )}
    </div>
  );
}
