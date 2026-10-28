"""wi.engine: the numerical reference for the protocol (docs/SPEC.md).

No pandas / xarray / netCDF4 / pyarrow / matplotlib imports at module level anywhere in this
package: the engine API bundle must stay slim (SPEC section 0). `wi.eval.ladder` (numpy) is imported
lazily by `hedge` only when a ladder is priced or a hedge is filled.

Layout: units (scales, rounding, canonical JSON) - events (catalogue) - log (hash chain) - state -
reducer (Ledger: emit / apply_line / replay, invariants after every event) - markets, auction,
policy, pool, staking, oracle, hedge, pricing, margin, rfq, house_mm (handlers + commands).
"""
