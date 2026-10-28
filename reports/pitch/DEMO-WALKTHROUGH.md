# Demo walkthrough: presenter notes

*weather-insurance (codename), Phase 16, 30 September 2026. About five minutes, run live from the hosted portal at https://wi-portal.vercel.app in sim mode. Synced to crypto deck slide 12 and fintech deck slides 3 and 11 (both `[shared S-F]`). Source shorthand as in the deck outlines: S09/S10/S11 = `.planning/phases/{09,10,11}-*/…-SUMMARY.md`, E1/E6/J = the results files, M14/M15 = the memos in `reports/pitch/`.*

**Status of this file.** Filled on 30 September 2026 from Phase 13 (`reports/demo/DEMO-SCRIPT.md`, `reports/demo/seed-state.json`, the smoke run in `reports/demo/SMOKE.md`). The numbers below are the live loop in DEMO-SCRIPT (the Chicago bakery fixture, hot-day cover at 90 °F, 2026-07-16 to 07-22), because that's the loop the smoke run checked on screen to the cent. The seeded bakery also holds a rain policy (cue in step 3); it lives in the shared world, not in the private one you start. The fallback screenshots are the Phase 13 ones in `reports/demo/screenshots/`. Don't use the older `reports/portal/` images: they came from the Phase 9-01 fixture API with 2025 dates.

---

## Before you start (two minutes, off-stage)

- Open https://wi-portal.vercel.app in a clean browser profile. Check the badge in the top bar says **sim** and there's no mode-mismatch banner.
- Go to **Admin**, click **New private world**, so you don't move the shared demo world. (The shared world's clock is admin-only; if the page asks for the admin token, the owner types it. It never goes on a slide or in a chat.)
- Keep `apps/portal/fixtures/square/csv-export.csv` on the desktop in case the Square card misbehaves.
- Have the fallback screenshots open in a second window.

## What to say up front (15 seconds)

"Everything here is simulated: test dollars, a simulated clock and a simulated chain. The weather readings and the Kalshi prices in this world are real, replayed from this summer. The businesses are made up. Nothing is on testnet or mainnet yet."

---

## Fintech order (slides 3 and 11): Onboard → Coverage → Policies → Pool → Trade

**1. Onboard (60 s).** Open **Onboard**. Fill in the demo shop: the bakery from DEMO-SCRIPT, `5700 S Cicero Ave, Chicago, IL 60638`, "Bakery with a shop". Show that it picks the settlement station (Chicago Midway, KMDW). At Midway there's no local-difference contract, because the shop sits at the station.
- Click **Connect Square**. Point at the badge: it says the data is recorded Square responses, not a live account. Or upload `csv-export.csv`.
- Pick location LFIXCHI000002, send the sales. Say the day count and date span on screen (400 days).
- On "How weather moves your sales", read the heat and rain numbers and the "give or take" next to them. **Say:** "This is advice, not a promise. When we tested this learning step on public bike and taxi data, it missed our bar. Real shops' sales are what the pilot is for." (E6 `verdicts.T2.*`; `05-SEAT-RULINGS.md` ruling 4.)

**2. Coverage (75 s).** Click **See the cover we suggest**.
- Read the suggestion in one sentence (the bakery sells less on hot days, so it suggests hot-day cover). The card says it can't price the 75 °F line in July; change the line to 90 and click **Get quotes**.
- Show the two paths side by side. **Say:** "On the left the house hedges. On the right you place the station contracts yourself and we sell only the local part."
- Point at the Kalshi rung table and the overround line. **Say:** "Those are the real asks from that morning."
- About the "Expected hedge fit" line (5% on the suggestion card, 7% on the 90 °F quote): **say** "that's the engine's estimate for this demo shop. What we've actually measured is 0.95 for the payout at the station and 0.37 once you count a day-ahead price." (E1 `he_cover.est`, `he_ladder.est`.)
- Click **Add $1,000 test USDC**, then **Buy** ($334.95 for up to $910.00).

**3. Policies (45 s).** On **Admin**, advance the clock enough for every covered day to settle (days go final at D+2 12:00 UTC; for a 7-day cover, advance 10 days). Open **Policies**, then the policy.
- Walk down the day-by-day table: reading from the NWS climate report, data version hash, payout. **Say:** "Nobody files a claim. The reporter records a hash of the exact data release, so anyone can check it later. It is not yet inside the signed report; that is a mainnet item."
- Money check: the balance should equal $1,000 − premium + payouts ($1,000 − $334.95 + $78.00 = $743.05; Midway paid on three hot days). The Phase 10 smoke asserted this to the cent on demo data (S10).
- **Rain cue (optional, 30 s, second window on the shared world).** Open `https://wi-portal.vercel.app/app/demo?as=chi`, which lands on Policies as the Chicago bakery, and open the rain policy. **Say:** "The bakery also bought rain cover: $20 for every wet day at O'Hare, 16 to 22 July. It cost $64.12 for up to $140." Show the day table: July 16 reads Dry day, $0.00, and the other six days are still open. The bakery's balance on that page is $613.93 (that is the shared world, so it won't match the private-world balance above). Don't advance the clock in the shared world.

**4. Pool (30 s).** Open **Pool**. Point at the two layers and read the "junior loses first" line. If you open the withdrawal list, each request has a **Claim by** date, three days after it matures. If nobody claims it in time it lapses: the shares go back and no USDC moves. Before it matures there's a **Cancel** button. **Say:** "The house's own money takes losses first. In a bad summer, about one in twenty by our model, that layer is gone." (J `model.splits.margin_t10.boot_p05_1in20`.) Don't quote any rate or return shown on this page as a result.

**5. Trade (30 s).** Open **Trade**, pick a cleared auction, show the clearing price and the conservation line ("long side plus short side equals units times $1"). **Say:** "This is the auction for the gap between the station and the neighbourhood. On testnet anyone with a wallet can trade here. Whether that survives for US persons is a question for counsel." (M15 §4.)
- If asked whether that local contract is proven: "Not for heat. We tested eight designs against a bar we wrote down first, and none added enough, so heat cover ships as the station part alone and the local part would be quoted one business at a time. For weekly rain, a design on PRISM grid cells passed, tested on all 26 station pairs, but that local rain contract isn't built and would only be quoted by request. The rain cover at the station is built, though, and it sells today." (E03 = `reports/eval-03/results.json`: `verdicts.winner.temperature` = none, best +0.061 against +0.10; `verdicts.winner.rain` = G1-P, +0.229 on `bakeoff.rain.G1-P.n_pairs` = 26, after the 2026-10-02 PRISM re-pull; +0.186 on 19 before.)

## Crypto order (slide 12): Trade → Pool → Onboard/Coverage → Policies

Same steps, reordered, with more time on the chain side.
1. **Trade (75 s).** Auctions list, one per city per day. Place a small order, let it clear (after the cutoff, or with the admin clear in sim), read the conservation check. Mention that the same clearing rule runs in the Solidity contract and matches the engine on 64 test books (S08).
2. **Pool (60 s).** Tranches, utilisation, deposit queue, the withdrawal queue (Claim by column, three-day claim window, Cancel before maturity), the WI staking panel: stake, cooldown, and the rule that a staked position is cut and burned in proportion to junior losses, capped at 30% a day. **Say:** "Stakers earn nothing in this version. What they may earn is for counsel." (M14 §3.)
3. **Onboard and Coverage (90 s).** Steps 1-2 above, shortened. Keep the "advice, not a promise" line and the 0.95 vs 0.37 line.
4. **Policies (45 s).** Step 3 above.
5. Close with: "The same flow runs against the real contracts on a local chain with identical money. The testnet deploy is scripted and waiting for me to run it." (S09.)

---

## Things not to say

- Don't say "we buy Kalshi contracts for you" or "hedged on a regulated exchange". The portal's house-hedge card currently says "We buy the station-temperature ladder at Kalshi to back your cover". Counsel question Q2 asks whether customer wording like that is itself a problem (M15 §3). Say instead: "the house hedges its own book".
- Don't call it insurance. Say cover, policy or payout (M14 note on words).
- Don't quote any hedge fit, rate or return from the demo screens as evidence. The evidence lives on the deck slides with source keys.
- Do sell rain in the demo, but say it the way it works. It's **Rainy days**, in dollars per wet day. It pays on measurable rain, 0.01 in or more, at the city's Kalshi station, and a trace counts as dry, which is the same rule Kalshi's contract settles on. We back each dollar per day with one KXRAIN contract. Don't offer a local rain contract for the neighbourhood: the local (residual) one is by request only and not built.
- Don't say "stake to earn" or talk about yield.

## If the live demo fails

Switch to the screenshots in `reports/demo/screenshots/`, in order: onboard with elasticity (`06-sales-elasticity.png`), quotes (`07-recommend-quotes.png`), policy settled (`11-policy-settled.png`), pool (`04-seeded-pool.png`), cleared auction (`03-seeded-auction-cleared.png`). Say they're from the same hosted demo, taken on 30 September. Their numbers match this file.

## Placeholders in this file

None left. All five (portal link, sales days, hedge fit shown, premium, balance after) were filled on 30 September 2026 from Phase 13.
