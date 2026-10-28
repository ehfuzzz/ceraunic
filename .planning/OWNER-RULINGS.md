# Owner rulings — weather-insurance

## 2026-09-30 — Project initialization (GSD discussion, owner answers verbatim where quoted)
- **Venue form:** on-chain protocol + off-chain simulator. **Chain:** HyperEVM testnet (Foundry). No stake is needed for HyperEVM contracts; the 500k HYPE stake applies only to native HyperCore markets (HIP-3/HIP-4), which are out of scope.
- **Done for v1:** paper + working prototype. Pitch pack = deck + live demo + evaluation report + token model; **two versions of the deck** (crypto-native funds, token story leads; fintech/insurtech funds, product story leads).
- **Residual design:** test all designs (per-cell PRISM + nClimGrid, regional factor per station, nearby-station pairs; temperature and rain), let the data pick.
- **Portal:** "deployable web app plus risk/margin/rfq/hedging/onboarding/trading/coverage/elasticity engines".
- **Constraints:** "make this project asap. goal is to get vc investment raise a coin do this project for real cash soon. we dont have to engineer heavy rn just build a prototype"; cloud allowed within the GCP trial; heavy data work on this Mac only.
- **Timing:** "prototype and numbers in under 2 days. we can do it with heavy parallelization". Quota: "Whatever it takes, no cap".
- **Cut order if tight:** POS-connect last-mile and token-memo polish first; keep numbers + testnet demo + deck.
- **Recorder:** "communicate with another agent session called hl mm which already has access to aws boxes and my kalshi. tell it to start this process on a aws box we already have" → relayed 2026-09-30; hl-mm confirmed owner approval 07:45Z and deployment on the Tokyo box to s3://hlmm-reduced-5325/kalshi-weather-books/.
- **Token:** pool capital + governance (junior first-loss tranche of the pool, votes on risk parameters).
- **Residual taker:** house market-maker first; outside LPs later.
- **Onboarding:** "concierge for the first pilots but self serve and pos connect systems should both be built as well. we will help concierge if absolutely needed".
- **Legal posture:** testnet prototype, counsel memo before mainnet.
- **Name:** keep the plain codename `weather-insurance`.
- **Testnet deploy:** owner runs the deploy script (agents hold no funded keys). **POS:** owner creates the Square sandbox app. Both after the window unless pinged earlier; owner 2026-09-30: "if ur waiting on me to do anything do other work in the meantime while i get u the stuff u need".
- **Hedge leg:** build both paths, default = business buys one policy and the house hedges the Kalshi leg; fallback = business buys the ladder itself, venue sells only the overlay.
- **Auction participants:** anyone with a wallet.
- **The ask:** pre-seed, roughly $500k–$1.5M.
- **Notifications:** push notification only, for blocking items and milestones.
- **Demo chain before testnet:** simulated chain backed by the engine API, chain-mode switch, no UI change on flip.

## GSD round 2026-09-30T20:17:43Z (AskUserQuestion, owner answers verbatim in quotes)
- Team line: "Leave the placeholder" — {{TEAM_LINE}} stays on both decks' last slide until the owner writes it.
- Testnet deploy: "Later this week" — demo stays in sim mode; 17-01 parked; status slide keeps "nothing on testnet yet".
- Square sandbox: "Later" — CSV upload + recorded-orders path stays; 17-02 parked.
- Legal route: "Present all three, decide after counsel" — decks show the fork with no lead route; the counsel brief asks the fork question first.
- US-person open-wallet trading of the residual: "Keep open wallets" — the open-auction ruling stands; the memo's hybrid item 4 is NOT adopted; counsel is asked to test it.
- Main Brain Upstash token exposure: "Leave it" — owner accepts; item closed as owner-accepted.

