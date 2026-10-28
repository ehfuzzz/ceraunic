// Engine calls the onboard / coverage / policies pages need that api.ts does not wrap (business read,
// policy list and detail, sim clock), plus a buyPolicy that can finish the needs_signature path: after the
// wallet signs, the engine's receipt read names the new policy and we GET it. Same client, world header
// and /api/v1 rewrite as api.ts.
import { api, createEngineClient, EngineError, type BuyPolicyRequest, type Policy, type Problem } from "./api";
import { execute, type Execution, type Step, type TxConfirm } from "./execute";
import type { components } from "./engine-schema";

export type Clock = components["schemas"]["Clock"];

const client = createEngineClient(process.env.NEXT_PUBLIC_ENGINE_BASE_URL ?? "");

async function unwrap<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await p;
  if (error !== undefined || data === undefined) {
    const e = (error ?? {}) as Partial<Problem>;
    throw new EngineError({ title: e.title ?? response.statusText, status: e.status ?? response.status, code: e.code, detail: e.detail ?? undefined });
  }
  return data;
}

/** Reads the policy id out of the engine's receipt read. The 09-03 ledger decides the exact keys; we accept
 *  {kind: "policy", id} or {policyId}. */
export function policyIdFrom(c: TxConfirm): string | null {
  for (const o of c.objects) {
    if (o.policyId) return o.policyId;
    if (o.kind === "policy" && o.id) return o.id;
  }
  return null;
}

export const coreApi = {
  clock: () => unwrap(client.GET("/api/v1/sim/clock")),
  business: (id: string) => unwrap(client.GET("/api/v1/businesses/{business_id}", { params: { path: { business_id: id } } })),
  policies: (holder: string) => unwrap(client.GET("/api/v1/policies", { params: { query: { holder } } })),
  policy: (id: string) => unwrap(client.GET("/api/v1/policies/{policy_id}", { params: { path: { policy_id: id } } })),

  async buyPolicy(req: BuyPolicyRequest, onStep?: (s: Step) => void): Promise<{ policy: Policy; mode: Execution<Policy>["mode"]; hashes: string[] }> {
    const env = await unwrap(
      client.POST("/api/v1/policies", { body: req, params: { header: { "Idempotency-Key": globalThis.crypto.randomUUID() } } }),
    );
    let hashes: string[] = [];
    const policy = await execute<Policy>(env as Execution<Policy>, {
      onStep,
      resolve: async (c, hs) => {
        hashes = hs;
        const id = policyIdFrom(c);
        if (!id) throw new Error("signed, but the engine did not say which policy was created; check the Policies page");
        return coreApi.policy(id);
      },
    });
    return { policy, mode: env.mode, hashes };
  },
};

/** Plain-words message for an engine error the user can act on. */
export function explain(e: unknown): string {
  if (e instanceof EngineError) {
    switch (e.code) {
      case "QUOTE_EXPIRED":
        return "That price has expired or was already used. Get a fresh quote.";
      case "INSUFFICIENT_BALANCE":
        return `Not enough test USDC in this account. ${e.problem.detail ?? ""}`.trim();
      case "WORLD_BUSY":
        return "The demo is busy with another request. Try again in a second.";
      case "RPC_UNAVAILABLE":
        return "The chain is not reachable right now, so this can't be done yet.";
      case "VALIDATION":
        return e.problem.detail ?? e.problem.title;
      case "NOT_FOUND":
        return `${e.problem.title}${e.problem.detail ? ` (${e.problem.detail})` : ""}.`;
      default:
        return e.message;
    }
  }
  return e instanceof Error ? e.message : String(e);
}

export { api };
