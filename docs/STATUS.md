# Ceraunic — status (2026-10-28)

Nothing is running. No jobs, deploys or cloud boxes are in flight.

## What is built
- **Phases 1–16 are done.** The project plan is in `.planning/ROADMAP.md`. The handoff log is `.planning/HANDOFF.md`; read the last sections.
- **Engine and contracts:** the Python reference engine (`src/wi/`) matches the Foundry contracts exactly (`contracts/`, 41 forge tests). Hardening added a 3-day withdraw claim window and lapse/cancel.
- **Portal:** live in sim mode at https://wi-portal.vercel.app. It offers heat, cool and rain cover; the engine runs at wi-engine.vercel.app with Upstash.
- **Square POS adapter, plus memos:** token/pool memo, legal options memo and evaluation report are in `reports/pitch/` and `reports/EVALUATION.md`.
- **Paper:** `paper/main.pdf`. Every number traces to a file via `paper/NUMBERS.md`.
- **Landing page:** `site/`. Deploy with `wrangler deploy` to the Worker "ceraunic". Apex: a Worker route `ceraunic.com/*` plus a proxied placeholder A record 192.0.2.1. Do not re-add the apex as a custom domain; it broke after Email Routing was turned on. www is a custom domain.

## Results (honest; quote these, don't oversell)
- **Station leg:** HE_cover is about 0.95, but the ladder gives only 0.37 on 2025+. Overround is about 10% (2025+) and 25% (pooled). EWR and TTN cost 2.4–2.7× fair.
- **Temperature residual:** no design clears the +0.10 bar. The best is G1-P at +0.06 on 37 of 37 pairs. Heat ships as the station leg plus RFQ residuals.
- **Rain residual:** G1-P scores +0.229 [0.119, 0.318] on 26 pairs, after the 10-02 PRISM re-pull (`var/phase3-repull/changes.tsv`). Rain does not net across sites (0.003), and Kalshi rain depth is about 300× too thin.
- **Pool:** the junior tranche is wiped in about 1 season in 20. Senior premium is 30 bps of kept margin.
- **Cost stack** (`reports/orfe-t5/COST-STACK.md`): replicating cover on the ladder costs 3.4× burn on the demo covers; tails cost 4–7×. Ladders list 37–39 h before close.
- **Venue census** (`reports/orfe-t5/VENUE-CENSUS.md`): no venue prices a week-ahead single-city cover under 2× burn.
- **CME weather premium redo** (`.planning/research/cme-first-look/REDO.md`, 2026-10-24): inconclusive. No premium is detectable at an MDE of about 78 HDD / 35 CDD. The earlier "trades lean cold" claim is withdrawn, and Kalshi "design 2" stays a research idea.
- Never claim a learned hedge beats having no hedge.

## Open items
1. **Settlement source.** Kalshi's KXHIGHNY series record names The Weather Company as the settlement source, apparently since about 2026-08-17. Phases 1–2 measured against the NWS climate report. The check: compare Kalshi settled values with NWS CLI values for the same days after the change. Needs owner go-ahead.
2. **Deviation 6: tmax 2026-08-01 disc gap.** Run `uv run python scripts/pull_grids.py prism` once, then `uv run python scripts/eval03.py --all`. Compare `reports/eval-03/results.json` before and after, then run `make report` and `python3 scripts/build_decks.py`. Needs the raw PRISM cache rebuilt first if you're on a fresh machine.
3. **Phase 17 (owner-hand):**
   - Team line on the ask slide.
   - Testnet deploy (`contracts/RUNBOOK.md`; needs a mainnet-deposited address for the faucet).
   - Square sandbox token.
   - ≥14-day order-book re-run on the Kalshi weather recorder (S3, owner's AWS account).
4. **Decks:** both pitch decks need slide 14 (`sg`) re-rendered from `scripts/render_decks.py`. The text there now says "+0.23, on all 26 pairs".
5. **Legal:** offshore posture, and whether US persons may trade through open wallets. Counsel memo before any mainnet.

## Working rules
- Pre-register (freeze a PREREG file) before computing any new number. Log deviations in the phase summary.
- Never trade, create accounts or keys, or touch mainnet.
- Cloud work: tag `project=weather-insurance`, compute in the data's region, and keep downloads small.
