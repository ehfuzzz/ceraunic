# 07-01 SUMMARY — protocol spec, interface stubs, units module (2026-09-30)

**Files:** `docs/SPEC.md` (498 lines, §0–18), `contracts/src/interfaces/{IPolicyManager,IBatchAuction,IPoolVault,IOracleAdapter}.sol` (revised), `contracts/src/interfaces/IWIStaking.sol` (new), `src/wi/engine/units.py` (new), `src/wi/engine/__init__.py` (docstring: no heavy imports).
**Verify:** `forge build` passes (solc 0.8.28). `uv run python -c "from wi.engine.units import L; assert L(880,880,940)==0 and L(940,880,940)==1000000"` passes. `grep TODO docs/SPEC.md` hits only §17. Worked examples (payouts, 6-order clearing, pool, haircut, sizing, fees) were computed with units.py and a scratch clearing checked on 3,000 random books. `src/wi/auction/clear.py` (Phase 4, landed mid-run) was read: same rule; the SPEC points at it. `reports/eval-04-05/handoff.json` was not there yet, so α/β/γ/u_max stay placeholders.

**Decisions beyond 07-CONTEXT (the seat should confirm or overrule):**
1. **Quote struct has 8 fields, not 6:** `Quote(market,buyer,isLong,units,premium,fee,expiry,nonce)`. Without `isLong`, puts and digital-below have no side (CONTEXT maps CAPPED_PUT to the short side). Without `fee`, the chain cannot split the treasury cut out of the premium.
2. **The house is the pool's agent, bounded per day:** `fundHouse(day)`, `returnFromHouse(day)` and `writeOffHouse(day)` (after 10 d), with `deployedByDay`. C1 caps reserved + deployed. Hedge P&L goes to junior. Kalshi paper is `@kalshi` in sim; on chain the house wallet plays that role. This keeps sim = anvil parity and makes "pool carries the convexity/tail" true.
3. **Binding:** the premium stays in PolicyManager escrow until `bind(policyId, residualOrderId)`. The chain checks that the order is the house's, cleared, used once and on the same day. boundUnits = mulDiv(units, fill, h). After `bindBy` (D 04:30Z) anyone can bind at full units. New `saleCutoff` at D 02:15Z so the house has 15 min to place residual legs before its 02:30Z cutoff.
4. **Market times are derived from global offsets, never passed in.** marketId excludes the times, so a front-runner could otherwise create a market with bad times. `createMarket` is permissionless for non-auctioned markets.
5. **Oracle config per index `{fetchLag, disputeWindow, voidGrace}`:** CLI 12h/24h, so it finalizes at D+2 12:00Z. nClimGrid 4d12h and PRISM 6d12h. voidGrace is 72h and maxReportAge 24h. `vintageHash` is stored and emitted but **not signed**, because the Report type string is locked. Suggest adding it to the struct in v1.
6. **Residual sizing in scalar units:** h = round(units·δ·2R/(hi−lo)). δ = the mid-implied P(lo<X≤hi) from the ladder, normalized. Rain: h = 2·units, which is an exact hedge. Temperature digitals are overlay/RFQ only.
7. **Station leg:** aggregated per (series, day) and rounded once to CONTRACT_STEP (1 contract). Candle fallback is capped at 30 contracts per rung. Kalshi fees are summed over levels, then ceil'd once per rung order.
8. **Pool details:**
   - SeniorShare has 12 decimals. Junior uses internal non-transferable shares. Deposits are immediate. Premium split is by seniorPremiumBps (2000); junior carries all hedge P&L.
   - Added C2 `jMinBps` (2000) and `minJuniorForSenior`.
   - The haircut is based on the **net junior P&L of a closed day** (`closeDay` needs openPolicies = 0 and deployed = 0). bps = l/(junior + l). Staking shares use the pool's virtual offset.
9. **Fees:**
   - `Quote.fee` = 10 bps of max payout + 10 % of the risk margin, with risk margin = `riskLoadBps` (200) × max payout.
   - Auction and RFQ per-unit fees exist but default to 0, because the chain cannot tell hedgers from traders.
10. **Void:** positions refund exactly `paid`. Bound policies refund keptPremium − keptFee through the waterfall; the treasury fee is kept. Unbound policies refund escrow.
11. **v0 sells floating day-ahead cover** (07-RESEARCH open question 1). Strips run through quoter-called `buyStripDay` with a daily max premium. A fixed-price term is shown as a quote only.
12. **Index registry:**
    - Pairs include EWR-NYC and TTN-NYC (the thin-ladder route) and RAIN twins.
    - R-A and METRO include S, with a 60 % quorum (03-RESEARCH template). Missing inputs lead to void, never a substitute station.
13. **RFQ:**
    - `RfqQuote(requestId,market,maker,taker,takerLong,tick,maxQty,validUntil,nonce)` under the `wi-policy` domain.
    - Maker margin balance in PolicyManager.
    - Cancel via `bumpNonceFloor`.
14. **New file `IWIStaking.sol`.** WIToken becomes fixed supply + ERC20Burnable (Phase 8 edits WIToken.sol; not touched here).
15. **Pause** blocks new risk only. Sim EIP-712 domains use sentinel verifyingContracts (0x…a1 / 0x…a2) on chainId 31337.

**Deviation to record:** CONVENTIONS.md §2 says 03:59Z close; daily markets close 05:00Z ET / 06:00Z CT. Logged in SPEC §18; CONVENTIONS.md itself not edited (seat's call).
**Not done:** WIToken.sol and Deploy.s.sol unchanged (Phase 8 scope); no tests written (none required by this plan).
