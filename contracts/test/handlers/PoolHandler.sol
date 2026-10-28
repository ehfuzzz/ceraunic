// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Test} from "forge-std/Test.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {MockUSDC} from "../../src/MockUSDC.sol";
import {PoolVault} from "../../src/PoolVault.sol";
import {PolicyManager} from "../../src/PolicyManager.sol";
import {BatchAuction} from "../../src/BatchAuction.sol";
import {OracleAdapter} from "../../src/OracleAdapter.sol";
import {IPoolVault} from "../../src/interfaces/IPoolVault.sol";
import {IPolicyManager} from "../../src/interfaces/IPolicyManager.sol";
import {IBatchAuction} from "../../src/interfaces/IBatchAuction.sol";
import {IOracleAdapter} from "../../src/interfaces/IOracleAdapter.sol";

/// @notice Random policy lifecycles over 4 climate days: buy at signed quotes, house residual orders,
///         clear, bind (downsizing), finalize or void, settle, house fund/return/write-off, LP
///         deposits and withdrawals, day close, donations. Ghosts record every waterfall step.
contract PoolHandler is Test {
    uint256 constant UNIT = 1_000_000;

    struct Keys {
        uint256 house;
        uint256 reporter;
    }

    MockUSDC public usdc;
    PoolVault public pool;
    PolicyManager public pm;
    BatchAuction public auction;
    OracleAdapter public oracle;
    Keys keys;
    address public house;
    address public treasury;
    bytes32 public idxLoc;
    bytes32 public idxBasis;
    uint32 public day0;

    address[] public buyers;
    uint256 public lapseMovedCash; // a cancel or lapse changed pool cash (must stay 0)
    address[] public lps;
    uint256[] public policyIds;
    uint256[] public houseOrders;
    uint256[] public withdrawIds;
    uint256 nonce;

    // ghosts
    uint256 public donated;
    uint256 public minted;
    uint256 public seniorHitWhileJuniorLeft;
    uint256 public juniorHitMismatch;
    uint256 public capBrokenAfterVoluntary;
    uint256 public bindIdentityBroken;
    uint256 public overPaidPolicy;
    uint256 public doubleSettled;
    uint256 public settledCount;
    uint256 public boundCount;
    uint256 public voidCount;
    mapping(uint256 => uint256) public paidToPolicy;

    constructor(
        MockUSDC usdc_,
        PoolVault pool_,
        PolicyManager pm_,
        BatchAuction auction_,
        OracleAdapter oracle_,
        uint256 housePk,
        uint256 reporterPk,
        address treasury_,
        bytes32 idxLoc_,
        bytes32 idxBasis_,
        uint32 day0_
    ) {
        (usdc, pool, pm, auction, oracle) = (usdc_, pool_, pm_, auction_, oracle_);
        keys = Keys(housePk, reporterPk);
        house = vm.addr(housePk);
        (treasury, idxLoc, idxBasis, day0) = (treasury_, idxLoc_, idxBasis_, day0_);
        for (uint256 i; i < 4; ++i) {
            buyers.push(address(uint160(0xB000 + i)));
            lps.push(address(uint160(0xC000 + i)));
            _approveAll(buyers[i]);
            _approveAll(lps[i]);
        }
        _approveAll(house);
        _mint(house, 1e13);
        for (uint256 i; i < 4; ++i) _mint(buyers[i], 1e12);
    }

    function _approveAll(address a) internal {
        vm.startPrank(a);
        usdc.approve(address(pool), type(uint256).max);
        usdc.approve(address(pm), type(uint256).max);
        usdc.approve(address(auction), type(uint256).max);
        vm.stopPrank();
    }

    function _mint(address a, uint256 amt) internal {
        usdc.mint(a, amt);
        minted += amt;
    }

    uint32 constant DAYS = 8;
    uint32[] public fundedDays;

    function _day(uint256 seed) internal view returns (uint32) {
        return day0 + uint32(seed % DAYS);
    }

    /// @dev Earliest day whose policy sales are still open, plus 0 or 1 (keeps time moving slowly).
    function _openDay(uint256 seed) internal view returns (uint32 d, bool ok) {
        for (d = day0; d < day0 + DAYS; ++d) {
            if (block.timestamp < pm.getMarket(_locMarket(d, false)).saleCutoff) {
                d += uint32(seed % 2);
                return (d, d < day0 + DAYS);
            }
        }
    }

    function _policyDay(uint256 seed) internal view returns (uint32 d, bool ok) {
        if (policyIds.length == 0) return (0, false);
        return (pm.getMarket(pm.getPolicy(policyIds[seed % policyIds.length]).market).day, true);
    }

    function _locMarket(uint32 d, bool put) internal view returns (bytes32) {
        return put ? pm.marketIdOf(idxLoc, d, 650, 700) : pm.marketIdOf(idxLoc, d, 880, 940);
    }

    function _basisMarket(uint32 d) internal view returns (bytes32) {
        return pm.marketIdOf(idxBasis, d, -50, 50);
    }

    /// @dev C1 after every voluntary action; C2 after new risk, senior deposits, junior withdrawals
    ///      (a junior deposit only improves C2, so it may leave a loss-broken C2 still broken).
    function _checkCaps() internal {
        _checkCaps(true);
    }

    function _checkCaps(bool c2) internal {
        uint256 cap = pool.capital();
        if ((pool.reserved() + pool.deployed()) * 10_000 > uint256(pool.capBps()) * cap) capBrokenAfterVoluntary++;
        if (c2 && pool.juniorAssets() * 10_000 < uint256(pool.jMinBps()) * cap) capBrokenAfterVoluntary++;
    }

    // ------------------------------------------------------------------ actions

    function buy(uint256 buyerSeed, uint256 daySeed, bool put, uint256 units, uint256 premiumBps, uint256 feeBps)
        external
    {
        (uint32 d, bool ok) = _openDay(daySeed);
        if (!ok) return;
        bytes32 m = _locMarket(d, put);
        if (block.timestamp >= pm.getMarket(m).saleCutoff) return;
        units = bound(units, 1, 20_000);
        uint256 maxP = units * UNIT;
        uint128 premium = uint128(Math.mulDiv(maxP, bound(premiumBps, 1, 10_000), 10_000));
        uint128 fee = uint128(Math.mulDiv(premium, bound(feeBps, 0, 10_000), 10_000));
        address buyer = buyers[buyerSeed % buyers.length];
        IPolicyManager.Quote memory q =
            IPolicyManager.Quote(m, buyer, !put, uint128(units), premium, fee, uint64(block.timestamp + 1 hours), ++nonce);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(keys.house, pm.quoteDigest(q));
        vm.prank(buyer);
        try pm.buyPolicy(q, abi.encodePacked(r, s, v)) returns (uint256 id) {
            policyIds.push(id);
            _checkCaps();
        } catch {}
    }

    function houseOrder(uint256 daySeed, uint256 tick, uint256 h, bool isBid) external {
        (uint32 d, bool ok) = _openDay(daySeed);
        if (!ok) return;
        bytes32 m = _basisMarket(d);
        IBatchAuction.Book memory b = auction.getBook(m);
        if (block.timestamp >= b.houseCutoff || b.orderCount >= 200) return;
        vm.prank(house);
        houseOrders.push(auction.placeOrder(m, isBid, uint8(bound(tick, 1, 99)), uint128(bound(h, 1, 50))));
    }

    function publicOrder(uint256 daySeed, uint256 buyerSeed, uint256 tick, uint256 qty, bool isBid) external {
        (uint32 d, bool ok) = _openDay(daySeed);
        if (!ok) return;
        bytes32 m = _basisMarket(d);
        IBatchAuction.Book memory b = auction.getBook(m);
        address who = buyers[buyerSeed % buyers.length];
        if (block.timestamp >= b.cutoff || auction.publicOrderCount(m) >= 200) return;
        if (auction.traderOrderCount(m, who) >= 20) return;
        tick = bound(tick, 1, 99);
        qty = bound(qty, 1, 50);
        uint256 side = isBid ? tick : 100 - tick;
        if (qty * side < 100) qty = (99 + side) / side; // public minimum escrow: 1 USDC
        vm.prank(who);
        auction.placeOrder(m, isBid, uint8(tick), uint128(qty));
    }

    function clear(uint256 daySeed) external {
        (uint32 d, bool ok) = _policyDay(daySeed);
        if (!ok) return;
        bytes32 m = _basisMarket(d);
        IBatchAuction.Book memory b = auction.getBook(m);
        if (b.cleared) return;
        if (block.timestamp < b.cutoff) vm.warp(b.cutoff);
        auction.clear(m);
    }

    function bind(uint256 policySeed, uint256 orderSeed, bool useOrder, bool late) external {
        if (policyIds.length == 0) return;
        uint256 id = policyIds[policySeed % policyIds.length];
        IPolicyManager.Policy memory p = pm.getPolicy(id);
        if (p.status != IPolicyManager.PolicyStatus.Bought) return;
        IPolicyManager.Market memory m = pm.getMarket(p.market);
        if (oracle.isVoid(m.indexId, m.day)) return; // bind reverts DayVoid; settle refunds the full premium
        uint256 rid;
        address caller = house;
        if (late || block.timestamp >= m.bindBy) {
            if (block.timestamp < m.bindBy) vm.warp(m.bindBy);
            caller = address(0xBEEF); // anyone, full units
        } else if (useOrder && houseOrders.length != 0) {
            rid = houseOrders[orderSeed % houseOrders.length];
            IBatchAuction.Order memory o = auction.getOrder(rid);
            if (pm.orderUsed(rid) || pm.getMarket(o.market).day != m.day) return;
            if (!auction.getBook(o.market).cleared) {
                IBatchAuction.Book memory b = auction.getBook(o.market);
                if (b.cutoff >= m.bindBy) return;
                if (block.timestamp < b.cutoff) vm.warp(b.cutoff);
                auction.clear(o.market);
            }
        }
        uint256 buyerBefore = usdc.balanceOf(p.buyer);
        uint256 treasBefore = usdc.balanceOf(treasury);
        uint256 capBefore = pool.capital();
        uint256 resBefore = pool.reserved();
        vm.prank(caller);
        uint128 bound_ = pm.bind(id, rid);
        boundCount++;
        uint256 refund = usdc.balanceOf(p.buyer) - buyerBefore;
        uint256 keptFee = usdc.balanceOf(treasury) - treasBefore;
        uint256 toPool = pool.capital() - capBefore;
        // I10: refund + kept == premium, keptFee + toPool == kept, bound <= units; reserve released for cut units
        if (refund + keptFee + toPool != p.premium) bindIdentityBroken++;
        if (bound_ > p.units) bindIdentityBroken++;
        if (resBefore - pool.reserved() != uint256(p.units - bound_) * UNIT) bindIdentityBroken++;
        if (rid == 0 && bound_ != p.units) bindIdentityBroken++;
    }

    function finalizeDay(uint256 daySeed, int64 xLoc, int64 xBasis) external {
        (uint32 d, bool ok) = _policyDay(daySeed);
        if (!ok) return;
        _finalize(idxLoc, d, int64(bound(xLoc, 600, 1000)));
        _finalize(idxBasis, d, int64(bound(xBasis, -80, 80)));
    }

    function voidDay(uint256 daySeed) external {
        if (daySeed % 4 != 0) return; // voids jump 4+ days: keep them rare
        (uint32 d, bool ok) = _policyDay(daySeed / 4);
        if (!ok) return;
        IOracleAdapter.Observation memory o = oracle.observation(idxLoc, d);
        if (o.posted || o.voided) return;
        uint256 at = uint256(oracle.finalizeAt(idxLoc, d)) + oracle.indexConfig(idxLoc).voidGrace;
        if (block.timestamp < at) vm.warp(at);
        oracle.voidDay(idxLoc, d);
    }

    function settle(uint256 policySeed) external {
        if (policyIds.length == 0) return;
        uint256 id = policyIds[policySeed % policyIds.length];
        IPolicyManager.Policy memory p = pm.getPolicy(id);
        (uint256 j0, uint256 s0) = (pool.juniorAssets(), pool.seniorAssets());
        uint256 buyerBefore = usdc.balanceOf(p.buyer);
        try pm.settlePolicy(id) returns (uint256 payout) {
            if (paidToPolicy[id] != 0 || p.status == IPolicyManager.PolicyStatus.Settled
                    || p.status == IPolicyManager.PolicyStatus.Voided) doubleSettled++;
            paidToPolicy[id] = payout + 1;
            settledCount++;
            if (usdc.balanceOf(p.buyer) - buyerBefore != payout) overPaidPolicy++;
            uint256 maxP = uint256(p.status == IPolicyManager.PolicyStatus.Bound ? p.boundUnits : p.units) * UNIT;
            if (p.status == IPolicyManager.PolicyStatus.Bound && payout > maxP) overPaidPolicy++;
            if (p.status == IPolicyManager.PolicyStatus.Bound) {
                if (pm.getPolicy(id).status == IPolicyManager.PolicyStatus.Voided) voidCount++;
                _checkWaterfall(j0, s0, payout);
            }
        } catch {}
    }

    function fundHouse(uint256 daySeed, uint256 amount) external {
        amount = bound(amount, 1, 5_000 * UNIT);
        (uint32 d, bool ok) = _openDay(daySeed);
        if (!ok) return;
        vm.prank(house);
        try pool.fundHouse(d, amount) {
            fundedDays.push(d);
            _checkCaps();
        } catch {}
    }

    function returnHouse(uint256 daySeed, uint256 amount) external {
        if (fundedDays.length == 0) return;
        uint32 d = fundedDays[daySeed % fundedDays.length];
        uint256 dep = pool.deployedByDay(d);
        amount = bound(amount, 0, dep * 2 + 1);
        (uint256 j0, uint256 s0) = (pool.juniorAssets(), pool.seniorAssets());
        vm.prank(house);
        try pool.returnFromHouse(d, amount) returns (int256 pnl) {
            if (pnl < 0) _checkWaterfall(j0, s0, uint256(-pnl));
        } catch {}
    }

    function writeOff(uint256 daySeed) external {
        if (fundedDays.length == 0 || daySeed % 4 != 0) return; // 10-day jump: keep rare
        uint32 d = fundedDays[(daySeed / 4) % fundedDays.length];
        uint256 dep = pool.deployedByDay(d);
        if (dep == 0) return;
        uint256 at = uint256(d) * 1 days + pool.houseReturnWindow();
        if (block.timestamp < at) vm.warp(at);
        (uint256 j0, uint256 s0) = (pool.juniorAssets(), pool.seniorAssets());
        pool.writeOffHouse(d);
        _checkWaterfall(j0, s0, dep);
    }

    function deposit(uint256 lpSeed, bool junior, uint256 amount) external {
        amount = bound(amount, 1, 20_000 * UNIT);
        address lp = junior ? house : lps[lpSeed % lps.length];
        _mint(lp, amount);
        vm.prank(lp);
        (bool ok,) = address(pool).call(
            abi.encodeCall(junior ? pool.depositJunior : pool.depositSenior, (amount))
        );
        if (ok) _checkCaps(!junior);
    }

    function requestWithdraw(uint256 lpSeed, bool junior, uint256 fracBps) external {
        address lp = junior ? house : lps[lpSeed % lps.length];
        uint256 bal = junior ? pool.juniorSharesOf(lp) : pool.senior().balanceOf(lp);
        uint256 shares = Math.mulDiv(bal, bound(fracBps, 1, 10_000), 10_000);
        if (shares == 0) return;
        vm.prank(lp);
        withdrawIds.push(pool.requestWithdraw(junior ? IPoolVault.Tranche.Junior : IPoolVault.Tranche.Senior, shares));
    }

    function claimWithdraw(uint256 seed) external {
        if (withdrawIds.length == 0) return;
        uint256 id = withdrawIds[seed % withdrawIds.length];
        IPoolVault.WithdrawRequest memory r = pool.getWithdrawRequest(id);
        if (block.timestamp < r.claimableAt) vm.warp(r.claimableAt);
        try pool.claimWithdraw(id) {
            _checkCaps(r.tranche == IPoolVault.Tranche.Junior);
        } catch {}
    }

    /// Cancel before maturity (owner) or lapse after the claim window (anyone): shares go back, no USDC moves.
    function cancelOrLapseWithdraw(uint256 seed) external {
        if (withdrawIds.length == 0) return;
        uint256 id = withdrawIds[seed % withdrawIds.length];
        IPoolVault.WithdrawRequest memory r = pool.getWithdrawRequest(id);
        if (r.claimed) return;
        uint256 cash0 = pool.cash();
        if (block.timestamp < r.claimableAt) {
            vm.prank(r.owner);
            pool.cancelWithdraw(id);
        } else {
            uint256 endAt = uint256(r.claimableAt) + pool.CLAIM_WINDOW();
            if (block.timestamp < endAt) vm.warp(endAt);
            pool.lapseWithdraw(id);
        }
        if (pool.cash() != cash0) lapseMovedCash++;
    }

    function closeDay(uint256 daySeed) external {
        (uint32 d, bool ok) = _policyDay(daySeed);
        if (!ok) d = _day(daySeed);
        try pool.closeDay(d) {} catch {}
    }

    function donate(uint256 amount) external {
        amount = bound(amount, 1, 1_000 * UNIT);
        _mint(address(this), amount);
        usdc.transfer(address(pool), amount);
        donated += amount;
    }

    function skipTime(uint256 dt) external {
        vm.warp(block.timestamp + bound(dt, 1, 12 hours));
    }

    // ------------------------------------------------------------------ helpers

    function _finalize(bytes32 idx, uint32 d, int64 x) internal {
        IOracleAdapter.Observation memory o = oracle.observation(idx, d);
        if (o.finalized || o.voided) return;
        uint64 fAt = oracle.fetchAt(idx, d);
        if (block.timestamp < fAt) vm.warp(fAt);
        if (block.timestamp < oracle.finalizeAt(idx, d)) {
            uint16 rev = o.posted ? o.revision + 1 : 0;
            uint64 asOf = uint64(block.timestamp);
            bytes32 digest = oracle.reportDigest(idx, d, x, rev, asOf);
            (uint8 v, bytes32 r, bytes32 s) = vm.sign(keys.reporter, digest);
            oracle.post(idx, d, x, rev, asOf, bytes32(0), abi.encodePacked(r, s, v));
        }
        if (!oracle.observation(idx, d).posted) return;
        vm.warp(oracle.finalizeAt(idx, d));
        oracle.finalize(idx, d);
    }

    /// @dev A loss of `l`: junior must drop by exactly min(l, j0); senior only by the rest.
    function _checkWaterfall(uint256 j0, uint256 s0, uint256 l) internal {
        uint256 j1 = pool.juniorAssets();
        uint256 s1 = pool.seniorAssets();
        uint256 jHit = l < j0 ? l : j0;
        if (j0 - j1 != jHit || s0 - s1 != l - jHit) juniorHitMismatch++;
        if (s1 < s0 && j1 != 0) seniorHitWhileJuniorLeft++;
    }

    function knownBalances() external view returns (uint256 sum) {
        sum = usdc.balanceOf(address(pool)) + usdc.balanceOf(address(pm)) + usdc.balanceOf(address(auction))
            + usdc.balanceOf(house) + usdc.balanceOf(treasury) + usdc.balanceOf(address(this));
        for (uint256 i; i < 4; ++i) sum += usdc.balanceOf(buyers[i]) + usdc.balanceOf(lps[i]);
    }
}
