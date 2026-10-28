import type { NextConfig } from "next";

// The engine API lives at ENGINE_ORIGIN (a production alias, never a per-deployment URL).
// The browser only ever sees this origin: /api/v1/* is proxied to the engine.
// Local dev: `uvicorn wi.api.app:app --port 8787` from the repo root.
const ENGINE_ORIGIN = process.env.ENGINE_ORIGIN ?? "http://127.0.0.1:8787";

const nextConfig: NextConfig = {
  // CHAIN_MODE is read in src/lib/chain-mode.ts only. Inline it so the
  // browser bundle sees the same value the server does.
  env: {
    CHAIN_MODE: process.env.CHAIN_MODE ?? "sim",
  },
  // The Square card's route reads the committed fixtures with fs at runtime (src/lib/sales/square/fixture-files.ts).
  // Tracing cannot follow those dynamic paths, so ship the folder with that route (hosted demo, Phase 13).
  outputFileTracingIncludes: {
    "/api/pos/square": ["./fixtures/square/**/*"],
  },
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${ENGINE_ORIGIN}/api/v1/:path*` }];
  },
};

export default nextConfig;
