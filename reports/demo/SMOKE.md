# Hosted demo smoke

Run 2026-09-30T19:34:09Z against https://wi-portal.vercel.app with `node scripts/smoke-demo.mjs` (installed Chrome, headless, 1440x900).
Result: **PASS**, 15/15 steps, 17.9 s end to end.
Deploys under test (after 09-LAPSE): engine `wi-engine-dznmgyl45`, portal `wi-portal-pf69u3it9`. Screenshot 04 (Pool board) retaken; the rest kept from the earlier run, numbers unchanged.

| Step | Seconds | Result | What it saw |
|---|---:|---|---|
| health: portal alias proxies the engine in sim mode | 0.1 | ok | mode sim, demo clock 2026-07-18T20:00:00Z |
| A1 seeded world: Chicago bakery policy, first day paid | 1.1 | ok | pol_000002: paid $13.00 on 2026-07-16, wallet $613.93 |
| A1r seeded world: the bakery's 7-day rain cover (O'Hare) | 0.6 | ok | pol_000004: $20/wet day 2026-07-16..2026-07-22, premium $64.12, 1 day settled (2026-07-16 dry $0.00) |
| A1 seeded world: Fixture Scoops Midtown | 1.3 | ok | paid $0.00, wallet $921.88 |
| A1 seeded world: Fixture Juice Bar Miami | 0.4 | ok | paid $92.00, wallet $777.50 |
| A2 seeded world: the cleared LaGuardia auction | 0.6 | ok | auc_RES-LGA-NYC_2026-07-17: 69c, 20 units, conservation ok |
| A3 seeded world: pool | 0.5 | ok | junior $200,221.06, senior $300,001.00 |
| B1 onboard: business in Chicago (private world) | 0.8 | ok | world w_3514a36e8f6b |
| B2 upload: fixture CSV -> sales summary -> elasticity | 0.8 | ok | 400 days sent; heat effect -1.4% |
| B3 recommend + quote (line raised to 90 F) | 1.1 | ok | recommendation: Hot days cover We can't price this line in this month; try a higher line. Pays when the hi...; house-hedge total $334.95 |
| B4 buy (house-hedge path) | 1.3 | ok | pol_000001, premium $334.95, balance $665.05 |
| B5 auction: order on tomorrow's LaGuardia auction, clock past the cutoff, cleared | 2.1 | ok | clock 2026-07-16T20:00:00Z -> +1 day; auc_RES-LGA-NYC_2026-07-17 cleared at 73c, 5 units (pool took 5), ours 5; balance after clear $661.40 |
| B6 settle: clock past D+2 of the last covered day | 1.5 | ok | clock 2026-07-24T20:00:00Z; 8 payout rows (7 policy days + 1 auction position) = $81.50; balance $742.90 = $661.40 + $81.50 |
| B8 rain cover: quote Rainy days, buy $20 per wet day for 7 days, clock past D+2, wet days paid | 2.7 | ok | pol_000002: premium $65.60; wet days 2026-07-27, 2026-07-31 paid $40.00; balance $717.30 = $742.90 - $65.60 + $40.00 |
| B7 Square card (fixture mode) answers on the hosted route | 2.6 | ok | GET 3 locations; POST 30-day pull ok (9805 bytes) |

Screenshots: `reports/demo/screenshots/` (full page, light scheme).
Part A reads the shared `demo` world seeded by `scripts/seed-demo.py` and compares against `reports/demo/seed-state.json`.
Part B runs in a fresh private world, so it never moves the shared demo clock. Clock moves in part B are API calls
(`POST /api/v1/sim/advance` on the portal origin); in the live demo the owner uses the Admin page instead.

Rain step (B8): pol_000002, $20 per wet day at O'Hare, premium $65.60; 2 of 7 days wet (2026-07-27, 2026-07-31), paid $40.00; first contract row: 2026-07-25 KXRAIN-26JUL25-CHI 20 73¢ Kalshi ask.
