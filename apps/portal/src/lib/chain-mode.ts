// The only place CHAIN_MODE is read.
//   sim     engine API simulates the chain; no wallet needed
//   anvil   local Foundry node at 127.0.0.1:8545
//   testnet HyperEVM testnet

export type ChainMode = "sim" | "anvil" | "testnet";

const MODES: readonly ChainMode[] = ["sim", "anvil", "testnet"];

function parse(raw: string | undefined): ChainMode {
  const value = (raw ?? "sim").trim().toLowerCase();
  if ((MODES as readonly string[]).includes(value)) return value as ChainMode;
  console.warn(`CHAIN_MODE="${raw}" is not one of ${MODES.join(" | ")}; using sim.`);
  return "sim";
}

export const CHAIN_MODE: ChainMode = parse(process.env.CHAIN_MODE);

export const MODE_LABEL: Record<ChainMode, string> = {
  sim: "Simulated chain. No wallet needed.",
  anvil: "Local anvil node.",
  testnet: "HyperEVM testnet.",
};
