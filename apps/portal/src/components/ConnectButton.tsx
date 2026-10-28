"use client";

import { useAccount, useConnect, useDisconnect, useSwitchChain } from "wagmi";
import { injected } from "wagmi/connectors";
import { TARGET } from "@/lib/chains";

const button =
  "rounded-full border border-rule px-4 py-1.5 text-sm transition-colors hover:border-ink disabled:opacity-50";

function short(address: string) {
  return `${address.slice(0, 6)}…${address.slice(-4)}`;
}

export function ConnectButton() {
  const { address, chain, chainId, isConnected } = useAccount();
  const { connect, isPending, error } = useConnect();
  const { disconnect } = useDisconnect();
  const { switchChain } = useSwitchChain();

  if (!isConnected || !address) {
    return (
      <div className="flex items-center gap-3">
        {error && (
          <span className="hidden text-xs text-muted sm:inline">
            No wallet found in this browser.
          </span>
        )}
        <button
          className={button}
          disabled={isPending}
          onClick={() => connect({ connector: injected() })}
        >
          {isPending ? "Connecting…" : "Connect wallet"}
        </button>
      </div>
    );
  }

  const targetChain = TARGET.kind === "evm" ? TARGET.chain : undefined;
  const wrongChain =
    targetChain !== undefined && chainId !== undefined && chainId !== targetChain.id;

  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="hidden text-muted sm:inline">
        {chain?.name ?? `chain ${chainId}`}
      </span>
      <span className="font-mono">{short(address)}</span>
      {wrongChain && targetChain && (
        <button
          className={`${button} text-accent`}
          onClick={() => switchChain({ chainId: targetChain.id })}
        >
          Switch to {targetChain.name}
        </button>
      )}
      <button className={button} onClick={() => disconnect()}>
        Disconnect
      </button>
    </div>
  );
}
