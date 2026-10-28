"use client";

// Business profile: name, where it is (local geocoder for the five demo cities, or typed coordinates), and
// what kind of business it is (NAICS). The engine picks the settlement station nearest to the location.
import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Business } from "@/lib/api";
import { explain } from "@/lib/core-api";
import { geocode, NAICS } from "@/lib/geocode";
import { ensureDemoAddress, ensureWorld, useCoreSession, useEngineMode, useHolder } from "@/lib/core-session";
import { btnPrimary, ErrorLine, input, label, Muted } from "./ui";

export function BusinessForm() {
  const cfg = useEngineMode();
  const holder = useHolder();
  const { save } = useCoreSession();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [manual, setManual] = useState(false);
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [naics, setNaics] = useState(NAICS[0].code);
  const isSim = cfg.data?.mode === "sim";

  const found = useMemo(() => (address.trim() ? geocode(address) : null), [address]);
  const coords = manual ? { lat: Number(lat), lon: Number(lon) } : found ? { lat: found.lat, lon: found.lon } : null;
  const coordsOk = !!coords && Number.isFinite(coords.lat) && Number.isFinite(coords.lon) && (!manual || (lat.trim() !== "" && lon.trim() !== ""));

  const create = useMutation({
    mutationFn: async (): Promise<Business> => {
      if (!coordsOk || !coords) throw new Error("We need a location: an address in one of the five demo cities, or latitude and longitude.");
      let owner = holder.address;
      if (!owner) {
        if (!isSim) throw new Error("Connect a wallet first.");
        owner = ensureDemoAddress();
      }
      if (isSim) await ensureWorld();
      const zip = address.match(/\b\d{5}\b/)?.[0];
      return api.createBusiness({ name: name.trim(), lat: coords.lat, lon: coords.lon, zip: zip ?? null, naics, owner });
    },
    onSuccess: (b) => {
      save("sales", null);
      save("elasticity", null);
      save("business", b);
      qc.invalidateQueries();
    },
  });

  return (
    <form
      className="grid gap-5"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <div>
        <label className={label} htmlFor="biz-name">
          Business name
        </label>
        <input id="biz-name" className={`${input} mt-1`} value={name} onChange={(e) => setName(e.target.value)} placeholder="Scoops on 9th" required data-testid="business-name" />
      </div>

      <div>
        <label className={label} htmlFor="biz-address">
          Address or ZIP
        </label>
        <input
          id="biz-address"
          className={`${input} mt-1`}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="e.g. 10019, or 350 W 42nd St, New York, NY 10036"
          disabled={manual}
          data-testid="business-address"
        />
        <p className="mt-1.5 text-xs text-muted" data-testid="geocode-result">
          {manual
            ? "Using the coordinates you typed."
            : found
              ? `Found ${found.label}${found.zip ? ` (ZIP ${found.zip})` : ""}: ${found.lat.toFixed(4)}, ${found.lon.toFixed(4)}. Approximate, but close enough to pick the weather station.`
              : address.trim()
                ? "We only know the five demo areas (New York City, Newark and Jersey City, Trenton and Princeton, Chicago, Miami). Try a ZIP, or type coordinates."
                : "The demo covers New York City, Newark and Jersey City, Trenton and Princeton, Chicago and Miami."}
        </p>
        <label className="mt-2 flex items-center gap-2 text-xs text-muted">
          <input type="checkbox" checked={manual} onChange={(e) => setManual(e.target.checked)} />
          Type latitude and longitude instead
        </label>
        {manual && (
          <div className="mt-2 grid grid-cols-2 gap-3">
            <input className={input} inputMode="decimal" placeholder="Latitude, e.g. 40.7651" value={lat} onChange={(e) => setLat(e.target.value)} aria-label="Latitude" />
            <input className={input} inputMode="decimal" placeholder="Longitude, e.g. -73.9858" value={lon} onChange={(e) => setLon(e.target.value)} aria-label="Longitude" />
          </div>
        )}
      </div>

      <div>
        <label className={label} htmlFor="biz-naics">
          What kind of business
        </label>
        <select id="biz-naics" className={`${input} mt-1`} value={naics} onChange={(e) => setNaics(e.target.value)} data-testid="business-naics">
          {NAICS.map((n) => (
            <option key={n.code} value={n.code}>
              {n.label} (NAICS {n.code})
            </option>
          ))}
        </select>
        <Muted className="mt-1.5 text-xs">
          The type sets the starting guess for how weather moves your sales, before we see any of your own numbers.
        </Muted>
      </div>

      <div>
        <button type="submit" className={btnPrimary} disabled={create.isPending || !name.trim() || !coordsOk} data-testid="business-save">
          {create.isPending ? "Saving…" : "Save business"}
        </button>
        <ErrorLine error={create.error ? explain(create.error) : null} />
      </div>
    </form>
  );
}
