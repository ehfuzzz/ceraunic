// Reads the committed fixture files. Node only (route handlers run on the nodejs runtime).
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { Params } from "./generate";

export function fixtureDir(): string {
  const cands = [
    process.env.SQUARE_FIXTURE_DIR,
    path.join(process.cwd(), "fixtures/square"),
    path.join(process.cwd(), "apps/portal/fixtures/square"),
  ].filter((x): x is string => !!x);
  for (const c of cands) if (existsSync(path.join(c, "params.json"))) return c;
  throw new Error(`square fixtures not found (looked in ${cands.join(", ")}); run pnpm gen:fixtures`);
}

export interface FixtureBundle {
  params: Params;
  tmax: Map<string, number>; // "STATION|YYYY-MM-DD" -> degF
  locationsWire: unknown;
  catalogPages: { objects: unknown[]; cursor?: string }[];
}

let cache: FixtureBundle | undefined;

export function parseTmaxCsv(text: string): Map<string, number> {
  const m = new Map<string, number>();
  const lines = text.trim().split("\n");
  const head = lines[0].split(",");
  const iD = head.indexOf("date"), iS = head.indexOf("station"), iT = head.indexOf("tmax_f");
  if (iD < 0 || iS < 0 || iT < 0) throw new Error("station-tmax.csv: need date,station,tmax_f columns");
  for (const l of lines.slice(1)) {
    const f = l.split(",");
    const v = Number(f[iT]);
    if (!Number.isFinite(v)) throw new Error(`station-tmax.csv: bad tmax ${l}`);
    m.set(`${f[iS]}|${f[iD]}`, v);
  }
  return m;
}

export function loadFixtures(): FixtureBundle {
  if (cache) return cache;
  const dir = fixtureDir();
  const rd = (f: string) => readFileSync(path.join(dir, f), "utf8");
  cache = {
    params: JSON.parse(rd("params.json")) as Params,
    tmax: parseTmaxCsv(rd("station-tmax.csv")),
    locationsWire: JSON.parse(rd("locations.json")),
    catalogPages: JSON.parse(rd("catalog.json")),
  };
  return cache;
}
