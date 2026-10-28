// Calls the trade, pool and admin pages need that api.ts does not wrap: cancel an order, clear with an
// optional admin token, the sim clock, and the admin routes. Everything goes through the same client
// (same world header, same /api/v1 rewrite) and the same Execution envelope as api.ts.
import { createEngineClient, EngineError, type Problem, type ClearingResult, type Order } from "./api";
import { execute, type Execution } from "./execute";
import type { components } from "./engine-schema";

type S = components["schemas"];
export type HouseMm = S["HouseMm"];
export type OracleRow = S["OracleRow"];
export type TickResult = S["TickResult"];
export type AdvanceResult = S["AdvanceResult"];
export type Clock = S["Clock"];
export type StakingView = S["StakingView"];

const client = createEngineClient(process.env.NEXT_PUBLIC_ENGINE_BASE_URL ?? "");

async function unwrap<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await p;
  if (error !== undefined || data === undefined) {
    const e = (error ?? {}) as Partial<Problem>;
    throw new EngineError({
      title: e.title ?? response.statusText,
      status: e.status ?? response.status,
      code: e.code,
      detail: e.detail ?? undefined,
    });
  }
  return data;
}

const write = <T>(p: Promise<{ data?: Execution<T>; error?: unknown; response: Response }>) =>
  unwrap(p).then((env) => execute<T>(env));

const adminHeader = (token: string) => ({ "X-Admin-Token": token });

export const tradingApi = {
  clock: () => unwrap(client.GET("/api/v1/sim/clock")),
  advanceDays: (days: number) => unwrap(client.POST("/api/v1/sim/advance", { body: { days } })),

  cancelOrder: (auctionId: string, orderId: string, trader: string): Promise<Order> =>
    write<Order>(
      client.DELETE("/api/v1/auctions/{auction_id}/orders/{order_id}", {
        params: { path: { auction_id: auctionId, order_id: orderId }, query: { trader } },
      }),
    ),
  /** Permissionless once the public cutoff has passed. An admin token lets sim clear early. */
  clearAuction: (auctionId: string, adminToken?: string | null): Promise<ClearingResult> =>
    write<ClearingResult>(
      client.POST("/api/v1/auctions/{auction_id}/clear", {
        params: { path: { auction_id: auctionId }, header: adminToken ? adminHeader(adminToken) : {} },
      }),
    ),

  houseMm: (token: string) => unwrap(client.GET("/api/v1/admin/house-mm", { params: { header: adminHeader(token) } })),
  houseMmTick: (token: string) =>
    unwrap(client.POST("/api/v1/admin/house-mm/tick", { params: { header: adminHeader(token) }, body: {} })),
  oracle: (token: string) => unwrap(client.GET("/api/v1/admin/oracle", { params: { header: adminHeader(token) } })),
  // WI staking (SPEC 8.7). WI amounts and shares are decimal strings (18-decimal token).
  staking: (owner?: string | null) =>
    unwrap(client.GET("/api/v1/staking", { params: { query: owner ? { owner } : {} } })),
  stake: (owner: string, amountWei: string): Promise<StakingView> =>
    write<StakingView>(client.POST("/api/v1/staking/stake", { body: { owner, amountWei } })),
  unstakeRequest: (owner: string, shares: string): Promise<StakingView> =>
    write<StakingView>(client.POST("/api/v1/staking/unstake-request", { body: { owner, shares } })),
  claimUnstake: (owner: string, requestId: number): Promise<StakingView> =>
    write<StakingView>(client.POST("/api/v1/staking/claim", { body: { owner, requestId } })),

  oracleReport: (token: string, index: string, day: string): Promise<OracleRow> =>
    write<OracleRow>(
      client.POST("/api/v1/admin/oracle/report", { params: { header: adminHeader(token) }, body: { index, day } }),
    ),
};
