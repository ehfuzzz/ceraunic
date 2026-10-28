// Runs an Execution envelope from the engine API (09-RESEARCH Pattern 3).
//   status "done"            -> the engine already applied it (sim, anvil with server-signing): return the result.
//   status "needs_signature" -> anvil/testnet: the browser signs `txs` in order with wagmi, then asks the engine
//                               to read the receipt (POST /api/v1/tx/{hash}/confirm) and resolves the object.
// Guards that protect money: every tx must target the chain of the envelope's mode, the wallet must actually be
// on that chain before we send, a reverted tx stops the sequence (no `buy` after a failed `approve`), and the
// wei value is parsed as an exact integer string, never a float.
import type { Config as WagmiConfig } from "wagmi";
import type { components } from "./engine-schema";

type Schemas = components["schemas"];
export type TxRequest = Schemas["TxRequest"];
export type TxConfirm = Schemas["TxConfirm"];
export type Hex = `0x${string}`;

export interface Execution<T> {
  mode: "sim" | "anvil" | "testnet";
  status: "done" | "needs_signature";
  result?: T | null;
  txs: TxRequest[];
}

/** Chain each mode is allowed to sign on. Sim never signs. */
export const MODE_CHAIN_ID: Record<"anvil" | "testnet", number> = { anvil: 31337, testnet: 998 };

export class NotImplementedError extends Error {
  constructor(what: string) {
    super(`not implemented: ${what}`);
    this.name = "NotImplementedError";
  }
}

export class ExecutionError extends Error {
  constructor(
    message: string,
    public readonly step: number | null,
    public readonly hashes: Hex[],
  ) {
    super(message);
    this.name = "ExecutionError";
  }
}

/** All txs went through, but the caller gave no way to read the resulting object. */
export class SignedNoResultError extends ExecutionError {
  constructor(public readonly confirmation: TxConfirm, hashes: Hex[]) {
    super("Signed and confirmed on chain. Reload to see the result.", null, hashes);
    this.name = "SignedNoResultError";
  }
}

/** The wallet side, injectable so the signing loop can be exercised without a browser wallet. */
export interface Signer {
  isConnected(): boolean;
  chainId(): number | undefined;
  switchChain(chainId: number): Promise<void>;
  send(tx: { to: Hex; data: Hex; value: bigint; chainId: number }): Promise<Hex>;
  waitForReceipt(hash: Hex, chainId: number): Promise<{ status: "success" | "reverted" }>;
  confirm(hash: Hex): Promise<TxConfirm>;
}

export type StepPhase = "switching" | "signing" | "waiting" | "confirming";
export interface Step {
  index: number; // 1-based
  total: number;
  description: string;
  phase: StepPhase;
  hash?: Hex;
}

export interface ExecuteOptions<T> {
  signer?: Signer;
  /** Turns the engine's receipt read into the object the caller wants (e.g. GET the new policy). */
  resolve?: (confirmation: TxConfirm, hashes: Hex[]) => Promise<T>;
  onStep?: (step: Step) => void;
}

const HEX = /^0x[0-9a-fA-F]*$/;
const ADDR = /^0x[0-9a-fA-F]{40}$/;
const WEI = /^\d+$/;

async function postConfirm(hash: Hex): Promise<TxConfirm> {
  const base = process.env.NEXT_PUBLIC_ENGINE_BASE_URL ?? "";
  for (let attempt = 0; attempt < 5; attempt++) {
    const r = await fetch(`${base}/api/v1/tx/${hash}/confirm`, { method: "POST" });
    if (!r.ok) throw new ExecutionError(`the engine could not read tx ${hash} (HTTP ${r.status})`, null, [hash]);
    const c = (await r.json()) as TxConfirm;
    if (c.status !== "pending") return c;
    await new Promise((res) => setTimeout(res, 1000));
  }
  throw new ExecutionError(`tx ${hash} is still pending; check again in a minute`, null, [hash]);
}

/** Signer backed by wagmi/actions and the connected injected wallet. */
export async function wagmiSigner(config?: WagmiConfig): Promise<Signer> {
  const actions = await import("wagmi/actions");
  const cfg = config ?? (await import("./chains")).wagmiConfig;
  return {
    isConnected: () => actions.getAccount(cfg).isConnected,
    chainId: () => actions.getAccount(cfg).chainId,
    switchChain: async (chainId) => {
      await actions.switchChain(cfg, { chainId: chainId as (typeof cfg)["chains"][number]["id"] });
    },
    send: (tx) =>
      actions.sendTransaction(cfg, {
        to: tx.to,
        data: tx.data,
        value: tx.value,
        chainId: tx.chainId as (typeof cfg)["chains"][number]["id"],
      }),
    waitForReceipt: async (hash, chainId) => {
      const r = await actions.waitForTransactionReceipt(cfg, {
        hash,
        chainId: chainId as (typeof cfg)["chains"][number]["id"],
      });
      return { status: r.status };
    },
    confirm: postConfirm,
  };
}

export async function execute<T>(env: Execution<T>, opts: ExecuteOptions<T> = {}): Promise<T> {
  if (env.status === "done") {
    if (env.result == null) throw new Error("engine returned done without a result");
    return env.result;
  }
  if (env.mode === "sim") throw new ExecutionError("the simulated chain never asks for a signature", null, []);
  if (env.txs.length === 0) throw new ExecutionError("the engine asked for a signature but sent no transactions", null, []);

  // Check the whole batch before signing anything.
  const want = MODE_CHAIN_ID[env.mode];
  env.txs.forEach((tx, i) => {
    if (tx.chainId !== want)
      throw new ExecutionError(`step ${i + 1} targets chain ${tx.chainId}, but ${env.mode} is chain ${want}; nothing was signed`, i + 1, []);
    if (!ADDR.test(tx.to) || !HEX.test(tx.data))
      throw new ExecutionError(`step ${i + 1} has a malformed target or calldata; nothing was signed`, i + 1, []);
    if (!WEI.test(tx.value)) throw new ExecutionError(`step ${i + 1} value ${JSON.stringify(tx.value)} is not whole wei; nothing was signed`, i + 1, []);
  });

  const signer = opts.signer ?? (await wagmiSigner());
  if (!signer.isConnected()) throw new ExecutionError("Connect a wallet to sign this.", null, []);

  const hashes: Hex[] = [];
  const total = env.txs.length;
  for (let i = 0; i < total; i++) {
    const tx = env.txs[i];
    const step = (phase: StepPhase, hash?: Hex) => opts.onStep?.({ index: i + 1, total, description: tx.description, phase, hash });
    if (signer.chainId() !== tx.chainId) {
      step("switching");
      await signer.switchChain(tx.chainId);
      if (signer.chainId() !== tx.chainId)
        throw new ExecutionError(`the wallet is not on chain ${tx.chainId}; stopped before step ${i + 1}`, i + 1, hashes);
    }
    step("signing");
    const hash = await signer.send({ to: tx.to as Hex, data: tx.data as Hex, value: BigInt(tx.value), chainId: tx.chainId });
    hashes.push(hash);
    step("waiting", hash);
    const receipt = await signer.waitForReceipt(hash, tx.chainId);
    if (receipt.status !== "success")
      throw new ExecutionError(`step ${i + 1} (${tx.description}) reverted; later steps were not sent`, i + 1, hashes);
  }

  const last = hashes[hashes.length - 1];
  opts.onStep?.({ index: total, total, description: env.txs[total - 1].description, phase: "confirming", hash: last });
  const confirmation = await signer.confirm(last);
  if (confirmation.status !== "confirmed")
    throw new ExecutionError(`the engine reads tx ${last} as ${confirmation.status}`, total, hashes);
  if (!opts.resolve) throw new SignedNoResultError(confirmation, hashes);
  return opts.resolve(confirmation, hashes);
}
