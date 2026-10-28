// Server-only. The only place the Square mode is resolved from env (token present => sandbox,
// else fixture). The mode is echoed on every response, and a present token that fails is a hard
// error: it never falls back to demo data.
import { enumerateDates, isLocalDate } from "@/lib/sales/dates";
import { resolveSquareMode, squareSalesSource } from "@/lib/sales/square/source";
import type { LocalDate } from "@/lib/sales/types";

export const runtime = "nodejs";

const MAX_DAYS = 400;

function fail(mode: string, status: number, message: string) {
  return Response.json({ mode, error: message }, { status });
}

/** Never put a token in an error body. */
const safeMsg = (e: unknown, token?: string) => {
  const m = e instanceof Error ? e.message : String(e);
  return token ? m.split(token).join("[redacted]") : m;
};

export async function GET() {
  const m = resolveSquareMode();
  const token = m.mode === "sandbox" ? m.token : undefined;
  try {
    const src = squareSalesSource(m);
    const locations = await src.listLocations();
    // Fixture history ends 2026-09-30; a real sandbox only has "today".
    const defaultEnd = m.mode === "fixture" ? "2026-09-30" : new Date().toISOString().slice(0, 10);
    return Response.json({ mode: m.mode, locations, defaultEnd });
  } catch (e) {
    return fail(m.mode, 502, safeMsg(e, token));
  }
}

export async function POST(req: Request) {
  const m = resolveSquareMode();
  const token = m.mode === "sandbox" ? m.token : undefined;
  let body: { locationIds?: unknown; start?: unknown; end?: unknown; includeCategories?: unknown };
  try {
    body = await req.json();
  } catch {
    return fail(m.mode, 400, "body must be JSON");
  }
  const { locationIds = [], start, end } = body;
  if (!isLocalDate(start) || !isLocalDate(end)) return fail(m.mode, 400, "start and end must be YYYY-MM-DD");
  if (end < start) return fail(m.mode, 400, "end before start");
  if (enumerateDates(start, end).length > MAX_DAYS) return fail(m.mode, 400, `range is capped at ${MAX_DAYS} days`);
  if (!Array.isArray(locationIds) || locationIds.some((x) => typeof x !== "string")) return fail(m.mode, 400, "locationIds must be a string array");
  try {
    const panel = await squareSalesSource(m).fetchDaily({
      locationIds: locationIds as string[],
      start: start as LocalDate,
      end: end as LocalDate,
      includeCategories: body.includeCategories === true,
    });
    return Response.json(panel); // plain numbers only: bigint is converted inside the adapter
  } catch (e) {
    return fail(m.mode, 502, safeMsg(e, token));
  }
}
