"use client";

// Shown on the trade, pool and admin pages when the engine and the portal disagree about the chain mode
// (or the engine cannot be reached at all).
import { CHAIN_MODE } from "@/lib/chain-mode";
import { useEngineConfig } from "@/lib/trading-queries";
import { messageOf } from "./TradingKit";

export function AdminModeBanner() {
  const cfg = useEngineConfig();
  if (cfg.isError)
    return (
      <p role="alert" className="mb-8 border border-accent px-4 py-3 text-sm">
        Can&rsquo;t reach the engine. {messageOf(cfg.error)}
      </p>
    );
  if (!cfg.data || cfg.data.mode === CHAIN_MODE) return null;
  return (
    <p role="alert" className="mb-8 border border-accent px-4 py-3 text-sm">
      Mode mismatch. The engine is running <span className="font-mono">{cfg.data.mode}</span> but this portal was built for{" "}
      <span className="font-mono">{CHAIN_MODE}</span>. What you see and what you sign may not line up until they match.
    </p>
  );
}
