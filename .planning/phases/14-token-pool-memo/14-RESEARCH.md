# Phase 14: Token + pool economics memo - Research

**Researched:** 2026-09-30
**Domain:** Tokenised first-loss capital for a parametric weather pool; 2025-2026 pre-seed comparables; US regulatory facts handed to Phase 15 (facts, not advice)
**Confidence:** MEDIUM overall. Precedent mechanics are HIGH (protocol docs, SEC primary texts). Comparables are LOW-MEDIUM because seed valuations are almost never disclosed. Uses-of-funds ranges are LOW-MEDIUM (audit cost sourced; counsel and team costs are estimates to validate with quotes).

## Summary

This research covers what the Phase 14 memo needs before the Phase 4 numbers land: how twelve insurance and credit protocols used a token or staked capital as first-loss money and what broke, what 2025-2026 seed rounds and token splits look like, what US regulators have said about tokens, staking and tranches, and what $500k / $1M / $1.5M buys. The owner ruling is fixed: the token is the pool's junior first-loss capital and governs risk parameters. The question here is how to implement that ruling without repeating the failures on record.

The evidence points one way. The two largest protocols that kept first-loss money in their own token, and would have had to sell it to cover dollar losses, both moved off the design: Aave replaced its AAVE-backed Safety Module with staked aTokens (Umbrella, activated 5 Jun 2025) because "the sell pressure of the slashing itself will circularly reduce the coverage", and Maple v1's first-loss was a 50/50 MPL-USDC pool that informed stakers withdrew before the Dec 2022 Orthogonal default. The designs that lasted keep claim-paying money in the currency of the claim (Ensuro's USDC junior/senior eTokens, Centrifuge TIN/DROP, Hyperliquid's USDC HLP vault), or make the token a claim on pool assets and burn stakers' tokens while the pool pays in its own assets (Nexus Mutual, more than $18.5M paid since 2019). The other repeat failures: withdrawable first-loss that runs before a known loss; correlated tails priced as independent (InsurAce paid about $11.7M on about $94k of UST premiums); claims decided by token votes (Unslashed/Kleros; Nexus moved to expert claims in v3); pool money parked in outside yield (Sherlock lost about $4M in Maple's Orthogonal pool); emissions and mint bugs (Cover 2020, Resolv 2026); and tranches treated as legally neutral (BarnBridge settled with the SEC in Dec 2023 for selling senior/junior tranches as unregistered securities).

Weather adds a twist the crypto precedents don't have: losses are forecast days ahead. Any stake or deposit that can leave inside the forecast horizon plus the settlement/revision window will leave right before a heatwave. Lock-ups must come from the weather calendar, not from DeFi defaults. And one regulatory fact matters more than any other for the token: the SEC/CFTC joint release of 17 Mar 2026 says a "digital commodity does not have intrinsic economic properties or rights, such as generating a passive yield or conveying rights to future income" (p. 14). A token whose stakers earn the pool's underwriting income sits outside that definition on its face. Phase 15 has to rule on that before the memo promises stakers any cash flow.

**Primary recommendation:** Keep every dollar that pays a claim in USDC. Implement the ruling as "the token is how you own the junior layer": a protocol-owned USDC junior layer (the house seed from the raise) sits behind the premium reserve and in front of senior stablecoin LPs; staked WI carries the vote and is cut pro-rata (burned, never sold) when the junior layer loses money, capped per event; what stakers receive in return (USDC income vs buyback) is left for Phase 15. No emissions, no voting on claims, bounded and timelocked parameters, unstake/withdraw delays longer than the forecast horizon plus the settlement window. The pilot needs none of this: until the token exists, the junior layer is just the house seed in USDC.

## Scope and locked inputs

**Locked (OWNER-RULINGS 2026-09-30, PROJECT.md):**
- Token = junior first-loss capital of the pool + governance over risk parameters. Senior tranche = stablecoin.
- House market-maker seeds the pool first; outside LPs later.
- Pre-seed ask roughly $500k-$1.5M from crypto-native funds; token launch later. Codename `weather-insurance` / `WI`.
- Testnet only; nothing real before counsel (Phase 15). Residual auctions open to any wallet.
- Memo in the owner's voice (memory `owner-writing-style`; banned: ecosystem, flywheel, wedge, unlock, robust, seamlessly, leveraging, "at scale", "positioned to", "the future of", ad fragments).
- Cut order: token-memo polish goes before numbers, demo and deck.

**Handoff this research creates for Phase 7/8 (planner: pass to the SPEC.md author, 07-01):** `contracts/src/interfaces/IPoolVault.sol` leaves open "whether the prototype takes USDC or WI" for junior deposits, and `contracts/src/WIToken.sol` is owner-mintable with the vault expected to become minter. Recommendation: junior deposit asset = USDC; WI is a separate staking position with a pro-rata, burn-only haircut; WI moves to fixed supply (no mint role anywhere, burn-only from the staking module) before it carries value. Phase 8 should not pick this on its own.

**Out of scope:** legal conclusions (Phase 15), the capital numbers (Phase 4), unit economics (Phase 5), deck copy (Phase 16).

## Standard Stack

For a memo phase the "stack" is the set of reference mechanisms the memo builds on, the contract primitives Phase 7/8 use to implement them, and the data sources for comparables.

### Core mechanisms (cite these; do not invent new ones)

| Mechanism | Reference implementation | Use in our design | Why this one |
|-----------|-------------------------|-------------------|--------------|
| Loss waterfall: premiums -> junior -> senior | Ensuro: won-premium pool, active-premium pool, junior SCR, senior SCR (senior sized to a 99.5% level) | Premium reserve pays first, then protocol-owned junior USDC, then senior LPs | Only on-chain protocol running junior/senior tranches for parametric-style risk (flight delay, cargo, CFAR) with licensed partners |
| Halt when the junior buffer is thin | Centrifuge Tinlake minimum TIN ratio (new senior issuance stops when breached); Ensuro `maxUtilizationRatio` | Minimum junior ratio + utilisation cap; breach halts new policies and senior deposits | Automatic, no vote |
| Stakers' tokens burned on loss; claim paid from pool assets | Nexus Mutual staking pools ("amount of NXM burned is the equivalent of the paid claim amount") | Staked WI cut pro-rata to the junior layer's loss; USDC pays the claim | Token takes the first hit without a market sale |
| Protocol-owned first loss ahead of stakers | Aave Umbrella offset ("the Aave DAO covers the first 100,000 USDT of bad debt before any staker assets are affected") | Protocol-owned junior USDC is the first money after premiums | Precedent for treasury capital sitting first |
| Rule-based slashing, no governance vote | Aave Umbrella ("Slashing is triggered automatically ... when a deficit ... exceeds the configured offset"); Risk Harbor parametric payouts | Haircut computed by the vault from realised loss; payouts from the oracle index | Removes the vote-on-your-own-loss conflict |
| Cooldown + unstake window; cooling-down stake stays at risk | Aave Umbrella: 20-day cooldown, 2-day window, "During cooldown ... funds remain slashable"; Nexus 91-day stake tranches; Sherlock 6/12-month locks; Ensuro locked SCR | Delays set from forecast horizon + tenor + settlement/revision window | Stops the run-before-loss seen at Maple |
| Token value from revenue, not emissions | Maple MIP-019 (31 Oct 2025, >91% yes: ended stSYRUP rewards; 25% of revenue to a buyback fund) | Treasury share of margin goes to the junior layer until target, then to whatever Phase 15 allows (buyback or distribution) | 2025-2026 norm |

### Supporting (contract primitives for Phase 7/8)

| Library | Version | Purpose | When to use |
|---------|---------|---------|-------------|
| OpenZeppelin `ERC4626` | v5.7.0 (vendored per contracts/README.md) | Senior and junior share accounting | Both tranches; keep the virtual-offset protection against the first-depositor inflation attack (Aave's Umbrella StakeTokens are also ERC4626) |
| OpenZeppelin `ERC20Votes` + `Governor` + `TimelockController` | v5.7.0 | Staked-WI voting with a delay | Bounded parameter changes only |
| OpenZeppelin `VestingWallet` | v5.7.0 | Team/investor vesting | Token launch only; not in the prototype |
| Safe multisig | current | Guardian: pause new policies/auctions, never move funds | From testnet onward |

### Data sources for comparables

| Source | What for | Confidence |
|--------|----------|------------|
| DefiLlama Raises, Cryptorank deals | Round sizes, leads, dates | MEDIUM (valuations rarely disclosed) |
| Galaxy Research quarterly VC report | Market totals, stage mix | MEDIUM |
| Tokenomist / DefiLlama unlocks | Actual allocation and vesting schedules | MEDIUM |
| Blockworks Token Transparency Framework template | Disclosure checklist for the eventual launch | MEDIUM |

### Alternatives considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| USDC junior + staked-WI pro-rata haircut (recommended, "Option D") | Staked WI as the only junior, sold to pay losses (Aave Safety Module v1, Maple v1 pool cover) | Loss-currency mismatch; forced sale of a thin new token on the day of the loss; needs a WI price oracle; Aave and Maple both moved off it |
| | Separate outside-LP junior USDC vault, WI only governs (Ensuro junior eToken, Centrifuge TIN, Resolv RLP) | Cleanest capital, but WI loses its first-loss role (breaks the ruling) and governance sits with people who don't eat the loss. Keep as a later second junior class |
| | NXM-style token minted/redeemed against the pool at book value | Most literal reading of the ruling, six-year record; but free team/investor allocations dilute book value, and redemptions froze when capital fell below requirement (pre-2023 Nexus) |
| | Maker-style dilution backstop (mint and auction WI if the junior is exhausted) | Worked once (Mar 2020, 5.3M DAI raised, Paradigm won 68% of auctions); needs deep buyers a new token won't have. Document as last resort only |

## Research Q1: Precedents - how the token or staked capital absorbed losses

Status is as of the source date. "Conf." = confidence.

| Protocol | First-loss asset / token role | How a loss hits it | Where yield comes from | Lock-up | What went wrong | Lesson for us | Conf. |
|----------|------------------------------|--------------------|-----------------------|---------|-----------------|---------------|-------|
| **Nexus Mutual** (2019-) | NXM is the mutual's capital: book value = capital pool / NXM supply. Minimum capital MCR = total active cover / 4.8 (about 21 cents per $1 of cover). Members stake NXM into underwriting pools | Claim paid from the capital pool (ETH/stables); staked NXM of the pool that wrote the cover burned equal to the claim | 50% of each cover fee minted as NXM to stakers; investment returns ($3.2M in 2025); RAMM spread ($5.6M+ in 2025); 2025 cover fees $5.7M vs claims $370k | 91-day tranches, 91 days to about 2 years | Bonding-curve era: redemptions blocked when MCR% < 100% and capped at 5% of MCR per tx; holders traded wNXM (no-KYC wrapper) instead. RAMM replaced the curve Nov 2023. Claims: bZx claims denied, then reversed after the post-mortem; UST depeg declined as out of scope (secondary). v3 moved claims from stake-weighted votes to a permissioned expert panel (NMPIP-261) | Token-as-pool-equity works when the token is backed by pool assets and payouts come from those assets. Stakers voting on claims that burn their own stake is a conflict; Nexus dropped it | HIGH (docs; Nexus blog 15 Jan 2026) |
| **Sherlock** (2021-) | USDC stakers are first loss; SHER is reward/governance | Up to about half of staked USDC usable per payout | Premiums (about 3% of cover/yr) + staker USDC deployed to yield + SHER; about 19%/yr paid | Fixed 6- or 12-month positions (NFT receipts) | Euler (Mar 2023): $4.5M payout; pool fell from $30M (late 2021) to $2.9M; some stakers lost about 70%. Also lost about $4M because staker USDC sat in Maple's Orthogonal pool. Co-founder: payments "have not been nearly enough to make up for the loss". Now an audit firm; "Sherlock Shield" cover up to $500k tied to its audits | One event can exceed the pool; premiums too low for the tail; never invest the pool in outside yield | MEDIUM (DL News; Sherlock docs) |
| **Maple** v1 (2021-22) | 50/50 MPL-USDC Balancer LP staked as "pool cover"; providers earned 10% of interest + MPL | Cover LP liquidated on default | Borrower interest + MPL emissions | Unstake cooldown | Orthogonal defaulted on $36M (Dec 2022). Informed stakers withdrew pool cover beforehand; M11 pools' cover covered "only a few percent" of bad debt | First-loss that can leave will leave before a known loss; half-own-token cover means selling your token into the crash | HIGH (The Block, CoinDesk, Forgd) |
| **Maple** v2 / SYRUP (2022-) | Pool-delegate cover posted by the credit manager, drawn automatically, capped max liquidation %; SYRUP staking ended | Cover drawn before lenders | Borrower interest; token value via buybacks | n/a | MIP-019 (voted 28-31 Oct 2025, >91% yes) ended stSYRUP rewards from Nov 2025; 25% of revenue funds buybacks. About $4B AUM, about $1M/month fees | Staking rewards gave way to buybacks from real revenue | MEDIUM (crypto.news) |
| **Ondo** v1 vaults (2021-22) | Senior fixed hurdle; junior takes all excess and all shortfall | Junior absorbs AMM LP losses | Uniswap LP fees | Fixed vault term | Sunset 2022 as DeFi yields compressed, after about $210M of total liquidity; pivoted to tokenised Treasuries | Tranching is easy to code; junior demand needs a real excess return | MEDIUM (Ondo docs) |
| **Risk Harbor** (2021-) | Underwriters' stablecoins; parametric, no claims vote | Automatic payout when Chainlink UST < $0.95 (about 2 blocks) | Premiums | Pool terms | Paid about $2.43M (UST + OneUNI depegs) as designed. Now about $38k TVL, "technically functional, commercially dead" | Parametric payout works; distribution is what killed it | MEDIUM (OpenCover; secondary tracker for TVL) |
| **Ensuro** (2021-) | Junior and senior eTokens, both USDC; not a governance token | Won premiums -> active premiums -> junior SCR -> senior SCR; internal loans between pools | Premiums + interest on locked SCR | Locked SCR not withdrawable; `maxUtilizationRatio` / `minUtilizationRatio`; senior "80% withdrawable in under three months" | No public blow-up found. Reports senior return 25.2% (May 2024-May 2025, self-reported) at about 90% utilisation; partners Otonomi, Koala, Spot | Closest template for our waterfall and caps. Its first-loss is stablecoin, not a token, and licensed partners front the policies | HIGH mechanics; LOW returns |
| **Neptune Mutual** (2022-24) | Stablecoin cover pools; NPM staked for incident reporting/governance | Parametric pool payouts | Premiums + NPM gauge emissions | Pool terms | Closure announced about 28 Jun 2024: emergency withdrawal returned LP funds, policyholder refunds, unused backer funds returned, code open-sourced. Stated reason: couldn't meet the metrics to list NPM on top-tier exchanges | A token whose purpose depends on exchange listings is fragile; contracts should support a clean wind-down | MEDIUM (Neptune statement via search; date from X post id) |
| **Etherisc** (2017-) | DIP staked to activate stablecoin risk "bundles" (1,000 DIP activated 100 USDT; min 5,000 DIP per bundle) | Bundle stablecoin pays; DIP is a bond | Premium fee + DIP rewards (12.5-15%/yr) | Bundle life | No large loss found; DIP rewards are emissions. Real products run through licensed partners (ACRE Africa crop cover, about 17-22k Kenyan farmers; FlightDelay relaunched on Base Feb 2025) | Token-gated stablecoin capital is a precedented hybrid; the gate did not create demand | MEDIUM (Etherisc docs/blog) |
| **Nayms -> OnRe** (2022-) | Bermuda DABA + Innovative General Business insurer licences (2022). NAYM governance token sold to capitalise a liquidity facility. OnRe (rebrand, May 2025) issues ONe backed by a reinsurance pool with sUSDe collateral | Reinsurance losses hit the pool behind ONe | Premiums + sUSDe yield + ONRE incentives ("over 30% in bull markets and around 8% in bear") | KYC to mint; secondary AMM pool open without KYC | First Base product was an industry-loss warranty on Florida weather catastrophe (Jan 2024). Full restructure into OnRe; $5M Series A May 2026 (secondary) | A regulated wrapper route exists for weather risk; headline yields that include token incentives are what our memo must not do | MEDIUM |
| **InsurAce** (2021-) | Stakers' capital pool + INSUR | Pool pays approved claims | Premiums + INSUR mining | Staking terms | UST depeg (May 2022): about $11.7M paid to 155 holders on about $94k of UST premiums (124x). Shortened the claims window after the collapse; staker plan to cut staker losses to 10% over 12 months; tracker paused May 2025 | Correlated tail priced as independent wipes the pool; changing terms after the event destroys trust | MEDIUM (Cointelegraph, InsurAce blog) |
| **Cover Protocol** (2020-21) | COVER token; shield-mining rewards | n/a (the token failed) | Emissions | n/a | 28 Dec 2020: bug in the "Blacksmith" mining contract minted about 40 quintillion COVER; about $4.4M drained; price -97%; core product unaffected | Mint authority is the attack surface; emissions contracts add risk with no underwriting benefit | HIGH (post-mortem, PeckShield) |
| **Unslashed** (2020-) | Capital buckets; USF token | Payout after challenge period; disputes to Kleros jurors | Premiums + USF | Bucket terms | UST claims (largest 742 ETH) rejected repeatedly on Kleros; about 1,018 ETH refused; allegations of an arbitration-side conflict (unverified). Market cap now under $1M | Wording-dependent claims plus token-voted juries end in disputes | LOW-MEDIUM (secondary) |

Adjacent precedents (not insurance, same mechanism):

| Protocol | Mechanism | What happened | Lesson | Conf. |
|----------|-----------|---------------|--------|-------|
| **Aave Safety Module -> Umbrella** | stkAAVE/stkABPT governance-slashed backstop replaced by staked aTokens/GHO (ERC4626) with automatic slashing, DAO offset first, 20-day cooldown + 2-day window, cooldown funds slashable | Activated 5 Jun 2025; stkAAVE slashing to be disabled once Umbrella scales. BGD (24 Jul 2024): "if any stkAAVE slashing happens, the AAVE would need to be sold to the asset on which the debt is denominated; so capital is not efficient"; "the sell pressure of the slashing itself will circularly reduce the coverage"; with aTokens "no selling is needed to cover the deficit, only burning is required" | The strongest single argument against an own-token junior that must be sold | HIGH (Aave docs, governance forum) |
| **Centrifuge Tinlake** | TIN junior / DROP senior; minimum TIN ratio | Breach stops new DROP issuance until restored | Automatic halt is the standard control | MEDIUM |
| **Goldfinch** | Backers first-loss, Senior Pool second | Stratos: about $7M likely write-down on $20M (Oct 2023), sponsor company backstopped; Tugende: $3.1M phased write-down | A thin first-loss layer against a concentrated exposure ends with the sponsor paying | MEDIUM |
| **Resolv** (USR / RLP) | RLP junior protects USR against strategy losses | 22 Mar 2026: single-EOA minting role let an attacker mint 80M unbacked USR, take about $25M; USR hit $0.025 on Curve; RLP did not protect holders | A junior tranche covers underwriting losses, not code failures | MEDIUM (The Block) |
| **Hyperliquid HLP** | USDC vault that makes markets and takes liquidations (our house-MM analogue) | JELLY (Mar 2025): HLP unrealised loss up to $13.5M; validators delisted and settled at $0.0095; HLP closed +$703k; HLP TVL reportedly fell from about $540M to about $150M within weeks | Depositors leave a house vault after a scare even without a loss; ad-hoc overrides cost credibility | MEDIUM (CoinDesk); LOW for TVL |
| **BarnBridge** | SMART Yield "Senior"/"Junior" tranches | SEC order 22 Dec 2023: Securities Act s.5 (unregistered offering) and Investment Company Act (unregistered investment companies); over $509M from investors; about $1.5M disgorgement, $125k penalty each for two founders | Tranching a pool and selling slices is a fact pattern the SEC has already charged | HIGH (SEC PR 2023-258) |
| **MakerDAO** (Black Thursday) | MKR minted and auctioned to cover bad debt | Mar 2020: 20,980 MKR sold for 5.3M DAI; Paradigm won 68% of 106 auctions | Dilution backstop works only with deep buyers | MEDIUM (The Block) |

**Market size context:** OpenCover counted $231M of active DeFi cover against about $48B TVL (about 0.5%) in Mar 2023; 2022 held over 90% of all-time payouts ($34.4M, UST alone $22.5M). Nexus is reported at about 85% of DeFi cover TVL (secondary). The on-chain insurance market is small, and one incident can decide a year.

## Research Q2: Design choices for our token

### 2.1 Where the first loss sits (the core choice)

| Option | What it is | Failure it invites | Verdict |
|--------|-----------|--------------------|---------|
| A. Staked WI is the junior; slashed WI sold for USDC | Aave SM v1, Maple v1 | Forced sale of a thin new token when a loss is announced; capacity tracks WI price, not risk; needs an on-chain WI price | Reject |
| B. Outside-LP USDC junior vault; WI only governs | Ensuro, Centrifuge, Resolv | WI has no first-loss role (breaks the ruling) | Reject for v1; later second junior class |
| C. WI minted/redeemed against the pool at book value | Nexus NXM | Allocations dilute book value; redemption freezes | Reject for a VC-backed launch; cite as proof the ruling is workable |
| **D. Protocol-owned USDC junior + staked-WI pro-rata haircut (burn)** | Ensuro waterfall + Nexus burn + Aave Umbrella offset | Stakers exit before forecast events; capture after a loss; house-MM conflict; staker reward may be security-like | **Recommend**, with the controls below |

How D works in one pass: a loss is paid in USDC from the premium reserve, then from the protocol-owned junior layer, then from senior LPs. If the junior layer lost x% of its balance in the event, every staked WI position (including positions in cooldown) is cut by min(x%, cap) and the cut tokens are burned. Nothing is sold. Stakers are first-loss relative to passive holders; the junior layer is first-loss relative to senior LPs; the claim is always paid in dollars.

### 2.2 Haircut rule

- Pro-rata: haircut = junior USDC lost in the event / junior USDC before the event. No WI price oracle, so nothing to manipulate.
- Cap per event: governance-bounded range, starting point 30%. (30% is the commonly cited cap of Aave's legacy Safety Module; recalled, not re-verified this session. Umbrella itself allows slashing up to the full stake.) The memo should present the cap as a choice to be set from Phase 4's stress days, not as a benchmark.
- Applies to positions in cooldown until they finish (Umbrella: "During cooldown ... funds remain slashable").
- Burned, not redistributed: passive holders gain from the supply cut, which is the point.

### 2.3 Utilisation caps and halt rules

| Control | Rule (numbers from Phase 4) | Precedent |
|---------|------------------------------|-----------|
| Aggregate cap | Sum of max payouts on unmatched residual <= U x (junior + senior) | Ensuro `maxUtilizationRatio` (runs about 90%) |
| Metro-day cap | Max payout on any one metro-day <= junior layer | InsurAce/Sherlock single-event wipeouts; ins2 found residuals around one station common-mode (rho 0.74-0.83) |
| Minimum junior ratio | junior / (junior + senior) >= J; breach halts new policies and senior deposits | Centrifuge minimum TIN ratio |
| Sales cutoff | Cover for a date sold at least N days ahead (N >= forecast skill horizon) | Weather-specific adverse selection |
| Premium floor | Residual premium >= expected loss x (1 + load) on Phase 4's tail model | InsurAce 124x loss ratio |

### 2.4 Premium and fee split

Per residual premium dollar, in order:
1. Pure premium (expected loss) -> premium reserve for the life of the policy (Ensuro pattern).
2. Senior target rate on senior capital, paid from risk margin first (Ondo v1 hurdle pattern).
3. Remaining risk margin -> protocol-owned junior layer.
4. Protocol fee (auction fee + fixed cut of margin, start 10-20%) -> treasury (operating account, not at risk).
5. Junior balance above its Phase 4 target -> released on a schedule to whatever Phase 15 allows: USDC distribution to staked WI, or buyback-and-burn. Below target, nothing is released.

Hedge P&L on the Kalshi station leg stays with the house MM account, not the pool, unless SPEC.md says otherwise (keeps pool accounting clean and the house's two roles visible).

Reference points only (none is a weather benchmark): Nexus stakers get 50% of cover fees; Maple v1 cover got 10% of interest; Maple now routes 25% of revenue to buybacks. Set the split so Phase 4's junior return in a 1-in-20 year is still positive over three years.

### 2.5 Emissions vs real yield

No emissions at launch. Evidence: Maple ended staking rewards for buybacks because staking had "served its purpose in bootstrapping" (MIP-019); Cover's loss came from its mining contract; OnRe and Etherisc headline yields include token incentives. If senior LPs need a start-up incentive, pay it from treasury USDC for a fixed period and label it as an incentive, separate from underwriting return. Token buybacks across crypto reached about $640M in the first eight months of 2026, concentrated in Hyperliquid and Pump.fun (secondary; figures inconsistent between summaries), so funds will ask where WI's buyback money comes from.

### 2.6 Governance scope

| Governed by staked WI | Bounds | Delay |
|-----------------------|--------|-------|
| Utilisation cap U, metro-day cap, minimum junior ratio J | Fixed min/max set at deploy | Timelock (start 3-7 days) |
| Haircut cap per event | e.g. 10-30% | Timelock |
| Protocol fee / treasury cut | e.g. 5-25% of margin | Timelock |
| New metro or index listings | Only with a published hedge-quality report (Phase 3 method) | Timelock |
| Oracle policy (sources, revision window) | Changes apply to new contract series only | Timelock |
| Treasury: junior top-ups, grants, releases above junior target | Releases only above target | Timelock |

Not governed: individual claims (the index decides), terms of live policies, emergency pause (guardian multisig can pause new policies and auctions only, cannot move funds, pause lapses unless renewed). Evidence: Nexus v3 took claims out of token votes; Aave Umbrella removed governance from slashing; the UMA whale vote (Mar 2025) and the HLP/JELLY validator override show the cost of ad-hoc decisions. Note the SEC/CFTC release describes governance tokens as voting on "software upgrades and treasury expenditures" (p. 15); risk-parameter votes that move an income-producing pool are a different thing, and Phase 15 should say so either way.

### 2.7 Lock-ups set from the weather calendar

- Unstake cooldown and senior withdrawal delay >= sales cutoff N + longest open policy tenor + settlement and revision window. With daily contracts, a 7-10 day forecast horizon and nClimGrid's preliminary-then-final monthly files, this is weeks. Aave's 20 days is a floor, not a target.
- Withdrawals are requests; queued capital still absorbs losses on exposure written before the request matures (already modelled in `IPoolVault.WithdrawRequest`).
- No outside junior deposits in v1, so there is no junior run to manage.

### 2.8 Failure modes and mitigations

| # | Failure mode | How it happens here | Precedent | Mitigation | Residual risk |
|---|--------------|--------------------|-----------|-----------|---------------|
| F1 | Death spiral via forced token sale | Junior in WI; loss forces sale; price falls; capacity shrinks | Aave SM rationale; Maple v1 | Junior in USDC; burn-only haircut | WI price still drops on loss news, but capacity doesn't |
| F2 | Run before a known loss | Heatwave forecast 5 days out; stakers/LPs exit | Maple Orthogonal pool cover | Delays longer than forecast + settlement; cooldown positions still cut | Long locks lower staking demand; price that into the memo |
| F3 | Correlated tail wipes junior, hits senior, senior flees | One metro heatwave across many policies | InsurAce UST; Sherlock Euler | Metro-day cap <= junior; min junior ratio halt; station leg hedged on Kalshi | Phase 4 tail-model error |
| F4 | Claim disputes | Payout depends on judgement or a vote | Unslashed/Kleros; Nexus bZx reversal | Parametric index; revision policy written before sale; no claims vote | Data errors (grid revisions, station outages) need a written fallback |
| F5 | Governance capture after a loss | WI cheap after a loss; attacker buys votes to loosen caps | UMA whale vote | Bounded params; timelock; locked-stake voting; guardian veto outside bounds | In-bounds harm still possible |
| F6 | Code failure larger than any tranche | Mint or accounting bug | Resolv (Mar 2026); Cover (Dec 2020) | Fixed-supply WI; no mint role; audits; per-tx and per-day caps; pause | Unknown bugs |
| F7 | Pool money lost outside underwriting | Pool USDC deployed for extra yield | Sherlock in Maple Orthogonal | Plain USDC in v1 | Stablecoin issuer risk |
| F8 | House MM conflict | House quotes auctions and owns the junior | HLP depositor exodus | Separate house and pool accounts; publish both P&Ls; no off-market house trades against the pool | Perception risk with LPs |
| F9 | Emissions-dependent yield | Incentives hide a negative underwriting return | Maple pre-MIP-019; OnRe headline yields | No emissions; publish underwriting return separately | Lower headline yield than competitors |
| F10 | Tranches or staker income treated as securities | Selling senior/junior slices or paying stakers pool income | BarnBridge (2023); 17 Mar 2026 release p. 14 | Phase 15 route decision before any outside LP, staker payout or token sale; testnet only | Legal |

## Research Q3: Comparables 2025-2026

### Rounds (valuations almost never disclosed)

| Company | Category | Round | Amount | Lead / notable | Date | Conf. |
|---------|----------|-------|--------|----------------|------|-------|
| functionSPACE | Pricing numerical outcomes on-chain (prediction-market infra) | Pre-seed | $1.7M | Maven 11; Blockwall, Smape | 25 Sep 2026 | MEDIUM |
| ParlayX | Institutional prediction-market infra | Pre-seed | $1.25M | Dreamcraft Ventures + angels | 3-4 Sep 2026 | MEDIUM |
| Elastics | AI agents for prediction markets | Pre-seed | about $2M (EUR 1.7M) | Frst | May 2026 | MEDIUM |
| Pascal | Prediction-market platform | Series A | $9M | (Fortune exclusive) | 16 Jul 2026 | MEDIUM |
| SpeedLabs | Micro-betting prediction markets | Seed | $6.5M | Parlay Capital | 2026 | MEDIUM |
| Cork | Programmable risk layer, cover tokens / depeg swaps | Seed | $5.5M | a16z CSX, Road Capital (+ BitGo Ventures, Hyperithm, others) | 21 Jan 2026 | MEDIUM |
| OnRe (ex-Nayms) | On-chain reinsurance | Series A | $5M | Forward Industries, RockawayX | May 2026 | LOW-MEDIUM |
| Ground | On-chain yield | Pre-seed | $3.6M | Bain Capital Crypto, ParaFi | Q2 2026 | LOW |
| Hypernova | Prop trading | Pre-seed | $3M | Lemniscap | Q2 2026 | LOW |
| Hyperbeat | HyperEVM yield vaults | Seed | $5.2M | ether.fi Ventures, Electric Capital; Coinbase Ventures | 15 Aug 2025 | HIGH (CoinDesk) |
| Risk Harbor (historic) | Parametric DeFi cover | Seed | $3.25M | Pantera | Jun 2021 | HIGH |
| Re (historic) | Blockchain reinsurer | Seed | $14M | Tribe, Defy, Exor | 2022 | MEDIUM |

Gap: no 2025-2026 round found for an on-chain *parametric weather* protocol, and no disclosed HyperEVM pre-seed valuation. Other HyperEVM teams (Kinetiq, Felix, HypurrFi, Ventuals) had no verifiable round data in this pass.

### Market context

- Galaxy Research Q2 2026: $5.68B across 384 crypto VC deals (+31% QoQ); about 78% of dollars to later stage; seed + pre-seed about 7% of dollars; median deal about $4.9M; valuations disclosed for only about 16% of deals. [MEDIUM, via news summaries]
- A secondary Q2 2026 web3 early-stage tally (55 deals from DefiLlama, cross-checked with press): pre-seed median $2.5M, seed median $5.2M; prediction markets 5 of the early deals; standard paper = post-money SAFE + separate token warrant, ratios 1:1 to 3:1 where described; only 1 of 55 disclosed a cap. [LOW-MEDIUM]
- General US pre-seed (Carta 2025, via summaries): median post-money SAFE caps about $10M for $250k-$1M rounds, about $15M for $1M-$2.5M rounds. [LOW-MEDIUM]
- Read-through: a $500k-$1.5M ask is below the web3 pre-seed median, which is fine for a pre-launch team with a working prototype. A post-money cap from the high single digits to the mid-teens of millions is the realistic range to test, with a token warrant at the equity percentage. [LOW: inference; no comparable disclosed cap found]

### Token allocation and vesting norms

| Bucket | Typical range | Vesting norm | Conf. |
|--------|--------------|--------------|-------|
| Team / founders | 15-25% (about 18-20% common) | 12-month cliff, 3-4 years linear | MEDIUM (practitioner benchmarks) |
| Investors | 11-19% | 12-month cliff, 2-4 years linear | MEDIUM |
| Community | 20-45% | none to short cliff, 1-4 years | MEDIUM |
| Treasury / foundation | about 20% | 6-12 month cliff, 4-10 years | MEDIUM |
| Team + investors combined | 40-55% | - | MEDIUM |

The comparison every HyperEVM pitch gets: Hyperliquid raised no VC money, airdropped 31% of 1B HYPE at genesis (29 Nov 2024), and gave core contributors 23.8% with a 1-year lock, most vesting 2027-2028. It also spends fee revenue on HYPE buybacks (scale not re-verified here). Crypto funds will hold any HyperEVM token's insider share against that.

Design-specific: the allocation table must say how much WI starts staked, and therefore first-loss. Team and investor tokens should be able to stake only after their cliff, so insiders can't collect junior-layer benefits without being locked.

### What crypto funds will ask about token demand (and our honest answer)

Inferred from 2025-2026 practice (buybacks replacing staking rewards, the no-VC Hyperliquid launch, the Mar 2026 SEC/CFTC definitions); not from a sourced VC survey. [LOW]

| Question | Our honest answer now |
|----------|-----------------------|
| Why does this need a token? | The pilot doesn't. The token is how the junior layer gets owned and governed by people who take its losses; it matters once outside senior LPs exist. |
| Why would someone buy and hold it? | Staking gets the vote and, if counsel allows, the junior layer's released income or buybacks. Until Phase 4/5 numbers exist we can't size that. |
| Where does revenue come from? | Premium margin on the unmatched residual + auction fees. The station leg passes through at cost. |
| What happens after a bad week? | Claims paid in USDC; stakers cut pro-rata; no WI sold; new cover halts if the junior ratio breaks. |
| Emissions? | None. |
| Is it a security? | For Phase 15. BarnBridge and the Mar 2026 release are why nothing launches before counsel. |
| Why HyperEVM? | Ordinary contracts need no HYPE stake, and it's where the owner's other on-chain work lives. Whether Hyperliquid users want weather risk is untested. |

## Research Q4: Legal-adjacent facts for Phase 15 (facts only, not advice)

| Date | Body | Item | What it says (short) | Why it matters to us | Conf. |
|------|------|------|----------------------|---------------------|-------|
| 22 Dec 2023 | SEC | BarnBridge DAO order (PR 2023-258) | "Senior"/"Junior" SMART Yield bonds were unregistered securities; pools were unregistered investment companies; >$509M; about $1.5M disgorgement + $125k x2 | Our senior/junior pool has the same shape | HIGH |
| 29 May 2025 | SEC Corp Fin (staff) | Statement on Certain Protocol Staking Activities | Solo, self-custodial-with-third-party and custodial PoS staking are "administrative or ministerial", not securities offerings. Excludes liquid staking, restaking, and assets with "intrinsic economic properties" (passive yield, business profit rights). "No legal force or effect" | Underwriting "staking" of WI is not protocol staking; this statement does not cover it | HIGH (read directly) |
| 5 Aug 2025 | SEC Corp Fin (staff) | Statement on Certain Liquid Staking Activities | Liquid staking where the provider acts as agent without entrepreneurial effort is not a securities offering | Same limit: PoS consensus only | MEDIUM (tracker summary) |
| 18 Jul 2025 | Congress | GENIUS Act signed | Stablecoin issuers may not pay "any form of interest or yield" to holders | Senior tranche must not be marketed or structured as a yield-bearing stablecoin | MEDIUM (LW tracker) |
| 31 Jul / 12 Nov 2025 | SEC Chair Atkins | "Project Crypto" and token-taxonomy speeches | Most tokens trading today are not securities; categories: network tokens/digital commodities, collectibles, tools, tokenized securities | Context for the Mar 2026 release | MEDIUM |
| 17 Mar 2026 (effective 23 Mar) | SEC + CFTC | Joint interpretation, Rel. 33-11412 | Five categories (digital commodities, collectibles, tools, stablecoins, digital securities). p. 14: a digital commodity "does not have intrinsic economic properties or rights, such as generating a passive yield or conveying rights to future income, profits, or assets of a business enterprise". p. 15: a digital commodity "may convey ... governance rights ... such as software upgrades and treasury expenditures". An investment contract can end once promised managerial efforts are done or permanently stop | A WI whose stakers get pool income, or that is a claim on pool assets (NXM-style), does not fit "digital commodity" on these words. Governance-only fits better. This is the central token question for counsel | HIGH (read directly) |
| 22 Jul 2026 | SEC Commissioner Peirce (personal) | Statement on crypto vaults | Vaults can be investment contracts or investment companies depending on who chooses the strategy; "moving activities ... onchain ... does not take those activities outside the scope of the laws". No discussion of tranches or insurance | A curated pool with governance-set risk parameters looks like a managed vault | MEDIUM (personal statement) |
| 18 Aug 2026 | SEC | Proposed Regulation Crypto Assets, Rel. 33-11434 | Startup exemption $5M over 4 years (no financials, general solicitation allowed); fundraising exemption $20M or $75M per 12 months (Form 1-CRYPTO); safe harbor once essential managerial efforts are complete; ten disclosure topics incl. tokenomics and governance. Nothing specific on DeFi, staking or revenue-right tokens. Comments due 20 Oct 2026 | A possible path for a WI sale if it is treated as an investment contract; not final | MEDIUM (Davis Polk, LW tracker) |
| 17 Jul 2025 / 15 Sep 2026 | Congress | CLARITY Act | Passed House 294-134 (17 Jul 2025); Senate Banking advanced 15-9 (14 May 2026); on the Senate calendar 1 Jun 2026; cloture vote 15 Sep 2026 reported to have failed 49-50; next window reported as the lame-duck session | No statute splitting SEC/CFTC token jurisdiction; rely on the 2026 release, not the bill | MEDIUM to calendar; LOW on the vote (one secondary source) |
| 7 Sep 2023 | CFTC | Opyn / ZeroEx / Deridex orders | Opyn's US IP blocking "was not sufficient" | Geo-blocking alone is not a defence | HIGH (via sister-project notes) |
| 3 Jan 2022 | CFTC | Polymarket (Blockratize) | $1.4M penalty for unregistered event-based binary options | Event-style payouts to US persons without a DCM | HIGH (via sister-project notes) |
| 10-12 Jun 2026 | CFTC | Event-contract NPRM (comments closed 27 Jul 2026) | Rewrites Rule 40.11 public-interest test | Bears on DCM-listing of weather residuals | HIGH (via sister-project notes) |

**How comparable protocols structure access (facts to hand over):**

| Protocol | Structure | Access control | Conf. |
|----------|-----------|----------------|-------|
| Nexus Mutual | "Discretionary mutual" run by a DAO; cover is sold to members, not as insurance | KYC membership (0.002 ETH fee); 23 listed restricted countries; the US is not on the list in the docs | MEDIUM |
| OnRe (ex-Nayms) | Bermuda-licensed reinsurer (DABA + IGB licences) | KYC to mint ONe; secondary AMM pool without KYC | MEDIUM |
| Ensuro | Protocol capital behind policies sold by licensed partners | Distribution via partners (Otonomi, Koala, Spot) | MEDIUM |
| Etherisc | Parametric crop cover through ACRE Africa, a licensed intermediary | Partner distribution | MEDIUM |
| Opyn | DeFi options with US IP block | CFTC: "not sufficient" | HIGH |
| Polymarket | Offshore with US block after the 2022 order; bought DCM+DCO QCEX for $112M (Jul 2025) to serve the US | Geo-block, then licence | HIGH (sister notes) |

**The tension to put in front of counsel:** the ruling wants token holders to carry first loss and have a cash-flow reason. Rewarding stakers for first-loss risk means paying them from pool income, and the Mar 2026 release says digital commodities don't convey "rights to future income". A governance-only token that is cut on losses but earns nothing is honest and fits the release better, but gives nobody a reason to stake. Phase 15 should say which of these the owner can actually launch, and in which route (offshore + US block, insurance wrapper, DCM).

## Research Q5: Uses of funds

Ranges, not quotes. Audit costs are sourced; counsel, team and pilot costs are estimates the owner should replace with real quotes. The house seed is capped by a rule, not by the budget.

| Line item | $500k (about 12 months) | $1M (about 18 months) | $1.5M (18-24 months, launch-ready) | Basis | Conf. |
|-----------|-----------------------|---------------------|-----------------------------------|-------|-------|
| Counsel (US securities/CFTC/insurance memo, entity, SAFE + warrant; later offshore or wrapper route, token opinion, KYC/geo-block vendors) | $60-90k | $120-180k | $200-300k | Estimate; replace with 2-3 firm quotes | LOW |
| Security (audit of vault + policy + auction + oracle; contest; bug-bounty reserve) | $40-70k | $90-150k | $150-250k | Sherlock (22 Sep 2026): mid-sized DeFi audit about $60k over 2-3 weeks; large systems $100k-$300k+ | MEDIUM |
| House-pool seed (protocol-owned junior USDC) | $100-150k | $200-300k | $300-450k | Never above Phase 4's junior target for the live book; ins1 found Kalshi depth supports about $100/day of policy per city near the touch, so the pilot book will be small | LOW-MEDIUM |
| Hedge working capital (station leg on Kalshi, if counsel allows the house to hedge) | $15-30k | $30-60k | $50-80k | Kalshi contracts are fully paid at purchase; capital is tied up until settlement | LOW |
| Pilot cohort (premium subsidies, concierge onboarding) | $15-30k (10-15 businesses) | $40-70k (25-40) | $60-100k (50+) | Estimate | LOW |
| Data, oracle signer, hosting, RPC, monitoring | $8-15k | $15-30k | $25-50k | Free NOAA/PRISM/IEM data; infra only | LOW |
| Team (founder stipend + engineers/quant) | $150-200k | $300-400k | $400-550k | Estimate | LOW |
| Reserve | $40-50k | $80-100k | $80-120k | about 8-10% | - |
| **Total (low-high)** | **about $430-635k** | **about $875k-1.29M** | **about $1.27-1.9M** | | |

What each tier buys, in one line each: $500k gets counsel's answer, one audit, a small house-seeded pilot and a year of runway. $1M adds a second audit or contest, a larger pilot and an engineer, enough to show real policies settling. $1.5M adds token-launch readiness (entity, token opinion, KYC/geo-blocking) and a house seed big enough to invite the first outside senior LPs, if counsel clears it.

## Architecture Patterns (for the memo document)

### Recommended memo structure (14-02 output)

```
14-MEMO.md
1. What the pool does, in two paragraphs (the business's view, then the pool's view)
2. The three layers and who loses first (plain words + one diagram)
3. What the token is and isn't (the token mechanics draft below, cleaned up)
4. Why it's built this way (5-6 precedents, one line each, with what broke)
5. The numbers (Phase 4/5 only; pre-registered rules below)
6. What could go wrong (failure table, shortened)
7. The raise: $500k / $1M / $1.5M and what each buys
8. What we don't know yet (Phase 4 gaps, counsel, demand)
Appendix: precedent table, comparables table, legal facts for counsel, sources
```

### Pattern: evidence -> rule -> failure mode
Every design rule in the memo is stated with the precedent that motivates it and the failure it prevents. No rule without a precedent or a Phase 4 number.

### Anti-patterns to avoid
- Quoting a yield before Phase 4 produces one, or any yield that includes incentives.
- Calling it "insurance" before Phase 15's wording guidance (the route may be "cover", reinsurance collateral, or a DCM-listed contract).
- Presenting the token as needed for the pilot.
- Promising stakers income before Phase 15 answers the "rights to future income" question.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| Tranche share accounting | Custom share math | OpenZeppelin ERC4626 (v5.7.0) | Rounding and first-depositor inflation attacks are handled there |
| Governance delay | Custom admin with a delay flag | OZ Governor + TimelockController | Audited, familiar to reviewers |
| Vesting | Custom vesting contract | OZ VestingWallet or an audited streaming vendor | Vesting bugs are common and public |
| Claims decisions | Token-voted court or own arbitration | Parametric index + published revision policy + fixed data-error fallback | Every voted-claims design above ended in disputes |
| Token supply control | Owner-mintable token with the vault as minter | Fixed supply minted once; staking module can only burn | Cover and Resolv losses came from mint authority |
| Capital model for the memo | New spreadsheet | Phase 4 outputs (reports/eval-04-05/) | One source of numbers |
| Launch disclosure | Own format | Blockworks Token Transparency Framework template | Exchanges and funds already read it |

**Key insight:** the hard part of a first-loss token is not code. It is currency mismatch, exit timing, claims discretion and what stakers are legally allowed to earn. The first three have known answers from protocols that got hurt; the fourth is Phase 15's.

## Common Pitfalls

### Pitfall 1: Own-token junior that must be sold
**What goes wrong:** a loss forces selling WI, the price drops, junior capacity shrinks, senior LPs leave.
**Why it happens:** it looks like skin in the game and needs no outside capital.
**How to avoid:** USDC junior, burn-only haircut (Option D).
**Warning signs:** a SPEC line that needs a WI price oracle to pay claims.

### Pitfall 2: Lock-ups copied from DeFi
**What goes wrong:** weather losses are forecast; a 7-day cooldown lets stakers leave before a forecast heatwave.
**How to avoid:** derive delays from forecast horizon + tenor + settlement/revision window; cooldown positions still take haircuts.
**Warning signs:** cooldown shorter than sales cutoff + settlement lag.

### Pitfall 3: Correlated tail priced as independent
**What goes wrong:** one metro heatwave hits every policy (ins2: residuals around one station are common-mode, rho 0.74-0.83).
**How to avoid:** metro-day cap <= junior, from Phase 4's stress days, not averages.

### Pitfall 4: Claims by vote or by wording
**How to avoid:** parametric settlement on a stated index; revision policy written before sale.

### Pitfall 5: Changing terms after the event
**What goes wrong:** InsurAce shortened the claims window after UST.
**How to avoid:** oracle and settlement policy changes apply only to new series.

### Pitfall 6: Yield that is really emissions
**How to avoid:** report underwriting return, collateral return and any incentive as separate lines.

### Pitfall 7: Investing the pool
**What goes wrong:** Sherlock lost about $4M of staker USDC in a Maple pool default.
**How to avoid:** plain USDC in v1.

### Pitfall 8: Mint authority left open
**What goes wrong:** `WIToken.sol` is owner-mintable and the stub expects the vault to become minter. Fine on testnet; dangerous with value.
**How to avoid:** fixed supply before launch; staking module can burn, not mint.

### Pitfall 9: Treating tranches or staker income as legally neutral
**How to avoid:** no outside senior or junior LPs, no staker payouts, no token sale before Phase 15's route decision.

### Pitfall 10: The house wearing two hats unseen
**How to avoid:** separate house MM and pool accounts; publish both P&Ls.

## Code Examples

Illustrative, for the Phase 7 engine and the memo's worked example. Loss order from Ensuro's docs; burn-on-loss from Nexus's docs; the pro-rata, oracle-free haircut is this research's recommendation.

```python
# Loss waterfall + pro-rata staked-WI haircut (illustrative; USDC as 6-dp integers)
from dataclasses import dataclass

@dataclass
class Pool:
    premium_reserve: int   # pure premiums held for live policies
    junior: int            # protocol-owned USDC (house seed + retained margin)
    senior: int            # outside stablecoin LPs
    staked_wi: int         # staked + cooling-down WI (18 dp)
    haircut_cap_bps: int = 3000  # governance-bounded; set from Phase 4 stress days

def absorb_loss(p: Pool, loss: int) -> dict:
    """Pay `loss` USDC in order reserve -> junior -> senior; cut staked WI pro-rata
    to the junior's loss. Never sells WI."""
    assert loss >= 0
    from_reserve = min(loss, p.premium_reserve); loss -= from_reserve
    junior_before = p.junior
    from_junior = min(loss, p.junior); loss -= from_junior
    from_senior = min(loss, p.senior); loss -= from_senior
    if loss > 0:
        raise RuntimeError("pool insolvent: caps failed")  # unreachable if caps hold
    p.premium_reserve -= from_reserve; p.junior -= from_junior; p.senior -= from_senior
    haircut_bps = 0 if junior_before == 0 else min(
        from_junior * 10_000 // junior_before, p.haircut_cap_bps)
    wi_burned = p.staked_wi * haircut_bps // 10_000
    p.staked_wi -= wi_burned
    return dict(from_reserve=from_reserve, from_junior=from_junior,
                from_senior=from_senior, haircut_bps=haircut_bps, wi_burned=wi_burned)

def can_write(p: Pool, new_max_payout: int, open_max_payout: int,
              same_metro_day_open_max_payout: int, U_bps: int, J_bps: int) -> bool:
    """Utilisation, metro-day and minimum-junior-ratio checks before any new policy."""
    capital = p.junior + p.senior
    if capital == 0:
        return False
    return ((open_max_payout + new_max_payout) * 10_000 <= U_bps * capital
            and same_metro_day_open_max_payout + new_max_payout <= p.junior
            and p.junior * 10_000 >= J_bps * capital)
```

Money-failure tests that belong (AGENTS.md rules): value conservation through `absorb_loss` (reserve + junior + senior + paid out == before); senior untouched while junior > 0; `can_write` refusing a policy that pushes a metro-day above the junior; the haircut hitting a position that requested unstake after the exposure was written.

## Pre-registered rules for the numbers half (14-02)

Written before any Phase 4 number exists (AGENTS.md). Deviations get logged in the memo.

1. Every number in the memo cites a Phase 4/5 report file and row; the memo does not re-derive capital.
2. Junior target = the larger of Phase 4's pre-registered tail measure and the worst historical metro-day loss on the pilot book; no rounding down.
3. "Capital per $ of cover" = (junior target + required senior) / total max payout of unmatched residual after netting, at Phase 4's pre-registered netting ratio. External reference points, shown but never substituted: Nexus MCR = active cover / 4.8 (about $0.21 per $1, diversified smart-contract risk); Ensuro senior sized to a 99.5% level.
4. Junior return reported three ways: median year, 1-in-20 bad year, worst historical year; zero emissions; collateral yield (if any) as a separate line.
5. Premium split shown as the 2.4 rule with a sensitivity table for treasury cut 10% / 20%; no single "APY" headline.
6. If the 1-in-20 junior return is negative over three years, the memo says so and states what would have to change (premium load, caps), rather than tuning the split to hide it.

## Token mechanics draft (one page, owner's voice; starting point for the memo)

**How the pool and the token work (draft)**

When a business buys cover from us, most of its weather risk is hedged with Kalshi contracts that settle at the nearby airport. What's left is the gap between the airport and the business's own street. Businesses with opposite exposure trade that gap with each other. Whatever doesn't match ends up in the pool, and the pool pays when the weather goes against it.

The pool has three layers, and losses go through them in order.

First, premiums. Each policy pays a premium, and the part that covers expected payouts stays in the pool until the policy ends. Normal weeks get paid from here.

Second, the junior layer. This is money the protocol owns. At the start it's the house seed from our raise, and later it grows from the share of each premium we keep. It's held in USDC, not in our own token. Claims are paid in dollars, and we don't want to be selling our own token into a falling market to pay one. Aave replaced its token-backed safety fund in 2025 for exactly that reason.

Third, the senior layer. These are outside depositors who put in stablecoins for a steadier return. They only lose money if the junior layer is used up. We won't take outside deposits until our lawyers tell us how we're allowed to.

The token is how you own the junior layer. If you stake it, you vote on the pool's risk settings, and you take the first hit. If the junior layer loses 10% of its money in a bad week, every staked position is cut by 10%, up to a cap per event, and those tokens are burned. Nobody sells anything to pay the claim. If you hold the token without staking it, you don't vote and you don't get cut. Nexus Mutual works a similar way: it burns stakers' tokens when it pays a claim, and it has paid more than $18.5 million in claims since 2019. What stakers get back for carrying that risk, whether a share of the pool's income or buybacks, depends on what counsel says we can offer, so we're not promising it yet.

A few rules keep the obvious failures from happening:

- You can't leave right before a heatwave. Weather is forecast days ahead, so unstaking and withdrawals take longer than the forecast window plus the time it takes for the weather data to become final. Tokens that are unstaking still take the cut.
- The pool can't write more than it can carry. There's a cap on total exposure, a cap on any one city on any one day, and a minimum size for the junior layer. If we hit a limit, we stop selling new cover until we're back under it.
- Nobody votes on claims. Payouts follow the published weather index and the revision rule written before the policy was sold.
- Governance can only move settings inside fixed ranges, and every change waits a few days before it takes effect. A small group can pause new sales in an emergency, but it can't move money.
- No token emissions. The income is premiums and fees. If that income is small, the return is small, and we'll say so.
- Pool money sits in USDC. We don't chase extra yield with it. Sherlock lost about $4 million of its stakers' money doing that.

What we don't know yet: how big the junior layer has to be for each dollar of cover, and what it earns in a normal year and a bad one. Those numbers come from our pool simulation, not from this page. We also don't know whether US rules let us offer staking, senior deposits, or the token itself to US persons at all. That's a question for counsel, and nothing goes live before we have an answer.

## State of the Art

| Old approach | Current approach | When changed | Impact |
|--------------|------------------|--------------|--------|
| Own-token slashable backstop (stkAAVE), governance-decided slashing | Stake the asset the loss is in; automatic burn-only slashing (Umbrella) | Aave, 5 Jun 2025 | Strongest precedent against selling the governance token to pay losses |
| Token-holder claims voting | Permissioned expert claims; parametric triggers | Nexus v3 (2025-26); Risk Harbor/Etherisc parametric | Claims out of governance |
| Bonding curve with MCR freeze | RAMM with book-value floor and ratchet | Nexus, Nov 2023 | Liquidity without blocking exits |
| Staking rewards / emissions | Buybacks from revenue | Maple MIP-019 (Oct-Nov 2025); others 2025-26 | Funds expect revenue-backed value accrual |
| SAFT | Post-money SAFE + token warrant | Standard by 2026 | Paper for our raise |
| Enforcement-led token policy | SEC/CFTC five-category release (Mar 2026); proposed Reg Crypto Assets (Aug 2026); CLARITY stalled in Senate | 2025-26 | A possible path, not final; income-bearing tokens still sit on the securities side of the definitions |

**Deprecated/outdated:** own-token first-loss pools (Maple v1, Aave SM), inflation-funded underwriting yield, voted claims.

## Open Questions

1. **What stakers receive.** What we know: first-loss without reward gets no stakers; reward from pool income runs into the Mar 2026 release's "rights to future income" language. What's unclear: whether buybacks, distributions, or neither are allowed in the chosen route. Recommendation: memo leaves the reward line blank pending Phase 15 and says why.
2. **Fixed-supply WI (Option D) vs NXM-style book-value token (Option C).** D fits a VC token with allocations; C is the most literal reading of the ruling and would look even more like a security. Recommendation: memo uses D, lists C, owner confirms.
3. **Haircut cap and lock length.** Depend on Phase 4 tail, contract tenors and the revision window. Recommendation: state the formulas now, fill numbers in 14-02.
4. **Outside junior LPs.** Not in v1; revisit only with flow and a Phase 15 route.
5. **Insurance-wrapper route changes the token.** If a licensed carrier fronts policies (Ensuro, Etherisc/ACRE, OnRe pattern), the pool becomes reinsurance collateral and WI stakers become capital providers to a regulated risk. Recommendation: Phase 15 decides; the memo shows D works in the offshore and the wrapper route.
6. **Comparable valuations.** Almost no disclosed caps for on-chain insurance or HyperEVM pre-seeds. Recommendation: the deck quotes round sizes, not valuations, unless the owner has private data.
7. **Unverified in this pass** (web search budget ran out mid-research): the 30% legacy Aave slashing cap; the CLARITY cloture vote count; Hyperliquid's fee-to-buyback share and its interface's restricted jurisdictions; counsel and team cost ranges; Maple's current pool-cover asset and percentages. Recommendation: 14-01 spends one short worker task re-checking these before the memo cites them.

## Sources

### Primary (HIGH confidence)
- Nexus Mutual docs: [token model](https://docs.nexusmutual.io/protocol/nxm-token/token-model/), [capitalisation history](https://docs.nexusmutual.io/protocol/nxm-token/history-capitalisation-controls/), [staking](https://docs.nexusmutual.io/protocol/staking/), [claims history](https://docs.nexusmutual.io/overview/claims-history/), [membership](https://docs.nexusmutual.io/overview/membership/); [Nexus v3 year review, 15 Jan 2026](https://nexusmutual.io/blog/nexus-mutual-v3-a-year-of-progress-in-onchain-risk-infrastructure)
- Ensuro docs: [risk management](https://docs.ensuro.co/ensuro-docs/readme/risk-management), [EToken](https://docs.ensuro.co/ensuro-docs/smart-contracts/contracts/etoken), [pools overview](https://docs.ensuro.co/ensuro-docs/liquidity-providers/ensuros-pools-overview)
- Aave: [Umbrella docs](https://aave.com/docs/aave-v3/umbrella); [BGD Umbrella proposal, 24 Jul 2024](https://governance.aave.com/t/bgd-aave-safety-module-umbrella/18366)
- SEC: [BarnBridge PR 2023-258](https://www.sec.gov/newsroom/press-releases/2023-258); [Rel. 33-11412 joint interpretation (read directly, pp. 14-15)](https://www.sec.gov/files/rules/interp/2026/33-11412.pdf); [protocol staking statement, 29 May 2025](https://www.sec.gov/newsroom/speeches-statements/statement-certain-protocol-staking-activities-052925); [Peirce on crypto vaults, 22 Jul 2026](https://www.sec.gov/newsroom/speeches-statements/peirce-statement-crypto-vaults-lending-strategies-072226); [Reg Crypto Assets proposal 33-11434](https://www.sec.gov/files/rules/proposed/2026/33-11434.pdf)
- [Cover Protocol post-mortem](https://coverprotocol.medium.com/12-28-post-mortem-34c5f9f718d4); [PeckShield analysis](https://peckshield.medium.com/cover-incident-the-unlimited-token-minting-vulnerability-f3afd9d2405c)
- Sherlock: [receipt NFTs / lockups](https://github.com/sherlock-protocol/sherlock-v2-docs/blob/main/tokens/receipt-nfts.md), [Sherlock Shield](https://docs.sherlock.xyz/coverage/sherlock-shield)
- CFTC orders (Opyn 8774-23, Polymarket 8478-22) and event-contract NPRM, as verified in `~/Desktop/defi-options/.planning/research/notes/notes-D-legal-pm.md` (2026-09-23)

### Secondary (MEDIUM confidence)
- [DL News on Sherlock after Euler](https://www.dlnews.com/articles/defi/sherlock-defi-insurer-on-edge-euler-hack/); [The Block, Sherlock pays Euler](https://www.theblock.co/post/219597/crypto-audit-provider-sherlock-pays-euler-finance)
- [The Block, Orthogonal default](https://www.theblock.co/post/192097/maple-finance-default-orthogonal-trading); [Yahoo/CoinDesk, Maple $54M sour debt and depleted cover](https://finance.yahoo.com/news/maple-finances-54m-sour-debt-035326041.html); [Forgd, Maple tokenomics](https://content.forgd.com/p/tokenomics-101-maple-finance); [crypto.news, MIP-019](https://crypto.news/maple-finance-end-syrup-staking-mip-019-vote-2025/)
- [Ondo v1 docs](https://docs.ondo.finance/ondo-v1-vaults-laas)
- [OpenCover, Risk Harbor](https://opencover.com/risk-harbor/); [CoinDesk, Risk Harbor seed](https://www.coindesk.com/tech/2021/06/24/defi-insurance-upstart-risk-harbor-goes-live-with-325m-in-seed-funding)
- [Neptune Mutual closure post (X)](https://x.com/neptunemutual/status/1806694966837522938)
- [Etherisc DIP staking and depeg cover](https://blog.etherisc.com/upgraded-dip-staking-and-usdc-depeg-protection-a92e026311a4); [Etherisc DIP staking docs](https://docs.etherisc.com/learn/dip-staking); [Cointelegraph, Kenyan farmers](https://cointelegraph.com/news/etherisc-onboards-17k-kenyan-farmers-covered-by-blockchain-based-crop-insurance)
- [Crowdfund Insider, Nayms Bermuda licences](https://www.crowdfundinsider.com/2022/05/191349-nayms-becomes-fully-regulated-insurance-marketplace-for-crypto-assets-in-bermuda/); [The Block, OnRe ONe launch](https://www.theblock.co/post/355248/solana-backed-onre-taps-ethena-for-first-one-token-and-pool-targets-750-billion-reinsurance-market)
- [Cointelegraph, UST depeg and DeFi insurance](https://cointelegraph.com/innovation-circle/the-ust-depeg-and-how-it-affected-defi-insurance); [InsurAce staker compensation](https://www.insurace.io/blog/?p=3068)
- [Cointelegraph, Cover mint attack](https://cointelegraph.com/news/cover-protocol-suffers-infinite-minting-attack-price-tanks-97)
- [The Block, OpenCover payout data](https://www.theblock.co/post/221423/more-than-90-of-all-time-defi-insurance-payout-value-was-in-2022-opencover)
- [The Block, Resolv USR exploit](https://www.theblock.co/post/394582/resolvs-usr-stablecoin-depegs-after-attacker-mints-80-million-unbacked-tokens-extracts-roughly-25-million)
- [CoinDesk, Hyperliquid JELLY](https://www.coindesk.com/markets/2025/03/26/hyperliquid-delists-jellyjelly-after-vault-squeezed-in-usd13m-tussle)
- [The Block, MKR debt auctions](https://www.theblock.co/news/defi/2020-03-31-mkr-auctions-conclude-with-crypto-venture-firm-paradigm-emerging-as-the-biggest-winner-60447)
- [Yahoo, Goldfinch Tugende write-down](https://finance.yahoo.com/news/goldfinch-writes-down-failed-5m-194724327.html); [Centrifuge v1 docs](https://docs.centrifuge.io/getting-started/legacy/centrifuge-v1/)
- [CryptoSlate, Umbrella activation](https://cryptoslate.com/aave-dao-activates-on-chain-slashing-mechanism-with-umbrella-launch/)
- Rounds: [CoinDesk, Hyperbeat](https://www.coindesk.com/tech/2025/08/15/hyperbeat-secures-usd5-2m-backing-from-ether-fi-electric-capital); [Yahoo, Cork seed](https://finance.yahoo.com/news/cork-raises-5-5m-via-173721712.html); [Cryptorank, functionSPACE](https://cryptorank.io/insights/deals/function-space-pre-seed-2026-09-24); [Cryptorank, ParlayX](https://cryptorank.io/insights/deals/parlay-x-pre-seed-2026-09-03); [FinTech Global, Elastics](https://fintech.global/2026/05/06/elastics-raises-2m-pre-seed-for-ai-prediction-market-agents/); [Fortune, Pascal](https://fortune.com/2026/07/16/exclusive-prediction-market-startup-pascal-9-million-heavyweights-kalshi-and-polymarket/); [EGR, SpeedLabs](https://www.egr.global/intel/news/micro-betting-prediction-markets-startup-raises-6-5m-in-seed-funding/)
- [crypto.news, Galaxy Q2 2026 VC report](https://crypto.news/crypto-vc-funding-hits-5-68b-in-q2-galaxy-says/)
- Latham & Watkins crypto policy tracker: [legislative](https://www.lw.com/en/us-crypto-policy-tracker/legislative-developments), [regulatory](https://www.lw.com/en/us-crypto-policy-tracker/regulatory-developments); [Davis Polk, Reg Crypto Assets](https://www.davispolk.com/insights/client-update/sec-proposes-regulation-crypto-assets-meaningful-offering-framework-though)
- [Sherlock, audit cost 2026 (22 Sep 2026)](https://sherlock.xyz/post/smart-contract-audit-cost)
- Hyperliquid allocation: [CoinGecko](https://www.coingecko.com/learn/what-is-hyperliquid-and-what-the-hyperliquid-airdrop-means-for-defi), [Tokenomist](https://tokenomist.ai/hyperliquid)

### Tertiary (LOW confidence - validate before citing in the memo)
- [Innmind/PitchPop, web3 pre-seed/seed Q2 2026](https://blog.innmind.com/web3-startup-funding-in-q2-2026-the-first-pre-seed-seed-report-real-medians-verified-deals/) (medians, Ground, Hypernova)
- Carta 2025 SAFE-cap medians (via search summaries; carta.com blocked fetch)
- Token allocation benchmarks: [8blocks](https://8blocks.io/learn/token-vesting-benchmarks), [Streamflow](https://streamflow.finance/blog/token-allocation-percentages)
- [homecryptoinvest, CLARITY cloture result](https://homecryptoinvest.com/articles/clarity-act-update-2026.html) (single source; internal inconsistencies in the vote breakdown)
- [Spark comparison page](https://www.spark.money/tools/stablecoin-insurance-coverage-comparison) (Risk Harbor TVL, Nexus market share)
- Unslashed/Kleros dispute details (search summaries of secondary posts)
- [KuCoin news, 2026 buybacks](https://www.kucoin.com/news/flash/crypto-token-buybacks-surge-to-640m-in-2026-spark-debate-on-value-creation)
- OnRe Series A May 2026 (search summary)
- Counsel, team and pilot cost ranges in Q5 (author estimates)

## Metadata

**Confidence breakdown:**
- Precedent mechanics (Q1): HIGH for Nexus, Ensuro, Aave, BarnBridge, Cover (docs/primary); MEDIUM for Sherlock, Maple, InsurAce, Etherisc, OnRe, Resolv, HLP; LOW-MEDIUM for Unslashed.
- Design recommendation (Q2): MEDIUM-HIGH. Each rule maps to a documented precedent; the combination (protocol-owned USDC junior + pro-rata burn) is this research's synthesis and has no single live precedent.
- Comparables (Q3): LOW-MEDIUM. Round sizes sourced; valuations mostly undisclosed; VC-question list inferred.
- Legal facts (Q4): HIGH for the SEC texts read directly (33-11412, staking statement, BarnBridge); MEDIUM for summaries (Reg Crypto Assets, GENIUS, liquid staking); LOW for the CLARITY vote count.
- Uses of funds (Q5): LOW-MEDIUM. Audit cost sourced; the rest are estimates.

**Research date:** 2026-09-30
**Valid until:** 2026-10-21 for the legal rows (Reg Crypto Assets comments close 20 Oct 2026; CLARITY may return in the lame-duck session); 2026-10-30 for everything else.
