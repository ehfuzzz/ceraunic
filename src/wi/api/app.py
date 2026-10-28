"""FastAPI app: the engine API (09-RESEARCH contract). Routes are transport only: they validate the wire,
pick the world, and call the Ledger adapter chosen once from CHAIN_MODE (Pattern 2):
  sim     -> SimLedger (wi.engine reducer per world; Upstash when UPSTASH_REDIS_REST_URL is set)
  anvil   -> EvmLedger (local contracts; the server signs with anvil's PUBLIC keys)
  testnet -> EvmLedger (calldata only: needs_signature envelopes; the boot guard refuses any key env)
"""
from __future__ import annotations

import os
import re
import secrets
from typing import Mapping

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import catalog as cat
from .envelope import ApiError, Problem, normalize_address
from .models import *  # noqa: F403  (wire models are the contract)
from .models import (
    Peril,
    AdvanceRequest, AdvanceResult, Auction, AuctionStatus, AuctionSummary, Balances, BalancesExecution, Business,
    BusinessCreate, ClaimUnstakeRequest, ClearingExecution, Clock, Config, DepositRequest, Elasticity,
    FaucetRequest, Health, HouseMm, OracleReportRequest, OracleRow, OracleRowExecution, OrderCreate, OrderExecution,
    Policy, PolicyCreate, PolicyExecution, PoolState, Positions, QueueTicketExecution, Quote, QuoteRequest,
    Recommendation, SalesSummary, SalesUpload, Settlement, StakeRequest, StakingExecution, StakingView, TickRequest,
    TickResult, TxConfirm, UnstakeRequest, WithdrawRequest, CancelWithdrawRequest, WorldCreate, WorldInfo,
)
from .store import DEMO

MODES = ("sim", "anvil", "testnet")
PROBLEM_JSON = "application/problem+json"
MAX_SALES_ROWS = 5000
MAX_FAUCET_E6 = cat.MAX_FAUCET_E6


def check_guards(mode: str, env: Mapping[str, str]) -> None:
    """Refuse to boot in unsafe configurations (Pattern 2)."""
    if mode not in MODES:
        raise RuntimeError(f"CHAIN_MODE={mode!r}; expected one of {MODES}")
    if mode == "testnet" and any(re.search("PRIVATE_KEY|MNEMONIC", k, re.I) for k in env):
        raise RuntimeError("testnet engine must hold no keys (PRIVATE_KEY/MNEMONIC env var present)")
    if mode == "anvil" and env.get("VERCEL"):
        raise RuntimeError("anvil mode is local-only")
    if mode == "sim" and env.get("VERCEL") and not env.get("UPSTASH_REDIS_REST_URL"):
        raise RuntimeError("sim on Vercel needs Upstash (in-memory state is per instance)")


def _problem(status: int, code: str, title: str, detail: str | None) -> JSONResponse:
    body = Problem(type=f"https://wi.local/problems/{code.lower()}", title=title, status=status,
                   detail=detail, code=code)  # type: ignore[arg-type]
    return JSONResponse(body.model_dump(by_alias=True, exclude_none=True), status_code=status, media_type=PROBLEM_JSON)


def _bad(detail: str) -> ApiError:
    return ApiError(422, "VALIDATION", "Validation failed", detail)


def _addr(a: str) -> str:
    try:
        return normalize_address(a).lower()
    except ValueError as e:
        raise _bad(str(e)) from None


def _day(s: str) -> int:
    from wi.engine.units import date_to_day

    try:
        return date_to_day(s)
    except ValueError:
        raise _bad(f"{s!r} is not a YYYY-MM-DD day") from None


def _int_str(s: str, name: str) -> int:
    if not re.fullmatch(r"[0-9]{1,40}", s or ""):
        raise _bad(f"{name} must be a non-negative integer string")
    return int(s)


def make_ledger(mode: str, env: Mapping[str, str]):
    if mode == "sim":
        from .ledger.sim import SimLedger
        from .store import store_from_env

        return SimLedger(store_from_env(env), env)
    from .ledger.evm import EvmLedger

    return EvmLedger(mode, env)


def build_router(mode: str, ledger, env: Mapping[str, str]) -> APIRouter:
    r = APIRouter(prefix="/api/v1", responses={"default": {"model": Problem, "description": "RFC 9457 problem"}})
    L = ledger

    def admin_ok(token: str | None) -> bool:
        expected = env.get("ADMIN_TOKEN") or (None if env.get("VERCEL") else "dev-admin")
        return bool(expected and token) and secrets.compare_digest(token.encode(), expected.encode())  # type: ignore[union-attr]

    def admin(x_admin_token: str | None = Header(None, alias="X-Admin-Token")) -> None:
        if not admin_ok(x_admin_token):
            raise ApiError(403, "FORBIDDEN", "Admin token required", "send a valid X-Admin-Token header")

    def world_id(x_wi_world: str = Header(DEMO, alias="X-WI-World")) -> str:
        if not re.fullmatch(r"demo|w_[0-9a-f]{12}", x_wi_world):
            raise _bad("X-WI-World must be 'demo' or a world id from POST /sim/worlds")
        return x_wi_world

    def idem_key(idempotency_key: str | None = Header(None, alias="Idempotency-Key")) -> str | None:
        if idempotency_key is not None and not (1 <= len(idempotency_key) <= 200):
            raise _bad("Idempotency-Key must be 1..200 characters")
        return idempotency_key

    def sim_only() -> None:
        if mode != "sim":
            raise ApiError(409, "MODE_NOT_SIM", "Sim-only route", f"the engine runs in {mode} mode")

    # ------------------------------------------------------------ meta
    @r.get("/health", response_model=Health, tags=["meta"])
    def health() -> Health:
        return L.health()

    @r.get("/config", response_model=Config, tags=["meta"])
    def config() -> Config:
        return L.config()

    # ------------------------------------------------------------ sim world
    @r.post("/sim/worlds", response_model=WorldInfo, tags=["sim"])
    def create_world(body: WorldCreate | None = None) -> WorldInfo:
        if mode == "testnet":  # anvil has one world (the chain); this rewinds it to the post-genesis snapshot
            sim_only()
        return L.new_world()

    @r.post("/sim/worlds/{world}/reset", response_model=WorldInfo, tags=["sim"])
    def reset_world(world: str, x_admin_token: str | None = Header(None, alias="X-Admin-Token")) -> WorldInfo:
        if mode == "testnet":
            sim_only()
        if world == DEMO and not admin_ok(x_admin_token):
            raise ApiError(403, "FORBIDDEN", "Admin token required", "the pinned demo world resets with X-Admin-Token")
        return L.reset_world(world)

    @r.post("/sim/advance", response_model=AdvanceResult, tags=["sim"])
    def advance(body: AdvanceRequest, wid: str = Depends(world_id),
                x_admin_token: str | None = Header(None, alias="X-Admin-Token")) -> AdvanceResult:
        if mode == "testnet":
            raise ApiError(409, "MODE_NOT_SIM", "Sim-only route", "testnet time is the chain's")
        if not 1 <= body.days <= 10:
            raise _bad("days must be 1..10")
        if wid == DEMO and env.get("VERCEL") and not admin_ok(x_admin_token):
            raise ApiError(403, "FORBIDDEN", "Admin token required",
                           "the pinned demo world's clock moves with X-Admin-Token; create a private world to explore")
        return L.advance(wid, body.days)

    @r.get("/sim/clock", response_model=Clock, tags=["sim"])
    def clock(wid: str = Depends(world_id)) -> Clock:
        return L.clock(wid)

    # ------------------------------------------------------------ accounts
    @r.get("/accounts/{address}/balances", response_model=Balances, tags=["accounts"])
    def balances(address: str, wid: str = Depends(world_id)) -> Balances:
        return L.balances(wid, _addr(address))

    @r.post("/faucet", response_model=BalancesExecution, tags=["accounts"])
    def faucet(body: FaucetRequest, wid: str = Depends(world_id)) -> BalancesExecution:
        if not 0 < body.amount_e6 <= MAX_FAUCET_E6:
            raise ApiError(409, "CAP_EXCEEDED", "Faucet cap", f"amountE6 must be 1..{MAX_FAUCET_E6}")
        return L.faucet(wid, body.address.lower(), body.amount_e6, BalancesExecution)

    # ------------------------------------------------------------ onboarding
    @r.post("/businesses", response_model=Business, tags=["onboarding"])
    def create_business(body: BusinessCreate, wid: str = Depends(world_id)) -> Business:
        if not (-90 <= body.lat <= 90 and -180 <= body.lon <= 180) or not body.name.strip():
            raise _bad("name required; lat/lon out of range")
        return L.create_business(wid, body)

    @r.get("/businesses/{business_id}", response_model=Business, tags=["onboarding"])
    def get_business(business_id: str, wid: str = Depends(world_id)) -> Business:
        return L.business(wid, business_id)

    @r.post("/businesses/{business_id}/sales", response_model=SalesSummary, tags=["onboarding"])
    def upload_sales(business_id: str, body: SalesUpload, wid: str = Depends(world_id)) -> SalesSummary:
        if len(body.rows) > MAX_SALES_ROWS:
            raise _bad(f"at most {MAX_SALES_ROWS} rows per upload")
        for row in body.rows:
            _day(row.date)
        return SalesSummary(**L.upload_sales(wid, business_id, body))

    @r.post("/businesses/{business_id}/elasticity", response_model=Elasticity, tags=["onboarding"])
    def elasticity(business_id: str, wid: str = Depends(world_id)) -> Elasticity:
        return L.elasticity(wid, business_id)

    @r.get("/businesses/{business_id}/recommendation", response_model=Recommendation, tags=["onboarding"])
    def recommendation(business_id: str, peril: Peril | None = Query(
            None, description="omit for the suggested temperature cover; 'rain' for the wet-day cover sized from the "
                              "wet-day effect (unitsPerDay = dollars per wet day)"),
            wid: str = Depends(world_id)) -> Recommendation:
        if peril not in (None, "rain"):
            raise _bad("peril may only be 'rain' (omit it for the suggested temperature cover)")
        return L.recommendation(wid, business_id, peril) if peril else L.recommendation(wid, business_id)

    # ------------------------------------------------------------ quotes, policies
    @r.post("/quotes", response_model=Quote, tags=["policies"])
    def create_quote(body: QuoteRequest, wid: str = Depends(world_id)) -> Quote:
        d0, d1 = _day(body.start_day), _day(body.end_day)
        if not 1 <= d1 - d0 + 1 <= 31:
            raise _bad("policy window must be 1..31 days, startDay <= endDay")
        if body.units <= 0 or (body.peril != "rain" and body.cap_tenths_f <= 0):
            raise _bad("units and capTenthsF must be positive")
        return L.quote(wid, body, list(range(d0, d1 + 1)))

    @r.post("/policies", response_model=PolicyExecution, tags=["policies"])
    def buy_policy(body: PolicyCreate, wid: str = Depends(world_id),
                   key: str | None = Depends(idem_key)) -> PolicyExecution:
        return L.buy(wid, body, key, PolicyExecution)

    @r.get("/policies", response_model=list[Policy], tags=["policies"])
    def list_policies(holder: str = Query(...), wid: str = Depends(world_id)) -> list[Policy]:
        return L.policies(wid, _addr(holder))

    @r.get("/policies/{policy_id}", response_model=Policy, tags=["policies"])
    def get_policy(policy_id: str, wid: str = Depends(world_id)) -> Policy:
        return L.policy(wid, policy_id)

    # ------------------------------------------------------------ auctions
    @r.get("/auctions", response_model=list[AuctionSummary], tags=["auctions"])
    def list_auctions(day: str | None = None, status: AuctionStatus | None = None,
                      wid: str = Depends(world_id)) -> list[AuctionSummary]:
        if day:
            _day(day)
        return L.auctions(wid, day, status)

    @r.get("/auctions/{auction_id}", response_model=Auction, tags=["auctions"])
    def get_auction(auction_id: str, wid: str = Depends(world_id)) -> Auction:
        return L.auction(wid, auction_id)

    @r.post("/auctions/{auction_id}/orders", response_model=OrderExecution, tags=["auctions"])
    def post_order(auction_id: str, body: OrderCreate, wid: str = Depends(world_id),
                   key: str | None = Depends(idem_key)) -> OrderExecution:
        if body.qty <= 0:
            raise _bad("qty must be positive")
        if not 10_000 <= body.limit_price_e6 <= 990_000 or body.limit_price_e6 % 10_000:
            raise _bad("limitPriceE6 must be a 1-cent tick between 10000 and 990000")
        return L.post_order(wid, auction_id, body, key, OrderExecution)

    @r.delete("/auctions/{auction_id}/orders/{order_id}", response_model=OrderExecution, tags=["auctions"])
    def cancel_order(auction_id: str, order_id: str, trader: str = Query(...),
                     wid: str = Depends(world_id)) -> OrderExecution:
        return L.cancel_order(wid, auction_id, order_id, _addr(trader), OrderExecution)

    @r.post("/auctions/{auction_id}/clear", response_model=ClearingExecution, tags=["auctions"])
    def clear(auction_id: str, wid: str = Depends(world_id),
              x_admin_token: str | None = Header(None, alias="X-Admin-Token")) -> ClearingExecution:
        return L.clear(wid, auction_id, admin_ok(x_admin_token), ClearingExecution)

    # ------------------------------------------------------------ pool
    @r.get("/pool", response_model=PoolState, tags=["pool"])
    def pool_state(wid: str = Depends(world_id)) -> PoolState:
        return L.pool(wid)

    @r.post("/pool/deposits", response_model=QueueTicketExecution, tags=["pool"])
    def pool_deposit(body: DepositRequest, wid: str = Depends(world_id),
                     key: str | None = Depends(idem_key)) -> QueueTicketExecution:
        if body.amount_e6 <= 0:
            raise _bad("amountE6 must be positive")
        return L.deposit(wid, body, key, QueueTicketExecution)

    @r.post("/pool/withdrawals", response_model=QueueTicketExecution, tags=["pool"])
    def pool_withdraw(body: WithdrawRequest, wid: str = Depends(world_id),
                      key: str | None = Depends(idem_key)) -> QueueTicketExecution:
        if body.shares <= 0:
            raise _bad("shares must be positive")
        return L.withdraw(wid, body, key, QueueTicketExecution)

    @r.post("/pool/withdraw/{request_id}/cancel", response_model=QueueTicketExecution, tags=["pool"])
    def pool_withdraw_cancel(request_id: int, body: CancelWithdrawRequest, wid: str = Depends(world_id),
                             key: str | None = Depends(idem_key)) -> QueueTicketExecution:
        """Owner only, before the request matures: the escrowed shares go back to the LP (PoolVault.cancelWithdraw).
        After maturity the request is claimed by the epoch, or lapses 3 days later (nothing to cancel)."""
        if request_id < 0:
            raise _bad("request id must be non-negative")
        return L.cancel_withdraw(wid, request_id, body, key, QueueTicketExecution)

    # ------------------------------------------------------------ staking (SPEC 8.7)
    @r.get("/staking", response_model=StakingView, tags=["staking"])
    def staking_view(owner: str | None = Query(None), wid: str = Depends(world_id)) -> StakingView:
        return L.staking(wid, _addr(owner) if owner else None)

    @r.post("/staking/stake", response_model=StakingExecution, tags=["staking"])
    def stake(body: StakeRequest, wid: str = Depends(world_id)) -> StakingExecution:
        return L.stake(wid, body.owner.lower(), _int_str(body.amount_wei, "amountWei"), StakingExecution)

    @r.post("/staking/unstake-request", response_model=StakingExecution, tags=["staking"])
    def unstake_request(body: UnstakeRequest, wid: str = Depends(world_id)) -> StakingExecution:
        return L.unstake_request(wid, body.owner.lower(), _int_str(body.shares, "shares"), StakingExecution)

    @r.post("/staking/claim", response_model=StakingExecution, tags=["staking"])
    def unstake_claim(body: ClaimUnstakeRequest, wid: str = Depends(world_id)) -> StakingExecution:
        return L.unstake_claim(wid, body.owner.lower(), body.request_id, StakingExecution)

    # ------------------------------------------------------------ positions, settlements
    @r.get("/positions", response_model=Positions, tags=["positions"])
    def positions(owner: str = Query(...), wid: str = Depends(world_id)) -> Positions:
        return L.positions(wid, _addr(owner))

    @r.get("/settlements", response_model=list[Settlement], tags=["positions"])
    def settlements(owner: str = Query(...), from_day: str | None = Query(None, alias="fromDay"),
                    to_day: str | None = Query(None, alias="toDay"), wid: str = Depends(world_id)) -> list[Settlement]:
        return L.settlements(wid, _addr(owner), from_day, to_day)

    # ------------------------------------------------------------ admin
    @r.get("/admin/house-mm", response_model=HouseMm, tags=["admin"], dependencies=[Depends(admin)])
    def house_mm(wid: str = Depends(world_id)) -> HouseMm:
        return L.house_mm(wid)

    @r.post("/admin/house-mm/tick", response_model=TickResult, tags=["admin"], dependencies=[Depends(admin)])
    def house_mm_tick(body: TickRequest | None = None, wid: str = Depends(world_id)) -> TickResult:
        return L.house_tick(wid)

    @r.get("/admin/oracle", response_model=list[OracleRow], tags=["admin"], dependencies=[Depends(admin)])
    def oracle(wid: str = Depends(world_id)) -> list[OracleRow]:
        return L.oracle(wid)

    @r.post("/admin/oracle/report", response_model=OracleRowExecution, tags=["admin"], dependencies=[Depends(admin)])
    def oracle_report(body: OracleReportRequest, wid: str = Depends(world_id)) -> OracleRowExecution:
        _day(body.day)
        return L.oracle_report(wid, body.index, body.day, OracleRowExecution)

    # ------------------------------------------------------------ tx follow-up
    @r.post("/tx/{tx_hash}/confirm", response_model=TxConfirm, tags=["chain"])
    def tx_confirm(tx_hash: str) -> TxConfirm:
        if not re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash):
            raise _bad("tx hash must be 0x + 64 hex")
        return L.tx_confirm(tx_hash)

    return r


def create_app(mode: str | None = None, env: Mapping[str, str] | None = None, ledger=None) -> FastAPI:
    env = os.environ if env is None else env
    mode = mode or env.get("CHAIN_MODE", "sim")
    check_guards(mode, env)
    app = FastAPI(title="weather-insurance engine API", version=cat.ENGINE_VERSION,
                  openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs")
    ledger = ledger or make_ledger(mode, env)
    app.include_router(build_router(mode, ledger, env))
    app.state.ledger = ledger

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError):
        return _problem(e.status, e.code, e.title, e.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, e: RequestValidationError):
        detail = "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors())
        return _problem(422, "VALIDATION", "Validation failed", detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, e: StarletteHTTPException):
        code = "NOT_FOUND" if e.status_code == 404 else "VALIDATION"
        return _problem(e.status_code, code, str(e.detail), None)

    return app


app = create_app()
