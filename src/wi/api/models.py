"""Pydantic wire models = the OpenAPI contract (09-RESEARCH "API Contract").

Units (Phase 7): money = integer USDC base units (suffix E6); temperature in tenths of a degree F;
rain in hundredths of an inch; days are YYYY-MM-DD climate days; timestamps are ISO-8601 Z.

Rain cover (13-RAIN), peril "rain": pays `units` dollars for each covered day the metro's Kalshi rain station
(Central Park, O'Hare, Miami Intl) reports a wet day on its NWS CLI (0.01 in or more; a trace "T" is dry, as on Kalshi).
There is no line or range: strikeTenthsF / capTenthsF are ignored on input and come back as 0 / 1 (the [0, 1] market
on the wet-day index CLI:<S>:WET:v1). The station leg is one Kalshi KXRAIN "> 0 in" contract per unit per day.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .envelope import Address, Execution, Mode, Wire

Peril = Literal["heat", "cold", "rain"]
HedgePath = Literal["house-hedge", "business-ladder"]
Side = Literal["buy", "sell"]
Tranche = Literal["senior", "junior"]
AuctionStatus = Literal["open", "closed", "cleared"]

# ---------------------------------------------------------------- meta


class Health(Wire):
    ok: bool
    mode: Mode
    chain_id: int | None = None
    engine_version: str
    spec_hash: str
    sim_time: str | None = None


class ChainInfo(Wire):
    id: int
    name: str
    rpc_url: str
    explorer_url: str | None = None


class Station(Wire):
    station_id: str
    city: str
    name: str
    lat: float
    lon: float
    kalshi_series: str
    settlement_source: str


class AuctionContract(Wire):
    contract_id: str
    station_id: str
    index_id: str
    range_tenths_f: int
    description: str


class Schedule(Wire):
    house_cutoff_utc: str
    public_cutoff_utc: str


class Limits(Wire):
    max_orders_per_auction: int
    max_sales_rows: int
    max_body_bytes: int


class Site(Wire):
    """A location site: a business settles on its nearest site's daily max (09-LEDGER)."""
    site: str
    station_id: str
    name: str
    lat: float
    lon: float
    metro: str
    settlement_station: str
    index_id: str
    residual_contract_id: str | None = None
    source: str


class Config(Wire):
    mode: Mode
    chain: ChainInfo
    contracts: dict[str, Address]
    stations: list[Station]
    auction_contracts: list[AuctionContract]
    schedule: Schedule
    limits: Limits
    sites: list[Site] = []
    replay_window: list[str] | None = None


# ---------------------------------------------------------------- sim world


class WorldCreate(Wire):
    template: Literal["demo-5-cities"] = "demo-5-cities"


class WorldInfo(Wire):
    world_id: str
    sim_time: str


class AdvanceRequest(Wire):
    days: int


class EventSummary(Wire):
    ts: str
    kind: Literal["markets_open", "house_cutoff", "public_cutoff", "hedge", "oracle_fetch", "finalize", "epoch"]
    detail: str


class AdvanceResult(Wire):
    sim_time: str
    events: list[EventSummary]


class Clock(Wire):
    sim_time: str
    next_events: list[EventSummary]


# ---------------------------------------------------------------- accounts


class Balances(Wire):
    usdc_e6: int
    locked_e6: int
    senior_shares: int
    junior_shares: int


class FaucetRequest(Wire):
    address: Address
    amount_e6: int


# ---------------------------------------------------------------- businesses


class BusinessCreate(Wire):
    name: str
    lat: float
    lon: float
    zip: str | None = None
    naics: str | None = None
    owner: Address


class Business(Wire):
    business_id: str
    name: str
    owner: Address
    lat: float
    lon: float
    zip: str | None = None
    naics: str | None = None
    city: str
    settlement_station: str
    location_index: str
    residual_contract_id: str  # "" when the business sits at its settlement station (no residual)
    location_site: str | None = None
    distance_km: float | None = None
    rain_station_id: str | None = Field(None, description="Station a rain cover settles on (the metro's Kalshi rain "
                                        "station, e.g. KORD for Chicago)")
    rain_station_name: str | None = None


class SalesRow(Wire):
    date: str
    gross_sales_cents: int
    order_count: int | None = None


class SalesUpload(Wire):
    source: Literal["csv", "square", "fixture"]
    rows: list[SalesRow]


class SalesSummary(Wire):
    rows: int
    first_date: str | None
    last_date: str | None
    gaps: int
    warnings: list[str]


class Coef(Wire):
    beta: float
    se: float
    n: int


class Prior(Wire):
    sector: str
    mu: float
    tau2: float
    learned: bool


class Elasticity(Wire):
    heat: Coef
    wet: Coef
    shrink_weight: float
    prior: Prior
    origin: Literal["prior", "own-shrunk"]
    method: str
    # 09-LEDGER additions: Phase 5 estimator outputs and the EVAL-06 hedge effectiveness per path
    he_cover: float | None = None  # house-hedge path: the policy pays on the index (HE_cover, group median)
    he_ladder: float | None = None  # business-ladder path: Kalshi ladder at 24 h asks (HE_ladder, group median)
    he_by_path: dict[str, float | None] = {}
    advisory_only: bool = True
    prior_group: str | None = None
    model: str | None = None
    heat_usd_per_deg_f: float | None = None
    rain_contracts: float | None = None
    recent_mean_daily_sales_cents: float | None = None
    rows_used: int = 0
    rows_ignored_after_sim_day: int = 0
    warnings: list[str] = []


class Recommendation(Wire):
    """GET /businesses/{id}/recommendation[?peril=rain]. For rain: unitsPerDay = dollars per wet day, strikeTenthsF 0,
    capTenthsF 1, maxDailyPremiumE6 = 1.25 x the first day's price."""
    peril: Peril
    strike_tenths_f: int
    cap_tenths_f: int
    units_per_day: int
    max_daily_premium_e6: int
    path: HedgePath
    he_estimate: float
    rationale: list[str]
    start_day: str | None = None
    end_day: str | None = None


# ---------------------------------------------------------------- quotes + policies


class QuoteRequest(Wire):
    business_id: str
    peril: Peril
    strike_tenths_f: int = Field(description="Line, tenths of a degree F (heat/cold); ignored for rain (send 0)")
    cap_tenths_f: int = Field(description="Range to full payout, tenths of a degree F (heat/cold); ignored for rain "
                              "(send 1)")
    units: int = Field(description="Heat/cold: units per day, each pays at most $1 (units = $/F x cap F). "
                       "Rain: dollars paid per wet day")
    start_day: str
    end_day: str
    path: HedgePath


class Rung(Wire):
    ticker: str
    qty: int  # whole contracts (display)
    ask_cents: int
    qty_centi: int | None = None  # centi-contracts, the engine's unit
    # rain: one row per covered day (one KXRAIN contract per unit per day)
    for_day: str | None = None
    source: Literal["kalshi-ask", "wet-day-rate", "not-open"] | None = Field(
        None, description="rain: kalshi-ask = the market is open and askCents is its ask; wet-day-rate = not open at "
        "quote time, askCents is the house price per contract (trailing wet-day rate + half-spread); not-open = listed "
        "for the business to place once Kalshi opens it (askCents 0)")


class StationLeg(Wire):
    series: str
    as_of: str
    rungs: list[Rung]
    overround_bp: int


class ResidualLeg(Wire):
    contract_id: str
    qty: int
    fair_price_e6: int
    half_spread_e6: int
    tick: int | None = None
    basis_tenths_f: int | None = None  # signed basis price of `tick` (SPEC 2: -R + t*2R/100)


class Quote(Wire):
    quote_id: str
    expires_at: str
    premium_e6: int
    station_leg_e6: int
    residual_leg_e6: int
    fees_e6: int
    max_payout_e6: int
    he_estimate: float
    station_leg: StationLeg
    residual_leg: ResidualLeg
    ladder_for_business: list[Rung] | None = None  # instructions only; we never place Kalshi orders
    # itemised (feesE6 = premium - stationLeg - residualLeg = tail + riskMargin + notionalFee or the minimum top-up)
    tail_e6: int = 0
    risk_margin_e6: int = 0
    notional_fee_e6: int = 0
    treasury_fee_e6: int = 0
    days: list[str] = []
    per_day_premium_e6: list[int] = []
    priced_with_ladder_day: str | None = None
    note: str | None = None


class PolicyCreate(Wire):
    quote_id: str
    holder: Address


class Settlement(Wire):
    ref_id: str
    kind: Literal["policy", "residual"]
    day: str
    index: str
    value: int
    unit: str = Field(description="tenthsF (temperature) or wetDay (rain: 1 = wet day, 0 = dry)")
    source: str
    vintage_hash: str
    status: Literal["pending", "reported", "final", "disputed", "void"]
    payout_e6: int


class Policy(Wire):
    policy_id: str
    business_id: str
    holder: Address
    path: HedgePath
    peril: Peril
    strike_tenths_f: int
    cap_tenths_f: int
    days: list[str]
    units: int
    premium_e6: int
    max_payout_e6: int
    status: Literal["active", "settled", "expired"]
    settlements: list[Settlement]
    refunded_e6: int = 0  # downsizing / void refunds already credited


# ---------------------------------------------------------------- auctions


class Level(Wire):
    price_e6: int
    qty: int
    basis_tenths_f: int | None = None


class HouseQuote(Wire):
    bid_e6: int
    ask_e6: int
    max_qty: int
    bid_basis_tenths_f: int | None = None
    ask_basis_tenths_f: int | None = None


class Fill(Wire):
    order_id: str
    trader: Address
    side: Side
    qty: int


class Conservation(Wire):
    long_locked_e6: int
    short_locked_e6: int
    ok: bool


class ClearingResult(Wire):
    price_e6: int | None
    filled_qty: int
    fills: list[Fill]
    pool_filled_qty: int
    conservation: Conservation
    basis_tenths_f: int | None = None  # signed basis price of the clearing tick (SPEC 2), tenths of a degree F


class AuctionSummary(Wire):
    auction_id: str
    contract_id: str
    station_id: str
    day: str
    status: AuctionStatus
    public_cutoff: str
    order_count: int
    range_tenths_f: int | None = None


class Auction(AuctionSummary):
    bids: list[Level]
    asks: list[Level]
    house_quote: HouseQuote | None = None
    result: ClearingResult | None = None


class OrderCreate(Wire):
    trader: Address
    side: Side
    qty: int
    limit_price_e6: int


class Order(Wire):
    order_id: str
    auction_id: str
    trader: Address
    side: Side
    qty: int
    limit_price_e6: int
    locked_e6: int
    status: Literal["open", "filled", "partial", "unfilled", "cancelled"]
    filled_qty: int = 0


# ---------------------------------------------------------------- pool


class ExposureRow(Wire):
    contract_id: str
    net_qty: int
    locked_e6: int


class QueueTicket(Wire):
    ticket_id: str
    kind: Literal["deposit", "withdrawal"]
    owner: Address
    tranche: Tranche
    amount_e6: int | None = None
    shares: int | None = None
    epoch_ts: str
    status: Literal["queued", "processed", "cancelled", "lapsed"]
    # withdrawals only: the engine / PoolVault request id (the {id} of POST /pool/withdraw/{id}/cancel), and the end of
    # the claim window (claimableAt + 3 days; after it anyone may lapse the request and the shares go back to the LP)
    request_id: str | None = None
    claim_by: str | None = None


class NavPoint(Wire):
    ts: str
    senior_nav_e6: int
    junior_nav_e6: int


class PoolQueue(Wire):
    deposits: list[QueueTicket]
    withdrawals: list[QueueTicket]


class PoolState(Wire):
    senior_assets_e6: int
    junior_assets_e6: int
    senior_shares: int
    junior_shares: int
    senior_rate_bp: int
    utilization_bp: int
    locked_e6: int
    free_e6: int
    exposure_by_contract: list[ExposureRow]
    queue: PoolQueue
    nav_history: list[NavPoint]
    capital_e6: int | None = None
    reserved_e6: int | None = None
    deployed_e6: int | None = None
    senior_premium_share_bp: int | None = None  # senior's share of net premium (seniorRateBp carries the same value)


class DepositRequest(Wire):
    owner: Address
    tranche: Tranche
    amount_e6: int


class WithdrawRequest(Wire):
    owner: Address
    tranche: Tranche
    shares: int


class CancelWithdrawRequest(Wire):
    owner: Address


# ---------------------------------------------------------------- positions


class ResidualPosition(Wire):
    contract_id: str
    day: str
    side: Side
    qty: int
    entry_price_e6: int
    locked_e6: int


class LpPosition(Wire):
    tranche: Tranche
    shares: int
    value_e6: int


class Positions(Wire):
    balances: Balances
    policies: list[Policy]
    residuals: list[ResidualPosition]
    lp: list[LpPosition]
    open_orders: list[Order]


# ---------------------------------------------------------------- admin


class HouseQuoteRow(Wire):
    auction_id: str
    bid_e6: int
    ask_e6: int
    max_qty: int


class InventoryRow(Wire):
    contract_id: str
    net_qty: int


class HedgeRow(Wire):
    series: str
    day: str
    rungs: list[Rung]
    cost_e6: int
    payout_e6: int | None = None


class HouseMm(Wire):
    quotes: list[HouseQuoteRow]
    inventory: list[InventoryRow]
    hedges: list[HedgeRow]
    pnl_e6: int
    caps_used: dict[str, float]  # fraction of each cap in use, 0..1 (1.0 = at the cap): C1 utilisation, C3/C4/C5 worst group


class TickRequest(Wire):
    as_of: str | None = None


class TickResult(Wire):
    tick_key: str
    quotes_posted: int
    hedges_placed: int
    events: list[EventSummary]


class OracleRow(Wire):
    index: str
    day: str
    value: int
    source: str
    vintage_hash: str
    fetched_at: str
    status: Literal["pending", "reported", "final", "disputed", "void"]


class OracleReportRequest(Wire):
    index: str
    day: str


# ---------------------------------------------------------------- staking (SPEC 8.7; WI has 18 decimals, so
# WI amounts and staking shares travel as decimal strings)


class Cooldown(Wire):
    request_id: int
    shares: str
    value_wei: str
    claimable_at: str
    claimed: bool
    claimable: bool = False  # cooldown over on the world clock and not yet claimed


class Haircut(Wire):
    day: str
    bps: int
    burned_wei: str


class StakingView(Wire):
    owner: Address | None = None
    wi_balance_wei: str
    staked_shares: str
    staked_value_wei: str
    voting_power_wei: str
    total_staked_wei: str
    total_shares: str
    cooldown_days: int
    haircut_cap_bps: int
    cooldowns: list[Cooldown]
    haircuts: list[Haircut]
    pays_stakers: bool = False
    note: str


class StakeRequest(Wire):
    owner: Address
    amount_wei: str


class UnstakeRequest(Wire):
    owner: Address
    shares: str


class ClaimUnstakeRequest(Wire):
    owner: Address
    request_id: int


class TxConfirm(Wire):
    status: Literal["confirmed", "reverted", "pending"]
    block_number: int
    objects: list[dict[str, str]]


# ---------------------------------------------------------------- concrete Execution types
# Concrete subclasses give readable names in OpenAPI / generated TS.


class BalancesExecution(Execution[Balances]): ...
class PolicyExecution(Execution[Policy]): ...
class OrderExecution(Execution[Order]): ...
class ClearingExecution(Execution[ClearingResult]): ...
class QueueTicketExecution(Execution[QueueTicket]): ...
class OracleRowExecution(Execution[OracleRow]): ...
class StakingExecution(Execution[StakingView]): ...
