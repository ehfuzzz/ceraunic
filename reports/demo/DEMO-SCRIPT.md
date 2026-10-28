# Five-minute demo

Link: **https://wi-portal.vercel.app** (engine behind it: https://wi-engine.vercel.app, simulated mode).

Everything below is fake money in a simulated world. The weather is real (NWS daily highs for July 2026) and the
Kalshi prices are real recorded prices, but no money moves, no chain is involved, and nothing is placed at Kalshi.

Before you start: open the link in a fresh browser window. Have the admin token ready (it's `ADMIN_TOKEN` in the
repo's `.env`); you only need it for the last part. Don't advance the clock while looking at the shared world. If
someone does, run `python3 scripts/seed-demo.py` to put it back (takes about 6 seconds).

---

## 0:00 to 0:30. What this is

**Click:** the landing page, then nothing yet.

**Say:** "Small businesses lose sales to the weather, and most of them can't do anything about it. An ice cream
shop has a bad week when it's cool. A bakery has a bad week when it's too hot to turn the ovens on. What we built
is cover that pays out automatically from the public weather record. You don't file a claim. If the day's high at
your weather station crosses the line you picked, the payout lands in your account two days later."

"Most of that risk we pass on to Kalshi, where temperature contracts already trade. The small gap between the
station and your actual block trades in a nightly auction. This is a prototype in a simulated world, so the money
is fake, but the weather and the Kalshi prices are real ones from this July."

## 0:30 to 2:00. Three shops, one hot day

**Click:** go to `https://wi-portal.vercel.app/app/demo?as=chi`. It lands on Policies as the Chicago bakery.

**Say:** "This world was set up with three shops, using a year of their sales. On July 15 each one bought a week
of cover. Then we moved the clock forward three days, so the first covered day, July 16, has settled."

What's on screen, and what it means:

| Shown | Number | What it means |
|---|---|---|
| Cover | Hot days above 90.0 °F, 130 units a day | Pays $13 for every degree above 90 °F at Chicago Midway, up to $130 a day (at 100 °F). |
| Paid | $334.95 | What the bakery paid for 7 days, about $47.85 a day. |
| Most it pays | $910.00 | 7 days × $130. |
| Payout row, 2026-07-16 | 91.0 °F, Final, $13.00 | Midway hit 91 °F, one degree over the line, so it paid 1 × $13. "Final" means the reading can't change anymore. |
| Data version | 0xf5b01cdb…0125fb | A fingerprint of the exact weather release the day settled on, so anyone can check it. |
| Balance | $613.93 test USDC | $1,000 − $334.95 (heat) − $64.12 (rain, below) + $13.00. |

**Say:** "The bakery's sales drop about 1.4% for every degree it gets hotter. That's measured from its own 315 days
of sales before the sim date, not guessed. So its loss is a hot day, and that's what it covers."

"One honest detail: our suggestion tool starts at 75 °F, but in a Chicago July nearly every day is above 75, so that
cover would cost more than it can pay and the engine refuses to sell it. The bakery took the same size at 90 °F."

**Say:** "The bakery also holds a week of rain cover: $20 for every day O'Hare reports rain, July 16 to 22. It settles
on O'Hare because that's the station Kalshi's Chicago rain market uses, so we can back it with one Kalshi 'rain today'
contract per dollar per day. It pays on 0.01 in or more; a trace is no rain, same as Kalshi, so our hedge matches it
exactly. It cost $64.12 for up to $140. July 16 was dry at
O'Hare, so that day paid nothing; the other six are still open. Honest detail: this bakery's own sales go up a little
on wet days, so our tool suggests only $1 a day. We sized it up to show the product."

**Click:** the rain policy (pol_000004) to show the day-by-day table: one row per day, "Dry day", $0.00.

**Click:** go back to `/app/demo`, pick **Fixture Juice Bar Miami**.

**Say:** "Miami, same idea, hot-day cover above 93 °F, 230 units a day. It paid $314.50 for the week and can get up
to $1,610 back. On July 16 Miami Intl hit 97 °F, four degrees over, so it got 4 × $23 = $92.00. Balance $777.50."

**Click:** go back to `/app/demo`, pick **Fixture Scoops Midtown**.

**Say:** "The ice cream shop is the opposite. It sells about 1.9% *more* for every degree hotter, so it loses on
cool days and buys cool-day cover, below 75 °F at Central Park. July 16 was 85 °F in Central Park, so it paid
nothing. That's what the shop wanted: a hot day was a good sales day anyway. It paid $78.12 for the week, and its
balance is $921.88."

"The price here works differently. That week the lowest Kalshi rung was 'below 89 °F', so there's nothing on Kalshi
to hedge a 75 °F line with, and the pool carries that risk itself. The pool prices it from how far the line sits
below the lowest rung: 88 °F costs $21.92 a day, 86 °F costs $11.86, and anything from 85 °F down costs the floor of
$11.16 a day (1¢ per unit plus the usual margin and fee). A line further from the rung is less likely to pay, so it
costs less. That rule is new, and it rests on 60 days of station-gap data, so treat it as a first version."

## 2:00 to 2:45. The auction

**Click:** Trade, then the **cleared** filter, then the row **NYC · RES-LGA-NYC · 2026-07-17**.

**Say:** "This is the leftover risk: how much hotter LaGuardia runs than Central Park on a given day. Each night
there's one auction per pair. Everyone sends orders before 03:00 UTC, then one price is picked for everybody."

| Shown | Number | What it means |
|---|---|---|
| House bid / ask | 65¢ / 73¢ | The pool's standing quote. A unit pays at most $1. 65¢ means the pool thinks LaGuardia runs about 1.5 °F hotter than the park; 73¢ means 2.3 °F. |
| Clearing price | 69¢ (+1.9 °F) | Two traders crossed: one bid 73¢, one offered at 65¢. Both got the same price. |
| Units traded | 20 | 20 units changed hands. The pool took none of it. |
| Conservation check | $13.80 + $6.20 = $20.00 | The buyer locks 69¢ a unit, the seller 31¢. Together that's exactly $1 per unit, so the auction didn't create or lose money. The page recomputes this itself instead of trusting the engine. |

## 2:45 to 3:15. The pool

**Click:** Pool.

**Say:** "Behind every cover there's a pool. The junior part takes losses first and was seeded with $200,000 by the
house. The senior part, $300,000, gets paid first and earns a small fixed share."

| Shown | Number | What it means |
|---|---|---|
| Junior | about $200,221.06 | $200,000 seed plus what three days of premiums, payouts and hedges left behind. |
| Senior | about $300,001.00 | $300,000 plus its share of the premium. |
| Value per share | 1.0000 senior, 1.0011 junior | What one share is worth in test USDC. Both started at 1.00; the chart below shows the same line over time. |
| Senior rate | 0.30% (30 bp) | The senior side's set share of the premium. |
| Utilisation | 2.04% | $10,223.07 of the pool's $500,222 is set aside backing open cover and auction positions. Most of it is still free. |

Skip WI staking; it's not part of this story.

## 3:15 to 4:45. Do it live

**Click:** Onboard. This starts a private world of your own, so the shared one stays put.

1. **Use a demo address.** Name: anything, say "Bakehouse on Archer". Address: `5700 S Cicero Ave, Chicago, IL 60638`.
   Kind of business: **Bakery with a shop**. Save. It says the settlement station is Chicago Midway (KMDW).
2. **Upload sales:** the file `apps/portal/fixtures/square/csv-export.csv`. Pick location **LFIXCHI000002**, send
   400 days. The heat effect comes back at about −1.4% per degree.
3. **Go to Cover.** The suggestion card says hot-day cover above 75 °F and "We can't price this line in this month;
   try a higher line." In a Chicago July the 75 °F line would pay almost every day. **Change the line to 90** and click
   **Get quotes**.
4. Two prices side by side. On the left, we handle the Kalshi side: **$334.95** for up to **$910.00**. On the right,
   you'd buy the Kalshi rungs yourself; at Midway there's no local gap to trade, so there's nothing left for us to
   sell and it shows $0.00.
5. **Add $1,000 test USDC**, then **Buy for $334.95**. The receipt shows the policy id.
6. **Admin:** paste the admin token, set days to **9**, click **Advance**. The clock goes from Jul 15 to Jul 24, 20:00 UTC.
7. **Policies:** all seven days are Final. Midway read 91, 94, 91, 79, 82, 86, 73 °F, so it paid $13 + $52 + $13
   = **$78.00**. Balance: $1,000 − $334.95 + $78.00 = **$743.05**.

**Say:** "Nobody filed anything. Three hot days paid on their own, and the four normal days didn't."

Optional, 30 seconds, rain: on **Cover**, set Weather to **Rainy days**, $20 per wet day, Jul 25 to 31, **Get quotes**.
The left card lists one Kalshi contract per day (the first day at Kalshi's 73¢ ask, later days at O'Hare's recent
wet-day rate) and costs **$65.60** for up to $140; the right card lists the same contracts for you to buy at Kalshi
yourself. Buy it, advance **9** days: O'Hare had measurable rain on Jul 27 and 31, so it pays **$40.00**. Jul 28 was
only a trace, which counts as no rain here and at Kalshi, so it pays nothing.

## 4:45 to 5:00. What's real and what isn't

**Say:** "To be clear about what this is: the weather readings and the Kalshi prices are real ones from July 2026.
The money, the traders and the chain are simulated. We haven't sold this to anyone, and the sales histories are
fixtures we generated, so the elasticity numbers show that the method works, not what a real shop looks like."

---

## What is simulated

- **Money.** Test USDC from a faucet. No real dollars, no wallet needed, no chain. (A testnet mode exists but isn't deployed.)
- **The clock.** A sim clock replaying July 15 to September 30, 2026. It only moves when someone advances it.
- **Kalshi hedges.** Priced and "filled" on paper at recorded Kalshi prices from July 2026. Nothing is placed at Kalshi.
- **The three shops.** Square-style fixture data generated in Phase 12 with a planted weather effect. They're not real businesses.
- **Traders.** The two auction traders and every address are public test accounts.
- **The elasticity priors.** Learned from public bikeshare, transit and taxi data as stand-ins, not retail sales. Advisory only.
- **Real:** the NWS daily highs and rain reports used for settlement (with their data fingerprints), the Kalshi ladders and rain-market prices, and the pricing, auction and pool rules in the engine.

## Numbers in this script

Every number above is either read from `reports/demo/seed-state.json` (written by `scripts/seed-demo.py`) or seen
in the smoke run at the public link (`reports/demo/SMOKE.md`, screenshots in `reports/demo/screenshots/`). To check
the shared world still matches: `python3 scripts/seed-demo.py --check`.
