# 13 SUMMARY: hosted demo (PORT-04), 2026-09-30. Done, uncommitted.

**Portal: https://wi-portal.vercel.app** (Vercel `wi-portal`, framework nextjs via vercel.json, sim). **Engine: https://wi-engine.vercel.app** (unchanged, demo world re-seeded).

**Shipped**
- `scripts/deploy-portal.sh`: git-less bundle in $TMPDIR (deleted on exit): apps/portal + a standalone lockfile cut from the workspace one + vercel.json pinning nextjs. Checks first: frozen install, local `next build`, fixtures in the Square route trace (16 files), rewrite in routes-manifest. ENGINE_ORIGIN and CHAIN_MODE=sim set via `vercel env add`, never printed; the portal holds no secrets.
- `apps/portal/next.config.ts`: `outputFileTracingIncludes {"/api/pos/square": ["./fixtures/square/**/*"]}`, following the Next 16 output.md docs.
- `scripts/seed-demo.py` (stdlib): resets `demo` (admin); 3 Phase 12 fixture merchants each upload csv-export rows, get elasticity and a recommendation, and buy 7 days; advance 1 day, house-MM tick, 2 traders cross the house quote on auc_RES-LGA-NYC_2026-07-17, advance 2 days. Writes `reports/demo/seed-state.json`; `--check` re-reads the world read-only.
- `reports/demo/DEMO-SCRIPT.md`: five minutes in the owner's voice; the word "insurance" does not appear.
- `scripts/smoke-demo.mjs`: Playwright, channel chrome. Writes `reports/demo/screenshots/01..12.png` and `reports/demo/SMOKE.md`.
- New `/app/demo?as=nyc|chi|mia` page (`src/components/DemoEntry.tsx`): forgets the browser's private world and acts as that seeded owner (public anvil addresses).
- `PoliciesView` shows short vintage hashes (full hash in the tooltip). The 66-character hash was pushing the Payout column off screen at 1440 px.

**Seeded world (clock 2026-07-18T20:00Z)**
- Scoops NYC cool-day <75 °F × 360, $328.16, 07-16 read 85 °F, paid $0. Bakehouse CHI heat >90 °F × 130, $334.95, read 91 °F, paid $13. Juice Bar MIA heat >93 °F × 230, $314.50, read 97 °F, paid $92.
- LGA auction for 07-17: 69¢, 20 units, $13.80 + $6.20 = $20.00. Junior $200,300.68, senior $300,001.24, utilisation 2.01%.

**Verification (commands run)**
- `bash scripts/deploy-portal.sh`: build ok. `/` returned 200; `/api/v1/health` returned `mode sim`; `/api/pos/square` returned fixture mode with 3 locations. Deployed twice, the second time for the hash change.
- `python3 scripts/seed-demo.py`: 45 calls in 5.5 s. Also run against a local uvicorn :8791: same money, beta floats differ at 1e-12.
- `python3 scripts/seed-demo.py --check`: OK, including after both smoke runs.
- `node scripts/smoke-demo.mjs`: **PASS, 13/13 steps, about 13 s** at the public alias. Seeded pages match the manifest. Private-world loop: upload → recommend → quote at 90 °F → buy $334.95 → own order cleared (5 at 73¢) → 7 days settled; balance $742.90 = $661.40 + $81.50 of payouts. A 9-day API rerun gives the script's live number, $743.05.
- `pnpm exec tsc --noEmit` and `pnpm lint`: clean.
- I did not run `PORTAL_URL=… pnpm smoke`: it overwrites the tracked reports/portal screenshots, and smoke-demo covers the same loop plus the auction.

**Deviations**
- The recommended 75 °F line is NO_PRICE for CHI/MIA in July, so the seed keeps the recommended size at 90/93 °F. "One advanced day" became 3 sim days (07-16 markets never open: genesis 14:00 = step time; first settlement at D+2 12:00Z).
- The junior seed and house-MM schedule come from genesis and the clock (checked, not added). Smoke clock moves are API calls on the private world, so no token goes into the browser.

**Still simulated:** money (faucet USDC), the clock, Kalshi fills (on paper at recorded prices), the merchants (fixtures), the traders, the stand-in priors. Real: the NWS highs and vintages, the Kalshi ladders.

**Owner and seat must know**
1. Engine bug (evidence): NYC cool-day quotes cost the same $46.88/day at every line from 75 to 86 °F. The station leg is 0, so the whole price is the tail charge plus risk. The demo script says so plainly.
2. Pool page "Value per share" shows 0.0000 (display bug; the chart shows about 1.00). The coverage card says "up to $0.00 a day" when the recommendation can't be priced. The portal header still says "weather-insurance".
3. Anyone advancing `demo` with the token moves the shared world; re-run `seed-demo.py` to restore it. Private worlds expire after 7 days.
