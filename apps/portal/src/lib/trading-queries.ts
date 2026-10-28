"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { tradingApi } from "./trading-api";

export const POLL_MS = 5000;

/** Engine config (mode, stations, auction contracts). Rarely changes. */
export function useEngineConfig() {
  return useQuery({ queryKey: ["config"], queryFn: () => api.config(), staleTime: 60_000 });
}

export function useSimClock() {
  return useQuery({ queryKey: ["clock"], queryFn: () => tradingApi.clock(), refetchInterval: POLL_MS, retry: false });
}

/** Lookups built from the engine config. */
export function useContractInfo() {
  const cfg = useEngineConfig();
  const contracts = new Map((cfg.data?.auctionContracts ?? []).map((c) => [c.contractId, c]));
  const stations = new Map((cfg.data?.stations ?? []).map((s) => [s.stationId, s]));
  return {
    mode: cfg.data?.mode,
    range: (contractId: string) => contracts.get(contractId)?.rangeTenthsF ?? 50,
    city: (stationId: string) => stations.get(stationId)?.city ?? stationId,
    contractCity: (contractId: string) => {
      const sid = contracts.get(contractId)?.stationId;
      return sid ? (stations.get(sid)?.city ?? sid) : contractId;
    },
    stations: cfg.data?.stations ?? [],
    ready: cfg.isSuccess,
  };
}
