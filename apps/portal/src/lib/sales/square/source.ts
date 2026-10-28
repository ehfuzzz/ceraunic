// Square adapter. One code path for fixture and sandbox: always a real SquareClient; in fixture mode
// only the transport (fetch) differs. Never reads the SQUARE_TOKEN env var, never defaults to
// Production (the SDK does both when not told otherwise).
import { SquareClient, SquareEnvironment, type Square } from "square";
import { addDays, enumerateDates, isLocalDate, localDateFn } from "../dates";
import type { FetchDailyRequest, LocalDate, SalesLocation, SalesPanel, SalesSource } from "../types";
import { validatePanel } from "../validate";
import { aggregate, newProv, type AggLocation } from "./aggregate";
import { createFixtureFetch } from "./fixture-fetch";

export const SQUARE_VERSION = "2026-09-16"; // header the pinned square@46.0.0 sends
const SANDBOX_HOST = "connect.squareupsandbox.com";

export type SquareMode = { mode: "fixture" } | { mode: "sandbox"; token: string };

/** Only the route handler calls this. Tests and scripts pass an explicit mode. */
export function resolveSquareMode(env: Record<string, string | undefined> = process.env): SquareMode {
  const token = env.SQUARE_SANDBOX_ACCESS_TOKEN?.trim();
  return token ? { mode: "sandbox", token } : { mode: "fixture" };
}

export function squareClientFor(m: SquareMode, fetchImpl?: typeof fetch): SquareClient {
  if (m.mode === "sandbox") {
    if (new URL(SquareEnvironment.Sandbox).host !== SANDBOX_HOST) throw new Error("refusing to run: sandbox host changed");
    return new SquareClient({
      token: m.token, // explicit: never falls back to SQUARE_TOKEN
      environment: SquareEnvironment.Sandbox, // explicit: the SDK default is Production
      maxRetries: 5,
      timeoutInSeconds: 30,
    });
  }
  return new SquareClient({
    token: "fixture-not-a-token",
    environment: SquareEnvironment.Sandbox, // only a URL prefix the fixture fetch matches on
    fetch: fetchImpl ?? createFixtureFetch().fetch,
  });
}

interface LocLoad { locations: SalesLocation[]; rejected: Array<{ id: string; reason: string }> }

async function loadLocations(client: SquareClient): Promise<LocLoad> {
  const res = await client.locations.list();
  if (res.errors?.length) throw new Error(`ListLocations: ${JSON.stringify(res.errors)}`);
  const locations: SalesLocation[] = [];
  const rejected: LocLoad["rejected"] = [];
  for (const l of res.locations ?? []) {
    const id = l.id ?? "";
    // Never default a missing zone to UTC and never convert currencies: reject, visibly.
    if (!id) { rejected.push({ id: "(none)", reason: "no id" }); continue; }
    if (!l.timezone) { rejected.push({ id, reason: "no timezone" }); continue; }
    try { new Intl.DateTimeFormat("en-CA", { timeZone: l.timezone }); } catch { rejected.push({ id, reason: `invalid timezone ${l.timezone}` }); continue; }
    if (l.currency !== "USD") { rejected.push({ id, reason: `currency ${l.currency ?? "missing"} is not USD` }); continue; }
    locations.push({
      id: `square:${id}`, name: l.name ?? id, timezone: l.timezone, currency: "USD",
      lat: l.coordinates?.latitude ?? undefined, lon: l.coordinates?.longitude ?? undefined,
      postalCode: l.address?.postalCode ?? undefined,
    });
  }
  return { locations, rejected };
}

/** One location, cursor loop. The body is built once (fixed endAt) and resent unchanged each page. */
async function* completedOrders(
  client: SquareClient, squareLocationId: string, startAtUtc: string, endAtUtc: string, onPage: () => void,
): AsyncGenerator<Square.Order> {
  const base = {
    locationIds: [squareLocationId],
    query: {
      filter: {
        stateFilter: { states: ["COMPLETED"] as Square.OrderState[] },
        dateTimeFilter: { closedAt: { startAt: startAtUtc, endAt: endAtUtc } },
      },
      sort: { sortField: "CLOSED_AT" as const, sortOrder: "ASC" as const },
    },
    limit: 1000,
  };
  let cursor: string | undefined;
  do {
    const res = await client.orders.search({ ...base, cursor });
    if (res.errors?.length) throw new Error(`SearchOrders: ${JSON.stringify(res.errors)}`);
    onPage();
    for (const o of res.orders ?? []) yield o;
    cursor = res.cursor ?? undefined; // absent = last page; a short page is NOT the last page
  } while (cursor);
}

/** variation id -> category name (reporting category first, else first category, else Uncategorized). */
async function categoryOf(client: SquareClient): Promise<(variationId?: string | null) => string> {
  const catName = new Map<string, string>();
  const itemRows: Array<[string[], string | undefined]> = [];
  for await (const obj of await client.catalog.list({ types: "ITEM,CATEGORY" })) {
    if (obj.type === "CATEGORY" && obj.id) catName.set(obj.id, obj.categoryData?.name ?? obj.id);
    if (obj.type === "ITEM") {
      itemRows.push([
        (obj.itemData?.variations ?? []).flatMap((v) => (v.id ? [v.id] : [])),
        obj.itemData?.reportingCategory?.id ?? obj.itemData?.categories?.[0]?.id ?? undefined,
      ]);
    }
  }
  const map = new Map<string, string>();
  for (const [vars, cat] of itemRows) for (const v of vars) map.set(v, (cat && catName.get(cat)) || "Uncategorized");
  return (v) => (v && map.get(v)) || "Uncategorized";
}

export function squareSalesSource(opts?: SquareMode, deps?: { fetch?: typeof fetch }): SalesSource {
  const mode: SquareMode = opts ?? resolveSquareMode();
  const client = squareClientFor(mode, deps?.fetch);
  const host = mode.mode === "fixture" ? "fixture" : SANDBOX_HOST;
  let locCache: LocLoad | undefined;
  const locs = async () => (locCache ??= await loadLocations(client));

  return {
    kind: "square",
    mode: mode.mode,
    async listLocations() {
      return (await locs()).locations;
    },
    async fetchDaily(req: FetchDailyRequest): Promise<SalesPanel> {
      if (!isLocalDate(req.start) || !isLocalDate(req.end)) throw new Error("start/end must be YYYY-MM-DD");
      if (req.end < req.start) throw new Error("end before start");
      const { locations: all, rejected } = await locs();
      const chosen = req.locationIds.length
        ? req.locationIds.map((id) => {
            const l = all.find((x) => x.id === id);
            if (!l) throw new Error(`unknown or rejected location ${id}`);
            return l;
          })
        : all;
      if (chosen.length === 0) throw new Error("no usable locations");
      const dates = enumerateDates(req.start, req.end);
      // Padded UTC window: covers every US offset, bucketed locally afterwards. No per-day queries.
      const startAt = `${addDays(req.start, -2)}T00:00:00Z`;
      const endAt = `${addDays(req.end, 2)}T00:00:00Z`;
      const prov = newProv();
      const catOf = req.includeCategories ? await categoryOf(client) : undefined;
      const rows = [];
      for (const l of chosen) {
        const agg: AggLocation = { id: l.id, squareId: l.id.replace(/^square:/, ""), timezone: l.timezone };
        const orders = completedOrders(client, agg.squareId, startAt, endAt, () => { prov.pages++; });
        const collected: Square.Order[] = [];
        for await (const o of orders) { collected.push(o); if (req.signal?.aborted) throw new Error("aborted"); }
        rows.push(...aggregate(collected, agg, dates, prov, catOf));
      }
      rows.sort((a, b) => (a.locationId === b.locationId ? (a.date < b.date ? -1 : 1) : a.locationId < b.locationId ? -1 : 1));
      const pulledAt = new Date().toISOString();
      const panel: SalesPanel = {
        source: "square",
        mode: mode.mode,
        locations: chosen,
        rows,
        start: req.start,
        end: req.end,
        pulledAt,
        provenance: { ...prov, host, squareVersion: SQUARE_VERSION, rejectedLocations: rejected.length },
      };
      if (mode.mode !== "fixture") {
        // Offline POS orders can arrive up to 72 h late: the trailing days are provisional.
        panel.provisionalFrom = addDays(localDateFn(chosen[0].timezone)(pulledAt), -3) as LocalDate;
      }
      const errs = validatePanel(panel);
      if (errs.length) throw new Error(`square panel invalid: ${errs.join("; ")}`);
      return panel;
    },
  };
}
