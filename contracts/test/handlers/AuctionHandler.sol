// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Test} from "forge-std/Test.sol";
import {MockUSDC} from "../../src/MockUSDC.sol";
import {BatchAuction} from "../../src/BatchAuction.sol";
import {PolicyManager} from "../../src/PolicyManager.sol";
import {OracleAdapter} from "../../src/OracleAdapter.sol";
import {IBatchAuction} from "../../src/interfaces/IBatchAuction.sol";
import {IPolicyManager} from "../../src/interfaces/IPolicyManager.sol";
import {IOracleAdapter} from "../../src/interfaces/IOracleAdapter.sol";

/// @notice Drives random books through place -> clear -> claim -> settle -> claimPosition and keeps
///         independent ghost books (brute-force demand/supply from the raw order list).
contract AuctionHandler is Test {
    uint256 constant UNIT = 1_000_000;
    uint256 constant TICK = 10_000;

    MockUSDC usdc;
    BatchAuction auction;
    PolicyManager pm;
    OracleAdapter oracle;
    uint256 reporterPk;

    bytes32[] public markets;
    mapping(bytes32 => bytes32) public indexOf;
    address[] public actors;
    uint256[] public orderIds;

    // ghosts
    mapping(bytes32 => uint256) public escrowIn;
    mapping(bytes32 => uint256) public movedToPm;
    mapping(bytes32 => uint256) public paidBack; // refunds + fees out of the auction
    mapping(bytes32 => uint256) public claimedBidFill;
    mapping(bytes32 => uint256) public claimedOfferFill;
    mapping(bytes32 => uint256) public claimedCost;
    mapping(bytes32 => uint256) public unclaimed; // orders not yet claimed
    mapping(bytes32 => uint256) public positionPayouts;
    mapping(bytes32 => uint256[100]) internal bidQty;
    mapping(bytes32 => uint256[100]) internal offerQty;
    uint256 public limitViolations;
    uint256 public escrowMismatches;
    uint256 public splitMismatches;
    uint256 public notMaxVolume;
    uint256 public bothSidesMarketable;
    uint256 public doubleClaims;
    uint256 public overPaid;
    uint256 public latePayouts;

    constructor(
        MockUSDC usdc_,
        BatchAuction auction_,
        PolicyManager pm_,
        OracleAdapter oracle_,
        uint256 reporterPk_,
        bytes32[] memory markets_,
        bytes32[] memory indices_
    ) {
        (usdc, auction, pm, oracle, reporterPk) = (usdc_, auction_, pm_, oracle_, reporterPk_);
        markets = markets_;
        for (uint256 i; i < markets_.length; ++i) indexOf[markets_[i]] = indices_[i];
        for (uint256 i; i < 10; ++i) {
            address a = address(uint160(0xA000 + i));
            actors.push(a);
            usdc.mint(a, 1e30);
            vm.prank(a);
            usdc.approve(address(auction), type(uint256).max);
        }
    }

    function place(uint256 actorSeed, uint256 marketSeed, bool isBid, uint256 tick, uint256 qty) external {
        bytes32 m = markets[marketSeed % markets.length];
        IBatchAuction.Book memory b = auction.getBook(m);
        if (block.timestamp >= b.cutoff || auction.publicOrderCount(m) >= 200) return;
        address a = actors[actorSeed % actors.length];
        if (auction.traderOrderCount(m, a) >= 20) return;
        tick = bound(tick, 1, 99);
        qty = bound(qty, 1, 1e6);
        // cluster a third of the orders around 40..42 to force volume / imbalance ties
        if (qty % 3 == 0) tick = 40 + (qty % 3 + tick) % 3;
        uint256 side = isBid ? tick : 100 - tick;
        if (qty * side < 100) qty = (99 + side) / side; // public minimum escrow: 1 USDC
        uint256 before = usdc.balanceOf(a);
        vm.prank(a);
        uint256 id = auction.placeOrder(m, isBid, uint8(tick), uint128(qty));
        uint256 pulled = before - usdc.balanceOf(a);
        uint256 worstLoss = qty * (isBid ? tick : 100 - tick) * TICK;
        uint256 fee = auction.bookFee(m);
        if (pulled != worstLoss + qty * fee) escrowMismatches++;
        escrowIn[m] += pulled;
        unclaimed[m] += 1;
        orderIds.push(id);
        if (isBid) bidQty[m][tick] += qty;
        else offerQty[m][tick] += qty;
    }

    function clear(uint256 marketSeed) external {
        bytes32 m = markets[marketSeed % markets.length];
        IBatchAuction.Book memory b = auction.getBook(m);
        if (b.cleared) return;
        // let books grow before the (shared) cutoff; rarely clear a small or empty book
        if (block.timestamp < b.cutoff && b.orderCount < 25 && marketSeed % 16 != 0) return;
        if (block.timestamp < b.cutoff) vm.warp(b.cutoff);
        auction.clear(m);
        b = auction.getBook(m);
        movedToPm[m] = uint256(b.qStar) * UNIT;
        // brute force from the raw order list: Q* must be the max executable volume, and at p*
        // not both sides can have unfilled marketable quantity.
        uint256 best;
        for (uint256 p = 1; p <= 99; ++p) {
            (uint256 d, uint256 s) = _ds(m, p);
            uint256 v = d < s ? d : s;
            if (v > best) best = v;
        }
        if (best != b.qStar) notMaxVolume++;
        if (b.qStar != 0) {
            (uint256 d, uint256 s) = _ds(m, b.pStar);
            if ((d < s ? d : s) != b.qStar) bothSidesMarketable++;
        }
    }

    function claim(uint256 orderSeed) external {
        if (orderIds.length == 0) return;
        uint256 id = orderIds[orderSeed % orderIds.length];
        IBatchAuction.Order memory o = auction.getOrder(id);
        IBatchAuction.Book memory b = auction.getBook(o.market);
        if (!b.cleared) return;
        if (o.claimed) {
            try auction.claim(id) {
                doubleClaims++;
            } catch {}
            return;
        }
        uint256 before = usdc.balanceOf(address(auction));
        uint256 collBefore = pm.marketCollateral(o.market);
        (uint128 fill, uint256 refund) = auction.claim(id);
        uint256 out = before - usdc.balanceOf(address(auction));
        // a fill claimed after its trader already claimed the position is paid out at once
        if (pm.marketCollateral(o.market) < collBefore) {
            latePayouts++;
            positionPayouts[o.market] += collBefore - pm.marketCollateral(o.market);
            if (positionPayouts[o.market] > movedToPm[o.market]) overPaid++;
        }
        uint256 fee = uint256(fill) * auction.bookFee(o.market);
        uint256 escrow = uint256(o.qty) * ((o.isBid ? uint256(o.tick) : 100 - uint256(o.tick)) * TICK + auction.bookFee(o.market));
        uint256 cost = uint256(fill) * (o.isBid ? uint256(b.pStar) : 100 - uint256(b.pStar)) * TICK;
        if (cost + fee + refund != escrow || out != fee + refund) splitMismatches++;
        if (fill > o.qty) limitViolations++;
        if (fill != 0 && (o.isBid ? o.tick < b.pStar : o.tick > b.pStar)) limitViolations++;
        paidBack[o.market] += out;
        claimedCost[o.market] += cost;
        if (o.isBid) claimedBidFill[o.market] += fill;
        else claimedOfferFill[o.market] += fill;
        unclaimed[o.market] -= 1;
    }

    function settle(uint256 marketSeed, int64 x, bool makeVoid) external {
        bytes32 m = markets[marketSeed % markets.length];
        if (!auction.getBook(m).cleared) return;
        uint32 day = pm.getMarket(m).day;
        bytes32 idx = indexOf[m];
        IOracleAdapter.Observation memory o = oracle.observation(idx, day);
        if (o.finalized || o.voided) return;
        if (makeVoid && !o.posted) {
            uint256 at = uint256(oracle.finalizeAt(idx, day)) + oracle.indexConfig(idx).voidGrace;
            if (block.timestamp < at) vm.warp(at);
            oracle.voidDay(idx, day);
            return;
        }
        _postAndFinalize(idx, day, int64(bound(x, -80, 80)), o.posted ? o.revision + 1 : 0);
    }

    function _postAndFinalize(bytes32 idx, uint32 day, int64 x, uint16 rev) internal {
        uint64 fAt = oracle.fetchAt(idx, day);
        if (block.timestamp < fAt) vm.warp(fAt);
        if (block.timestamp < oracle.finalizeAt(idx, day)) {
            uint64 asOf = uint64(block.timestamp);
            bytes32 digest = oracle.reportDigest(idx, day, x, rev, asOf);
            (uint8 v, bytes32 r, bytes32 s) = vm.sign(reporterPk, digest);
            oracle.post(idx, day, x, rev, asOf, bytes32(0), abi.encodePacked(r, s, v));
        }
        vm.warp(oracle.finalizeAt(idx, day));
        if (oracle.observation(idx, day).posted) oracle.finalize(idx, day);
    }

    function claimPosition(uint256 marketSeed, uint256 actorSeed) external {
        bytes32 m = markets[marketSeed % markets.length];
        address a = actors[actorSeed % actors.length];
        IPolicyManager.Position memory p = pm.positionOf(m, a);
        vm.prank(a);
        try pm.claimPosition(m) returns (uint256 amount) {
            if (p.claimed) doubleClaims++;
            positionPayouts[m] += amount;
            if (positionPayouts[m] > movedToPm[m]) overPaid++;
        } catch {}
    }

    // ---- views for invariants ----
    function marketsLength() external view returns (uint256) {
        return markets.length;
    }

    function _ds(bytes32 m, uint256 p) internal view returns (uint256 d, uint256 s) {
        for (uint256 t = p; t <= 99; ++t) d += bidQty[m][t];
        for (uint256 t = 1; t <= p; ++t) s += offerQty[m][t];
    }
}

