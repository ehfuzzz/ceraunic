// Emulates exactly the three Square endpoints the adapter calls, from the generator.
// Anything else answers 404 so an unexpected call fails loudly. No network.
import { createHash } from "node:crypto";
import { addDays, dayIndex } from "../dates";
import { loadFixtures } from "./fixture-files";
import { generateDay, type WireOrder } from "./generate";

const FAKE_HOST = "connect.squareupsandbox.com"; // only a URL prefix the SDK builds; we never resolve it

const b64u = (s: string) => Buffer.from(s).toString("base64url");
const unb64u = (s: string) => Buffer.from(s, "base64url").toString("utf8");
const sha = (s: string) => createHash("sha256").update(s).digest("hex");

interface SearchBody {
  location_ids?: string[];
  cursor?: string;
  limit?: number;
  query?: {
    filter?: {
      state_filter?: { states?: string[] };
      date_time_filter?: { closed_at?: { start_at?: string; end_at?: string }; created_at?: unknown; updated_at?: unknown };
    };
    sort?: { sort_field?: string; sort_order?: string };
  };
}

export interface FixtureFetchStats { searchCalls: number; planted429: number; plantedShortPage: number }

/** A fresh instance per run: the planted one-time quirks (one 429, one short page before the end) reset per instance. */
export function createFixtureFetch(): { fetch: typeof fetch; stats: FixtureFetchStats } {
  const stats: FixtureFetchStats = { searchCalls: 0, planted429: 0, plantedShortPage: 0 };
  const perBodyCalls = new Map<string, number>();
  const resultCache = new Map<string, WireOrder[]>(); // body hash (no cursor) -> sorted matching orders

  const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
  const err = (status: number, code: string, detail: string) => json(status, { errors: [{ category: "INVALID_REQUEST_ERROR", code, detail }] });

  function select(body: SearchBody): WireOrder[] {
    const { params, tmax } = loadFixtures();
    const f = body.query?.filter;
    const states = f?.state_filter?.states;
    const c = f?.date_time_filter?.closed_at;
    const startMs = c?.start_at ? Date.parse(c.start_at) : -Infinity;
    const endMs = c?.end_at ? Date.parse(c.end_at) : Infinity;
    const out: WireOrder[] = [];
    for (const locId of body.location_ids ?? []) {
      const loc = params.locations.find((l) => l.id === locId);
      if (!loc) continue;
      // candidate local dates: UTC date range padded by a day each side, clamped to the window
      const lo = Number.isFinite(startMs) ? new Date(startMs).toISOString().slice(0, 10) : params.window.start;
      const hi = Number.isFinite(endMs) ? new Date(endMs).toISOString().slice(0, 10) : params.window.end;
      let d = addDays(lo, -1) < params.window.start ? params.window.start : addDays(lo, -1);
      const last = addDays(hi, 1) > params.window.end ? params.window.end : addDays(hi, 1);
      for (; dayIndex(d) <= dayIndex(last); d = addDays(d, 1)) {
        const t = tmax.get(`${loc.station}|${d}`);
        if (t === undefined) throw new Error(`no tmax for ${loc.station} ${d}`);
        for (const o of generateDay(params, loc, d, t).orders) {
          if (states && !states.includes(o.state)) continue;
          if (c) {
            if (!o.closed_at) continue; // OPEN orders have no closed_at; a closed_at filter excludes them
            const ms = Date.parse(o.closed_at);
            if (ms < startMs || ms > endMs) continue;
          }
          out.push(o);
        }
      }
    }
    const asc = body.query?.sort?.sort_order === "ASC";
    out.sort((a, b) => {
      const ta = Date.parse(a.closed_at ?? a.created_at), tb = Date.parse(b.closed_at ?? b.created_at);
      const k = ta !== tb ? ta - tb : a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
      return asc ? k : -k;
    });
    return out;
  }

  const fixtureFetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : (input as Request).url);
    const method = (init?.method ?? "GET").toUpperCase();
    if (url.host !== FAKE_HOST) return json(404, { errors: [{ code: "NOT_FOUND", detail: `fixture fetch only serves ${FAKE_HOST}` }] });
    const { locationsWire, catalogPages } = loadFixtures();

    if (url.pathname === "/v2/locations" && method === "GET") return json(200, locationsWire);
    if (url.pathname === "/v2/catalog/list" && method === "GET") {
      const cur = url.searchParams.get("cursor");
      return json(200, cur === "CATALOGPAGE2" ? catalogPages[1] : catalogPages[0]);
    }
    if (url.pathname !== "/v2/orders/search" || method !== "POST") return json(404, { errors: [{ code: "NOT_FOUND" }] });

    stats.searchCalls++;
    const body = JSON.parse(String(init?.body ?? "{}")) as SearchBody;
    // Square's own rules
    if ((body.location_ids?.length ?? 0) > 10) return err(400, "INVALID_VALUE", "location_ids: at most 10");
    if ((body.location_ids?.length ?? 0) === 0) return err(400, "MISSING_REQUIRED_PARAMETER", "location_ids required");
    const limit = body.limit ?? 500;
    if (limit < 1 || limit > 1000) return err(400, "INVALID_VALUE", "limit must be 1..1000");
    const f = body.query?.filter;
    const sortField = body.query?.sort?.sort_field;
    if (f?.date_time_filter?.closed_at && sortField !== "CLOSED_AT") return err(400, "INVALID_VALUE", "a closed_at filter requires sort_field CLOSED_AT");
    if (sortField === "CLOSED_AT" && !f?.state_filter?.states?.length) return err(400, "INVALID_VALUE", "CLOSED_AT sort requires a state_filter");

    const { cursor, ...rest } = body;
    const h = sha(JSON.stringify(rest));
    let offset = 0;
    if (cursor) {
      let c: { h: string; o: number };
      try { c = JSON.parse(unb64u(cursor)); } catch { return err(400, "INVALID_CURSOR", "bad cursor"); }
      if (c.h !== h) return err(400, "INVALID_CURSOR", "cursor must be used with the original query");
      offset = c.o;
    }
    const n = (perBodyCalls.get(h) ?? 0) + 1;
    perBodyCalls.set(h, n);

    // planted quirk 1: one 429 (global, once) on the second request of a query
    if (n === 2 && stats.planted429 === 0) {
      stats.planted429++;
      return json(429, { errors: [{ category: "RATE_LIMIT_ERROR", code: "RATE_LIMITED", detail: "planted by fixture fetch" }] }, { "retry-after": "1" });
    }
    let all = resultCache.get(h);
    if (!all) {
      all = select(body);
      resultCache.clear(); // keep one query's results in memory at a time
      resultCache.set(h, all);
    }
    // planted quirk 2: one short page that is not the last (global, once; armed from the third request on)
    let take = limit;
    if (n >= 3 && stats.plantedShortPage === 0 && offset + Math.floor(limit / 2) < all.length && all.length - offset > limit) {
      take = Math.floor(limit / 2);
      stats.plantedShortPage++;
    }
    const page = all.slice(offset, offset + take);
    const next = offset + take < all.length ? b64u(JSON.stringify({ h, o: offset + take })) : undefined;
    return json(200, next ? { orders: page, cursor: next } : page.length ? { orders: page } : {});
  }) as typeof fetch;

  return { fetch: fixtureFetch, stats };
}
