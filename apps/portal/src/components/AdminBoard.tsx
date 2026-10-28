"use client";

import { useAdminToken } from "@/lib/trading-store";
import { useEngineConfig } from "@/lib/trading-queries";
import { AdminHouseMm } from "./AdminHouseMm";
import { AdminModeBanner } from "./AdminModeBanner";
import { AdminOracle } from "./AdminOracle";
import { AdminSimControls } from "./AdminSimControls";
import { AdminTokenGate } from "./AdminTokenGate";

function Sections() {
  const { token } = useAdminToken();
  const cfg = useEngineConfig();
  if (!token) return null;
  return (
    <>
      {cfg.data?.mode === "sim" && <AdminSimControls />}
      <AdminHouseMm token={token} />
      <AdminOracle token={token} />
    </>
  );
}

export function AdminBoard() {
  return (
    <div className="max-w-5xl">
      <h1 className="font-display text-3xl tracking-tight">Admin</h1>
      <p className="mt-4 max-w-2xl text-muted">
        The house side of the pool: the quotes it posts, what it holds, the paper hedges it places on Kalshi, and the temperature readings that
        settle everything. On testnet these are run by the house; in the simulated chain you can drive them by hand.
      </p>
      <div className="mt-8">
        <AdminModeBanner />
        <AdminTokenGate>
          <Sections />
        </AdminTokenGate>
      </div>
    </div>
  );
}
