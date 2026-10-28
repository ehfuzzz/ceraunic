// Typed client for the engine API (Phase 9). The contract is generated:
//   pnpm gen:api  ->  src/lib/engine-schema.d.ts  (from <ENGINE_ORIGIN>/api/v1/openapi.json)
// Method names are the 10-01 facade's; shapes now follow the wire contract.
// Units: money is integer USDC base units with an `E6` suffix (1_000_000 = $1), temperatures are
// tenths of a degree F, rain is hundredths of an inch, days are YYYY-MM-DD, timestamps ISO-8601 Z.
// Requests go to /api/v1/* on this origin; next.config.ts rewrites them to the engine.
import createClient, { type Middleware } from "openapi-fetch";
import { execute, type Execution } from "./execute";
import type { components, paths } from "./engine-schema";

type S = components["schemas"];

export type { Execution, TxRequest } from "./execute";
export type Peril = S["QuoteRequest"]["peril"];
export type HedgePath = S["QuoteRequest"]["path"];
export type Side = S["OrderCreate"]["side"];
export type Tranche = S["DepositRequest"]["tranche"];
export type Health = S["Health"];
export type Config = S["Config"];
export type Business = S["Business"];
export type BusinessCreate = S["BusinessCreate"];
export type SalesRow = S["SalesRow"];
export type SalesSummary = S["SalesSummary"];
export type Elasticity = S["Elasticity"];
export type Recommendation = S["Recommendation"];
export type QuoteRequest = S["QuoteRequest"];
export type Quote = S["Quote"];
export type Rung = S["Rung"];
export type BuyPolicyRequest = S["PolicyCreate"];
export type Policy = S["Policy"];
export type AuctionSummary = S["AuctionSummary"];
export type Auction = S["Auction"];
export type PostOrderRequest = S["OrderCreate"] & { auctionId: string };
export type Order = S["Order"];
export type ClearingResult = S["ClearingResult"];
export type PoolTxRequest = S["DepositRequest"];
export type PoolWithdrawRequest = S["WithdrawRequest"];
export type QueueTicket = S["QueueTicket"];
export type PoolState = S["PoolState"];
export type Position = S["Positions"];
export type Positions = S["Positions"];
export type Settlement = S["Settlement"];
export type Balances = S["Balances"];
export type Problem = S["Problem"];

export class EngineError extends Error {
  constructor(public readonly problem: Problem | { title: string; status: number; code?: string; detail?: string }) {
    super(`${problem.code ?? problem.status}: ${problem.title}${problem.detail ? ` (${problem.detail})` : ""}`);
    this.name = "EngineError";
  }
  get code() {
    return this.problem.code;
  }
}

const WORLD_KEY = "wi.world";
export const worldStore = {
  get: (): string | null => (typeof localStorage === "undefined" ? null : localStorage.getItem(WORLD_KEY)),
  set: (id: string) => typeof localStorage !== "undefined" && localStorage.setItem(WORLD_KEY, id),
};

const idemKey = () => globalThis.crypto.randomUUID();

export function createEngineClient(baseUrl = "") {
  const client = createClient<paths>({ baseUrl });
  const world: Middleware = {
    onRequest({ request }) {
      const id = worldStore.get();
      if (id) request.headers.set("X-WI-World", id);
      return request;
    },
  };
  client.use(world);
  return client;
}

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

export function createApi(client = createEngineClient(process.env.NEXT_PUBLIC_ENGINE_BASE_URL ?? "")) {
  const write = <T>(p: Promise<{ data?: Execution<T>; error?: unknown; response: Response }>) =>
    unwrap(p).then((env) => execute<T>(env));

  return {
    health: () => unwrap(client.GET("/api/v1/health")),
    config: () => unwrap(client.GET("/api/v1/config")),
    /** Sim only. Creates a fresh visitor world and remembers it in localStorage. */
    async newWorld() {
      const w = await unwrap(client.POST("/api/v1/sim/worlds", { body: { template: "demo-5-cities" } }));
      worldStore.set(w.worldId);
      return w;
    },
    advance: (days: number) => unwrap(client.POST("/api/v1/sim/advance", { body: { days } })),
    balances: (address: string) =>
      unwrap(client.GET("/api/v1/accounts/{address}/balances", { params: { path: { address } } })),
    faucet: (address: string, amountE6: number) =>
      write<Balances>(client.POST("/api/v1/faucet", { body: { address, amountE6 } })),

    createBusiness: (body: BusinessCreate) => unwrap(client.POST("/api/v1/businesses", { body })),
    /** Suggested temperature cover; pass "rain" for the wet-day cover sized from the wet-day effect. */
    recommendation: (businessId: string, peril?: "rain") =>
      unwrap(
        client.GET("/api/v1/businesses/{business_id}/recommendation", {
          params: { path: { business_id: businessId }, query: peril ? { peril } : {} },
        }),
      ),
    elasticity: (businessId: string) =>
      unwrap(client.POST("/api/v1/businesses/{business_id}/elasticity", { params: { path: { business_id: businessId } } })),
    uploadSales: (businessId: string, rows: SalesRow[], source: "csv" | "square" | "fixture" = "csv") =>
      unwrap(
        client.POST("/api/v1/businesses/{business_id}/sales", {
          params: { path: { business_id: businessId } },
          body: { source, rows },
        }),
      ),

    quote: (req: QuoteRequest) => unwrap(client.POST("/api/v1/quotes", { body: req })),
    buyPolicy: (req: BuyPolicyRequest) =>
      write<Policy>(client.POST("/api/v1/policies", { body: req, params: { header: { "Idempotency-Key": idemKey() } } })),

    auctions: (query?: { day?: string; status?: "open" | "closed" | "cleared" }) =>
      unwrap(client.GET("/api/v1/auctions", { params: { query } })),
    auction: (auctionId: string) =>
      unwrap(client.GET("/api/v1/auctions/{auction_id}", { params: { path: { auction_id: auctionId } } })),
    postOrder: ({ auctionId, ...body }: PostOrderRequest) =>
      write<Order>(
        client.POST("/api/v1/auctions/{auction_id}/orders", {
          params: { path: { auction_id: auctionId }, header: { "Idempotency-Key": idemKey() } },
          body,
        }),
      ),
    runAuction: (auctionId: string) =>
      write<ClearingResult>(client.POST("/api/v1/auctions/{auction_id}/clear", { params: { path: { auction_id: auctionId } } })),

    pool: () => unwrap(client.GET("/api/v1/pool")),
    poolDeposit: (req: PoolTxRequest) =>
      write<QueueTicket>(client.POST("/api/v1/pool/deposits", { body: req, params: { header: { "Idempotency-Key": idemKey() } } })),
    poolWithdraw: (req: PoolWithdrawRequest) =>
      write<QueueTicket>(client.POST("/api/v1/pool/withdrawals", { body: req, params: { header: { "Idempotency-Key": idemKey() } } })),
    /** Owner only, before the request matures (QueueTicket.epochTs): the escrowed shares go back to the LP. */
    poolWithdrawCancel: (requestId: string, owner: string) =>
      write<QueueTicket>(
        client.POST("/api/v1/pool/withdraw/{request_id}/cancel", {
          params: { path: { request_id: Number(requestId) }, header: { "Idempotency-Key": idemKey() } },
          body: { owner },
        }),
      ),

    positions: (owner: string) => unwrap(client.GET("/api/v1/positions", { params: { query: { owner } } })),
    settlements: (owner: string, range?: { fromDay?: string; toDay?: string }) =>
      unwrap(client.GET("/api/v1/settlements", { params: { query: { owner, ...range } } })),
  };
}

export type EngineApi = ReturnType<typeof createApi>;
export const api: EngineApi = createApi();
