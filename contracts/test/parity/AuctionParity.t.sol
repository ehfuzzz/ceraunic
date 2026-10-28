// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ProtocolFixture} from "../ProtocolFixture.sol";
import {FixtureReader} from "./FixtureReader.sol";
import {IBatchAuction} from "../../src/interfaces/IBatchAuction.sol";
import {IOracleAdapter} from "../../src/interfaces/IOracleAdapter.sol";

/// @notice SPEC 14 auction parity: every book in auction_cases.json (engine) cleared on-chain gives
///         the same pStar, qStar, tb, to, mb, mo and, per order, ahead, escrow, fill, cost, fee, refund.
contract AuctionParity is ProtocolFixture, FixtureReader {
    // alphabetical field order = forge's JSON object encoding order
    struct OrderIn {
        bool isBid;
        uint256 qty;
        uint256 tick;
    }

    struct OrderOut {
        uint256 ahead;
        uint256 cost;
        uint256 escrow;
        uint256 fee;
        uint256 fill;
        uint256 refund;
    }

    struct Expected {
        uint256 mb;
        uint256 mo;
        OrderOut[] orders;
        uint256 pStar;
        uint256 qStar;
        uint256 tb;
        uint256 tieRangeLen;
        uint256 to;
    }

    struct Case {
        uint256 auctionFeePerUnit;
        Expected expected;
        string name;
        OrderIn[] orders;
        string[] tags;
    }

    function setUp() public {
        _deploy();
        // The house places every book: parity is about clearing and claim math, and house orders are
        // exempt from the public placement limits (min escrow, per-address and 200-order caps).
        vm.prank(house);
        usdc.approve(address(auction), type(uint256).max);
    }

    /// forge-config: default.gas_limit = 9223372036854775807
    function test_auctionParity() public {
        (bool ok, string memory json) = _fixture("auction_cases.json");
        if (!ok) return;
        Case[] memory cases = abi.decode(vm.parseJson(json, ".cases"), (Case[]));
        assertGe(cases.length, 50, "SPEC 14 wants >= 50 books");
        for (uint256 i; i < cases.length; ++i) {
            uint256 snap = vm.snapshotState();
            _run(cases[i], i);
            vm.revertToState(snap);
        }
    }

    function _run(Case memory c, uint256 i) internal {
        vm.warp(T0);
        bytes32 idx = keccak256(abi.encode("auction-parity", i));
        vm.startPrank(admin);
        oracle.registerIndex(
            idx, IOracleAdapter.IndexConfig({fetchLag: 12 hours, disputeWindow: 24 hours, voidGrace: 72 hours, active: true})
        );
        auction.setAuctionFeePerUnit(c.auctionFeePerUnit);
        bytes32 m = pm.createMarket(idx, D, -50, 50, true);
        vm.stopPrank();
        uint256 n = c.orders.length;
        uint256[] memory ids = new uint256[](n);
        for (uint256 j; j < n; ++j) {
            OrderIn memory o = c.orders[j];
            usdc.mint(house, c.expected.orders[j].escrow);
            uint256 b0 = usdc.balanceOf(house);
            vm.prank(house);
            ids[j] = auction.placeOrder(m, o.isBid, uint8(o.tick), uint128(o.qty));
            assertEq(b0 - usdc.balanceOf(house), c.expected.orders[j].escrow, string.concat(c.name, ": escrow"));
            assertEq(auction.getOrder(ids[j]).ahead, c.expected.orders[j].ahead, string.concat(c.name, ": ahead"));
        }
        vm.warp(auction.getBook(m).cutoff);
        auction.clear(m);
        IBatchAuction.Book memory b = auction.getBook(m);
        assertEq(b.pStar, c.expected.pStar, string.concat(c.name, ": pStar"));
        assertEq(b.qStar, c.expected.qStar, string.concat(c.name, ": qStar"));
        assertEq(b.tb, c.expected.tb, string.concat(c.name, ": tb"));
        assertEq(b.to, c.expected.to, string.concat(c.name, ": to"));
        assertEq(b.mb, c.expected.mb, string.concat(c.name, ": mb"));
        assertEq(b.mo, c.expected.mo, string.concat(c.name, ": mo"));
        for (uint256 j; j < n; ++j) {
            OrderOut memory e = c.expected.orders[j];
            uint256 paid0 = pm.positionOf(m, house).paid;
            uint256 t0 = usdc.balanceOf(treasury);
            (uint128 fill, uint256 refund) = auction.claim(ids[j]);
            assertEq(fill, e.fill, string.concat(c.name, ": fill"));
            assertEq(refund, e.refund, string.concat(c.name, ": refund"));
            assertEq(usdc.balanceOf(treasury) - t0, e.fee, string.concat(c.name, ": fee"));
            assertEq(pm.positionOf(m, house).paid - paid0, e.cost, string.concat(c.name, ": cost"));
        }
        assertEq(usdc.balanceOf(address(auction)), 0, string.concat(c.name, ": auction not empty after claims"));
        assertEq(pm.marketCollateral(m), uint256(b.qStar) * UNIT, string.concat(c.name, ": collateral"));
    }
}
