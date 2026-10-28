// Unit stub for the needs_signature path of execute.ts. Run: pnpm test:unit
// Only the ways the signing loop could lose money are tested:
//   1. a reverted approve must stop the sequence (no buy is sent, nothing is confirmed);
//   2. a tx aimed at another chain (e.g. mainnet 1) must not be signed at all;
//   3. a wallet that stays on the wrong chain after a switch must not send;
//   4. the wei value must reach the wallet as the exact integer, not a float.
import assert from "node:assert/strict";
import { test } from "node:test";
import { execute, ExecutionError, type Execution, type Hex, type Signer, type TxConfirm } from "../src/lib/execute";

const USDC = "0x5FbDB2315678afecb367f032d93F642f64180aa3";
const PM = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512";

function envelope(overrides: Partial<Execution<{ policyId: string }>["txs"][number]>[] = [{}, {}]): Execution<{ policyId: string }> {
  const base = [
    { chainId: 998, to: USDC, data: "0x095ea7b3", value: "0", description: "MockUSDC.approve" },
    { chainId: 998, to: PM, data: "0xa6f2ae3a", value: "0", description: "PolicyManager.buy" },
  ];
  return { mode: "testnet", status: "needs_signature", result: null, txs: base.map((t, i) => ({ ...t, ...(overrides[i] ?? {}) })) };
}

function stub(opts: { chain?: number; revertAt?: number; switchWorks?: boolean } = {}) {
  let chain = opts.chain ?? 998;
  const sent: { to: string; value: bigint; chainId: number }[] = [];
  const confirmed: Hex[] = [];
  const signer: Signer = {
    isConnected: () => true,
    chainId: () => chain,
    switchChain: async (id) => {
      if (opts.switchWorks !== false) chain = id;
    },
    send: async (tx) => {
      sent.push({ to: tx.to, value: tx.value, chainId: chain });
      return `0x${String(sent.length).padStart(64, "0")}` as Hex;
    },
    waitForReceipt: async () => ({ status: sent.length === opts.revertAt ? "reverted" : "success" }),
    confirm: async (hash): Promise<TxConfirm> => {
      confirmed.push(hash);
      return { status: "confirmed", blockNumber: 7, objects: [{ kind: "policy", id: "pol_000001" }] };
    },
  };
  return { signer, sent, confirmed };
}

test("happy path signs in order and resolves from the last hash", async () => {
  const s = stub({ chain: 1 });
  const out = await execute(envelope(), {
    signer: s.signer,
    resolve: async (c, hashes) => ({ policyId: `${c.objects[0].id}@${hashes.length}` }),
  });
  assert.deepEqual(s.sent.map((t) => [t.to, t.chainId]), [[USDC, 998], [PM, 998]]);
  assert.equal(s.confirmed.length, 1);
  assert.equal(s.confirmed[0], `0x${"2".padStart(64, "0")}`);
  assert.equal(out.policyId, "pol_000001@2");
});

test("a reverted approve stops before buy and never confirms", async () => {
  const s = stub({ revertAt: 1 });
  await assert.rejects(execute(envelope(), { signer: s.signer, resolve: async () => ({ policyId: "x" }) }), (e: ExecutionError) => {
    assert.equal(e.step, 1);
    return true;
  });
  assert.equal(s.sent.length, 1);
  assert.equal(s.confirmed.length, 0);
});

test("a tx aimed at another chain is refused before anything is signed", async () => {
  const s = stub();
  await assert.rejects(execute(envelope([{}, { chainId: 1 }]), { signer: s.signer }), ExecutionError);
  assert.equal(s.sent.length, 0);
});

test("a wallet that stays on the wrong chain does not send", async () => {
  const s = stub({ chain: 1, switchWorks: false });
  await assert.rejects(execute(envelope(), { signer: s.signer }), ExecutionError);
  assert.equal(s.sent.length, 0);
});

test("wei value reaches the wallet exactly; a decimal value is refused", async () => {
  const s = stub();
  await execute(envelope([{ value: "1000000000000000001" }, {}]), { signer: s.signer, resolve: async () => ({ policyId: "x" }) });
  assert.equal(s.sent[0].value, BigInt("1000000000000000001"));
  const s2 = stub();
  await assert.rejects(execute(envelope([{ value: "1e18" }, {}]), { signer: s2.signer }), ExecutionError);
  assert.equal(s2.sent.length, 0);
});
