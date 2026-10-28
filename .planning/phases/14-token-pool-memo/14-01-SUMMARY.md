---
phase: 14-token-pool-memo
plan: 01
status: complete (section 5 placeholder by design)
files: [reports/pitch/14-TOKEN-POOL-MEMO.md]
---
# 14-01 Summary: token + pool memo draft

- Wrote `reports/pitch/14-TOKEN-POOL-MEMO.md` in the owner's voice: sections 1-4, 6-8 and appendices A (precedents), B (comparable rounds), C (facts for counsel), D (sources pointer).
- Section 5 "The numbers" is a marked placeholder listing: capital per $ cover (H=30), junior share, fee income per $ notional, netting ratio central/null, worst window (+ES99) from `reports/eval-04-05/handoff.json`; HE_ladder by sector (+HE_cover) from `reports/eval-06/results.json`; plus the pre-registered rules from 14-RESEARCH. Neither file exists yet.
- Stated plainly: claims paid in USDC; token owns the junior layer, burned pro-rata on junior losses (capped); fixed supply, no emissions; staker income undecided pending counsel; the pilot needs no token.
- Section 4 gives ten design rules, each as precedent -> rule -> failure prevented (Aave Umbrella, Nexus, Maple, InsurAce, Unslashed/Nexus v3, Sherlock, Cover/Resolv, Maple MIP-019, BarnBridge, HLP/JELLY).
- Uses of funds at $500k/$1M/$1.5M from Q5, with the "replace with quotes" caveat and the house-seed cap rule.
- Length: body prose about 2,110 words; about 2,520 counting the section 6/7 tables' markdown (placeholder excluded). Appendix tables extra.
- Banned-word grep (ecosystem, flywheel, wedge, unlock, robust, seamless, leverag, at scale, positioned to, the future of): 0 hits.

## Deviations / choices
- Uses "cover"/"policy", not "insurance" (14-RESEARCH anti-pattern; 07-CONTEXT §12). A one-line note at the top says why.
- Did not cite the unverified items from 14-RESEARCH Open Question 7 (Aave legacy 30% cap, CLARITY vote count, Hyperliquid buyback share). The 30% haircut cap and 10-day exit delay show up only as prototype placeholders (07-CONTEXT §4).
- Added two legal-risk bullets from 15-RESEARCH to section 8: the swap-or-insurance fork, and Kalshi venue/data-terms risk (NY AG suit; data-terms restriction).
- Protocol fee described as prototype default 10% of margin (07-CONTEXT §11), not the 10-20% range.
- No git operations run.
