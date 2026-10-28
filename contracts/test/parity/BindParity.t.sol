// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {FixtureReader} from "./FixtureReader.sol";
import {BindMath} from "../../src/lib/BindMath.sol";
import {MockUSDC} from "../../src/MockUSDC.sol";
import {PoolVault} from "../../src/PoolVault.sol";

/// @notice SPEC 14 bind parity (bind_cases.json): boundUnits, refund, keptFee, toPool from the
///         contract's BindMath (the code PolicyManager.bind runs) and the senior/junior split from a real
///         PoolVault.creditPremium equal the engine's policy.bind_amounts.
contract BindParity is FixtureReader {
    struct Expected {
        uint256 boundUnits;
        uint256 juniorPremium;
        uint256 keptFee;
        uint256 refund;
        uint256 seniorPremium;
        uint256 toPool;
    }

    struct Case {
        Expected expected;
        uint256 fee;
        uint256 fill;
        uint256 h;
        uint256 premium;
        uint256 seniorPremiumBps;
        uint256 units;
    }

    function test_bindParity() public {
        (bool ok, string memory json) = _fixture("bind_cases.json");
        if (!ok) return;
        Case[] memory cases = abi.decode(vm.parseJson(json, ".cases"), (Case[]));
        assertGe(cases.length, 15, "SPEC 14 wants >= 15 bind cases");
        MockUSDC usdc = new MockUSDC();
        for (uint256 i; i < cases.length; ++i) {
            Case memory c = cases[i];
            string memory at = string.concat("bind case ", vm.toString(i));
            uint256 bound = BindMath.boundUnits(c.units, c.fill, c.h);
            (, uint256 refund, uint256 keptFee, uint256 toPool) = BindMath.split(c.premium, c.fee, c.units, bound);
            assertEq(bound, c.expected.boundUnits, string.concat(at, ": boundUnits"));
            assertEq(refund, c.expected.refund, string.concat(at, ": refund"));
            assertEq(keptFee, c.expected.keptFee, string.concat(at, ": keptFee"));
            assertEq(toPool, c.expected.toPool, string.concat(at, ": toPool"));
            PoolVault pool = new PoolVault(IERC20(address(usdc)), address(this), 12 days, 10 days);
            pool.setPolicyManager(address(this));
            pool.setParams(8000, 2000, uint16(c.seniorPremiumBps), 0);
            (uint256 s, uint256 j) = toPool == 0 ? (0, 0) : pool.creditPremium(20_000, toPool);
            assertEq(s, c.expected.seniorPremium, string.concat(at, ": senior premium"));
            assertEq(j, c.expected.juniorPremium, string.concat(at, ": junior premium"));
            assertEq(pool.seniorAssets(), s);
            assertEq(pool.juniorAssets(), j);
        }
    }
}
