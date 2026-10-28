// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {StdInvariant} from "forge-std/StdInvariant.sol";
import {ProtocolFixture} from "./ProtocolFixture.sol";
import {AuctionHandler} from "./handlers/AuctionHandler.sol";
import {IOracleAdapter} from "../src/interfaces/IOracleAdapter.sol";
import {IBatchAuction} from "../src/interfaces/IBatchAuction.sol";

/// @notice M1 (clearing mints or burns value), M3b (under-collateralised orders), M5 (double claim /
///         over-payment) for the auction and its positions. Three books, one with a non-zero fee.
contract AuctionInvariants is StdInvariant, ProtocolFixture {
    AuctionHandler handler;
    bytes32[] markets;

    function setUp() public {
        _deploy();
        bytes32[] memory idx = new bytes32[](3);
        idx[0] = keccak256("PAIR:A-S:TMAX:v1");
        idx[1] = keccak256("PAIR:B-S:TMAX:v1");
        idx[2] = keccak256("RAIN:A-S:IND:v1");
        IOracleAdapter.IndexConfig memory cli =
            IOracleAdapter.IndexConfig({fetchLag: 12 hours, disputeWindow: 24 hours, voidGrace: 72 hours, active: true});
        vm.startPrank(admin);
        for (uint256 i; i < 3; ++i) oracle.registerIndex(idx[i], cli);
        markets.push(pm.createMarket(idx[0], D, -50, 50, true));
        auction.setAuctionFeePerUnit(1_234);
        markets.push(pm.createMarket(idx[1], D, -37, 41, true)); // hi - lo = 78 does not divide UNIT
        auction.setAuctionFeePerUnit(0);
        markets.push(pm.createMarket(idx[2], D, -1, 1, true));
        vm.stopPrank();
        handler = new AuctionHandler(usdc, auction, pm, oracle, REPORTER_PK, markets, idx);
        targetContract(address(handler));
    }

    function invariant_auctionHoldsExactlyUnclaimedEscrow() public view {
        uint256 expected;
        for (uint256 i; i < markets.length; ++i) {
            bytes32 m = markets[i];
            expected += handler.escrowIn(m) - handler.movedToPm(m) - handler.paidBack(m);
        }
        assertEq(usdc.balanceOf(address(auction)), expected);
    }

    function invariant_fillsConserveAndMatchCollateral() public view {
        for (uint256 i; i < markets.length; ++i) {
            bytes32 m = markets[i];
            IBatchAuction.Book memory b = auction.getBook(m);
            assertLe(handler.claimedBidFill(m), b.qStar);
            assertLe(handler.claimedOfferFill(m), b.qStar);
            assertEq(handler.movedToPm(m), uint256(b.qStar) * UNIT);
            if (b.cleared && handler.unclaimed(m) == 0) {
                assertEq(handler.claimedBidFill(m), b.qStar, "sum bid fills != Q*");
                assertEq(handler.claimedOfferFill(m), b.qStar, "sum offer fills != Q*");
                assertEq(handler.claimedCost(m), uint256(b.qStar) * UNIT, "sum costs != Q* * UNIT");
            }
            // collateral never goes negative and payouts never exceed what the auction funded
            assertEq(pm.marketCollateral(m) + handler.positionPayouts(m), handler.movedToPm(m));
        }
    }

    function invariant_noLimitViolationOrBadSplit() public view {
        assertEq(handler.limitViolations(), 0, "fill crossed its limit");
        assertEq(handler.escrowMismatches(), 0, "escrow != worst-case loss + fee");
        assertEq(handler.splitMismatches(), 0, "escrow != cost + fee + refund");
        assertEq(handler.notMaxVolume(), 0, "Q* is not the max executable volume");
        assertEq(handler.bothSidesMarketable(), 0, "unfilled marketable bid and offer at p*");
        assertEq(handler.doubleClaims(), 0, "claimed twice");
        assertEq(handler.overPaid(), 0, "positions paid more than collateral");
    }
}
