# Ceraunic

Weather cover for small businesses. A café or shop buys cover against heat days or rainy days. The book is hedged on exchange-listed weather contracts (Kalshi daily station ladders), and the leftover local risk sits in an on-chain junior/senior pool (HyperEVM testnet prototype).

Research preview. Site: [ceraunic.com](https://ceraunic.com). Demo (simulated data): [wi-portal.vercel.app](https://wi-portal.vercel.app).

**Start here:** [`docs/STATUS.md`](docs/STATUS.md) has what is built, the results, and what is still open.

## Layout

| path | what |
|---|---|
| `src/wi/` | Python reference engine, data pullers, evaluations, API |
| `contracts/` | Foundry contracts (pool, auction, oracle, token) and tests |
| `apps/portal/` | Next.js portal (business, trader and pool views) |
| `scripts/` | data pulls, evaluations, report and deck builders |
| `reports/` | evaluation outputs (`eval-01`…`eval-05`), report, memos, demo screenshots |
| `paper/` | working paper: LaTeX source, PDF, `NUMBERS.md` (source of every number) |
| `data/manifests/` | where every raw file came from |
| `data/cache/` | small derived caches (eval03/04, elasticity, vintages); raw data is not in the repo |
| `.planning/` | project plan, roadmap, owner rulings, per-phase plans and summaries, handoff log |
| `.planning/research/` | CME vs Kalshi weather research (latest work, 2026-10-24) |
| `site/` | ceraunic.com landing page (Cloudflare Worker static assets) |

## Setup

```bash
uv sync                      # Python engine + evaluations
pnpm install                 # portal
cd contracts && forge test   # contracts (needs Foundry; run `forge install` first)
```

Raw data (about 1 GB: Kalshi, PRISM, GHCN-D, IEM, nClimGrid, CME) is not committed. The pull scripts in `scripts/` and the manifests in `data/manifests/` rebuild it. PRISM allows only 2 downloads per file per Pacific day; never re-request a file the same day.
