"use client";

// Who is acting: a connected wallet wins; in the simulated chain a demo address is fine.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { explain } from "@/lib/core-api";
import { shortAddr, usdE6 } from "@/lib/core-format";
import { ensureDemoAddress, useEngineMode, useHolder } from "@/lib/core-session";
import { btn, ErrorLine } from "./ui";

export function HolderCard({ showBalance = false }: { showBalance?: boolean }) {
  const holder = useHolder();
  const cfg = useEngineMode();
  const qc = useQueryClient();
  const isSim = cfg.data?.mode === "sim";

  const balance = useQuery({
    queryKey: ["balances", holder.address],
    queryFn: () => api.balances(holder.address!),
    enabled: showBalance && !!holder.address,
  });
  const faucet = useMutation({
    mutationFn: () => api.faucet(holder.address!, 1_000 * 1_000_000),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["balances"] }),
  });

  if (!holder.address) {
    return (
      <div className="border border-rule px-4 py-4 text-sm">
        {isSim ? (
          <>
            <p>
              No wallet connected. The simulated chain doesn&apos;t need one: you can use a demo address that only exists
              in this browser.
            </p>
            <button type="button" className={`${btn} mt-3`} onClick={() => ensureDemoAddress()} data-testid="use-demo-address">
              Use a demo address
            </button>
          </>
        ) : (
          <p>Connect a wallet (top right) to continue. Everything you sign goes to {cfg.data?.chain.name ?? "the chain"}.</p>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border border-rule px-4 py-3 text-sm" data-testid="holder-card">
      <span>
        Acting as <span className="font-mono">{shortAddr(holder.address)}</span>{" "}
        <span className="text-muted">({holder.source === "wallet" ? "your wallet" : "demo address, this browser only"})</span>
      </span>
      {showBalance && (
        <span className="flex items-center gap-3">
          <span data-testid="usdc-balance">
            {balance.data ? `${usdE6(balance.data.usdcE6)} test USDC` : balance.isLoading ? "…" : "–"}
          </span>
          {isSim && (
            <button type="button" className={btn} disabled={faucet.isPending} onClick={() => faucet.mutate()} data-testid="faucet-button">
              {faucet.isPending ? "Adding…" : "Add $1,000 test USDC"}
            </button>
          )}
        </span>
      )}
      <ErrorLine error={faucet.error ? explain(faucet.error) : balance.error ? explain(balance.error) : null} />
    </div>
  );
}
