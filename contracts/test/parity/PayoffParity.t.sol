// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {FixtureReader} from "./FixtureReader.sol";
import {Payoff} from "../../src/lib/Payoff.sol";

/// @notice SPEC 14 payoff parity: lib/Payoff.sol L(x) and position payouts equal the engine's
///         units.L on every case in payoff_cases.json (negative lo, [0,1], [-1,1], non-dividing spans,
///         int64 extremes, qty up to 2^128 - 1).
contract PayoffParity is FixtureReader {
    struct Case {
        uint256 L; // "L" sorts before lower-case keys
        int256 hi;
        int256 lo;
        uint256 longPayout;
        uint256 qty;
        uint256 shortPayout;
        uint256 sum;
        int256 x;
    }

    function test_payoffParity() public {
        (bool ok, string memory json) = _fixture("payoff_cases.json");
        if (!ok) return;
        Case[] memory cases = abi.decode(vm.parseJson(json, ".cases"), (Case[]));
        assertGe(cases.length, 60, "SPEC 14 wants >= 60 payoff cases");
        for (uint256 i; i < cases.length; ++i) {
            Case memory c = cases[i];
            uint256 l = Payoff.L(int64(c.x), int64(c.lo), int64(c.hi));
            assertEq(l, c.L, string.concat("L case ", vm.toString(i)));
            assertEq(Payoff.payout(c.qty, 0, l), c.longPayout, string.concat("long case ", vm.toString(i)));
            assertEq(Payoff.payout(0, c.qty, l), c.shortPayout, string.concat("short case ", vm.toString(i)));
            assertEq(Payoff.payout(c.qty, c.qty, l), c.sum, string.concat("pair case ", vm.toString(i)));
        }
    }
}
