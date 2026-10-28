"use client";

// Browser-side state for the onboard -> coverage -> policies flow.
//  - The sim world id lives in localStorage under "wi.world" (api.ts worldStore); we create one on first use.
//  - The acting address: a connected wallet wins. In sim mode without a wallet we use a random demo address
//    kept under "wi.trade.address", the same key the trade/pool pages use, so the demo is one person.
//  - The business, its sales summary and elasticity are cached per world under "wi.core.*".
import { useCallback, useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAccount } from "wagmi";
import { api, EngineError, worldStore, type Business, type Elasticity, type SalesSummary } from "./api";
import { coreApi } from "./core-api";

const EVT = "wi:core-session";
const SIM_ADDR = "wi.trade.address";
const K = { business: "wi.core.business", sales: "wi.core.sales", elasticity: "wi.core.elasticity" } as const;

function subscribe(cb: () => void) {
  window.addEventListener(EVT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVT, cb);
    window.removeEventListener("storage", cb);
  };
}
const notify = () => window.dispatchEvent(new Event(EVT));
const read = (k: string) => (typeof window === "undefined" ? null : window.localStorage.getItem(k));
function write(k: string, v: string | null) {
  if (v == null) window.localStorage.removeItem(k);
  else window.localStorage.setItem(k, v);
  notify();
  window.dispatchEvent(new Event("wi:trading-store"));
}

function useStored(k: string) {
  return useSyncExternalStore(subscribe, () => read(k), () => null);
}

type Scoped<T> = { world: string; value: T };
function parseScoped<T>(raw: string | null, world: string | null): T | null {
  if (!raw || !world) return null;
  try {
    const s = JSON.parse(raw) as Scoped<T>;
    return s.world === world ? s.value : null;
  } catch {
    return null;
  }
}

export function useEngineMode() {
  return useQuery({ queryKey: ["config"], queryFn: () => api.config(), staleTime: 60_000 });
}

export interface Holder {
  address: string | null;
  source: "wallet" | "demo" | null;
}

export function useHolder(): Holder {
  const { address } = useAccount();
  const sim = useStored(SIM_ADDR);
  if (address) return { address, source: "wallet" };
  if (sim && /^0x[0-9a-fA-F]{40}$/.test(sim)) return { address: sim, source: "demo" };
  return { address: null, source: null };
}

export function randomDemoAddress(): string {
  const b = new Uint8Array(20);
  crypto.getRandomValues(b);
  return "0x" + Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

export function ensureDemoAddress(): string {
  const cur = read(SIM_ADDR);
  if (cur && /^0x[0-9a-fA-F]{40}$/.test(cur)) return cur;
  const a = randomDemoAddress();
  write(SIM_ADDR, a);
  return a;
}

export function useCoreSession() {
  const world = useStored("wi.world");
  const businessRaw = useStored(K.business);
  const salesRaw = useStored(K.sales);
  const elasticityRaw = useStored(K.elasticity);
  const business = parseScoped<Business>(businessRaw, world);
  const sales = parseScoped<SalesSummary>(salesRaw, world);
  const elasticity = parseScoped<Elasticity>(elasticityRaw, world);
  const save = useCallback(
    <T,>(k: keyof typeof K, value: T | null) => {
      const w = worldStore.get();
      write(K[k], value == null || !w ? null : JSON.stringify({ world: w, value } satisfies Scoped<T>));
    },
    [],
  );
  return { world, business, sales, elasticity, save };
}

export function clearCoreSession() {
  for (const k of Object.values(K)) window.localStorage.removeItem(k);
  notify();
}

/** Sim only: make sure this visitor has a world the engine still knows (the local API loses worlds on restart). */
export async function ensureWorld(): Promise<string> {
  const cur = worldStore.get();
  if (cur) {
    try {
      await coreApi.clock();
      return cur;
    } catch (e) {
      if (!(e instanceof EngineError && e.problem.status === 404)) throw e;
    }
  }
  clearCoreSession();
  const w = await api.newWorld();
  notify();
  return w.worldId;
}

/** Starts the demo over: a fresh world and no business. */
export async function freshWorld(): Promise<string> {
  clearCoreSession();
  const w = await api.newWorld();
  notify();
  return w.worldId;
}
