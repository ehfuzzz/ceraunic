"use client";

// Small browser-storage hooks for the trade, pool and admin pages.
//  - The admin token is typed once and kept in sessionStorage only (gone when the tab closes).
//  - Without a wallet (sim mode) the trader address is an address the visitor picks; localStorage.
import { useCallback, useSyncExternalStore } from "react";
import { useAccount } from "wagmi";
import { isAddress } from "viem";

const EVT = "wi:trading-store";

const getStore = (kind: "session" | "local") => (kind === "session" ? window.sessionStorage : window.localStorage);

function useStored(kind: "session" | "local", key: string): [string | null, (v: string | null) => void] {
  const subscribe = useCallback(
    (cb: () => void) => {
      window.addEventListener(EVT, cb);
      window.addEventListener("storage", cb);
      return () => {
        window.removeEventListener(EVT, cb);
        window.removeEventListener("storage", cb);
      };
    },
    [],
  );
  const value = useSyncExternalStore(
    subscribe,
    () => getStore(kind).getItem(key),
    () => null,
  );
  const set = useCallback(
    (v: string | null) => {
      if (v == null) getStore(kind).removeItem(key);
      else getStore(kind).setItem(key, v);
      window.dispatchEvent(new Event(EVT));
    },
    [kind, key],
  );
  return [value, set];
}

export function useAdminToken() {
  const [token, setToken] = useStored("session", "wi.admin.token");
  return { token, setToken };
}

/** The sim world this browser is in (same key api.ts uses); null means the shared demo world. */
export function useWorldId() {
  const [id] = useStored("local", "wi.world");
  return id;
}

/** Tell the hooks above that storage changed from outside them (api.newWorld writes localStorage directly). */
export function notifyStoreChanged() {
  window.dispatchEvent(new Event(EVT));
}

export interface TradingAccount {
  address: string | null;
  source: "wallet" | "sim" | null;
  setSimAddress: (a: string | null) => void;
}

export function useTradingAccount(): TradingAccount {
  const { address: wallet } = useAccount();
  const [sim, setSim] = useStored("local", "wi.trade.address");
  if (wallet) return { address: wallet, source: "wallet", setSimAddress: setSim };
  if (sim && isAddress(sim)) return { address: sim, source: "sim", setSimAddress: setSim };
  return { address: null, source: null, setSimAddress: setSim };
}

/** A fresh random address for sim trading (20 random bytes; nobody holds its key). */
export function randomSimAddress(): string {
  const b = new Uint8Array(20);
  crypto.getRandomValues(b);
  return "0x" + Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}
