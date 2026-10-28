import { createConfig, http } from "wagmi";
import { injected } from "wagmi/connectors";
import { anvil, hyperliquidEvmTestnet } from "viem/chains";
import type { Chain } from "viem";
import { CHAIN_MODE } from "./chain-mode";

// viem ships hyperliquidEvmTestnet (id 998, HYPE, 18 decimals,
// https://rpc.hyperliquid-testnet.xyz/evm), so we use it as is.
// verify: Phase 8 research (RPC URL, big-block deploy needs, explorer)
export { anvil, hyperliquidEvmTestnet };

// The sim pseudo-chain is not an EVM chain and is never given to wagmi.
export const simChain = {
  kind: "sim",
  name: "Simulated chain",
} as const;

export type Target =
  | { kind: "sim"; name: string }
  | { kind: "evm"; name: string; chain: Chain };

export const TARGET: Target =
  CHAIN_MODE === "sim"
    ? simChain
    : {
        kind: "evm",
        name: CHAIN_MODE === "anvil" ? anvil.name : hyperliquidEvmTestnet.name,
        chain: CHAIN_MODE === "anvil" ? anvil : hyperliquidEvmTestnet,
      };

// Optional override for the active chain's RPC.
const rpcOverride = process.env.NEXT_PUBLIC_RPC_URL || undefined;

function transportFor(chain: Chain) {
  const isTarget = TARGET.kind === "evm" && TARGET.chain.id === chain.id;
  return http(isTarget ? rpcOverride : undefined);
}

// Injected connector only (MetaMask, Rabby). No WalletConnect.
export const wagmiConfig = createConfig({
  chains: [hyperliquidEvmTestnet, anvil],
  connectors: [injected()],
  transports: {
    [hyperliquidEvmTestnet.id]: transportFor(hyperliquidEvmTestnet),
    [anvil.id]: transportFor(anvil),
  },
  ssr: true,
});
