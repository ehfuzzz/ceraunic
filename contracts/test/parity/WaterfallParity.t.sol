// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {FixtureReader} from "./FixtureReader.sol";
import {MockUSDC} from "../../src/MockUSDC.sol";
import {WIToken} from "../../src/WIToken.sol";
import {PoolVault} from "../../src/PoolVault.sol";
import {WIStaking} from "../../src/WIStaking.sol";
import {IPoolVault} from "../../src/interfaces/IPoolVault.sol";

/// @notice SPEC 14 pool parity: each step sequence in waterfall_cases.json (== pool_cases.json) is
///         replayed on a real PoolVault (this test plays the PolicyManager); after every step the
///         ledgers, shares, reserved, deployed, cash, per-day books, result and revert name must equal
///         the engine's exactly.
contract WaterfallParity is FixtureReader {
    address constant HOUSE = address(0x1001);

    struct Params {
        uint256 capBps;
        uint256 haircutCapBps;
        uint256 houseReturnWindow;
        uint256 jMinBps;
        uint256 minJuniorForSenior;
        uint256 seniorPremiumBps;
        uint256 withdrawDelay;
    }

    struct Step {
        address actor;
        uint256 amount;
        uint256 day;
        uint256 loss;
        string op;
        uint256 released;
        uint256 requestId;
        uint256 shares;
        string tranche;
        uint256 ts;
    }

    struct Snap {
        uint256 actorJuniorShares;
        uint256 actorSeniorShares;
        uint256 cash;
        int256 dayPnl;
        uint256 deployed;
        uint256 deployedByDay;
        uint256 junior;
        uint256 juniorSupply;
        uint256 openPolicies;
        uint256 reserved;
        int256 result;
        string revertName; // JSON key "revert" (renamed below)
        uint256 senior;
        uint256 seniorSupply;
    }

    MockUSDC usdc;
    PoolVault pool;
    string caseName;

    function test_waterfallParity() public {
        (bool ok, string memory json) = _fixture("waterfall_cases.json");
        if (!ok) return;
        uint256 n = _count(json, ".cases");
        assertGe(n, 20, "SPEC 14 wants >= 20 pool sequences");
        uint256 steps;
        for (uint256 i; i < n; ++i) {
            string memory base = string.concat(".cases[", vm.toString(i), "]");
            caseName = vm.parseJsonString(json, string.concat(base, ".name"));
            Params memory p = abi.decode(vm.parseJson(json, string.concat(base, ".params")), (Params));
            Step[] memory s = abi.decode(vm.parseJson(json, string.concat(base, ".steps")), (Step[]));
            _setUpVault(p);
            for (uint256 k; k < s.length; ++k) {
                string memory eb = string.concat(base, ".expected[", vm.toString(k), "]");
                _step(s[k], _readSnap(json, eb), k);
                ++steps;
            }
        }
        assertGt(steps, 0);
    }

    function _readSnap(string memory json, string memory eb) internal pure returns (Snap memory e) {
        e.actorJuniorShares = vm.parseJsonUint(json, string.concat(eb, ".actorJuniorShares"));
        e.actorSeniorShares = vm.parseJsonUint(json, string.concat(eb, ".actorSeniorShares"));
        e.cash = vm.parseJsonUint(json, string.concat(eb, ".cash"));
        e.dayPnl = vm.parseJsonInt(json, string.concat(eb, ".dayPnl"));
        e.deployed = vm.parseJsonUint(json, string.concat(eb, ".deployed"));
        e.deployedByDay = vm.parseJsonUint(json, string.concat(eb, ".deployedByDay"));
        e.junior = vm.parseJsonUint(json, string.concat(eb, ".junior"));
        e.juniorSupply = vm.parseJsonUint(json, string.concat(eb, ".juniorSupply"));
        e.openPolicies = vm.parseJsonUint(json, string.concat(eb, ".openPolicies"));
        e.reserved = vm.parseJsonUint(json, string.concat(eb, ".reserved"));
        e.result = vm.parseJsonInt(json, string.concat(eb, ".result"));
        e.revertName = vm.parseJsonString(json, string.concat(eb, ".revert"));
        e.senior = vm.parseJsonUint(json, string.concat(eb, ".senior"));
        e.seniorSupply = vm.parseJsonUint(json, string.concat(eb, ".seniorSupply"));
    }

    function _setUpVault(Params memory p) internal {
        usdc = new MockUSDC();
        pool = new PoolVault(IERC20(address(usdc)), address(this), uint64(p.withdrawDelay), uint64(p.houseReturnWindow));
        WIToken wi = new WIToken(address(this), 1e27);
        WIStaking staking = new WIStaking(address(wi), address(this), 12 days);
        staking.setHaircutCapBps(uint16(p.haircutCapBps));
        staking.setPool(address(pool));
        pool.setPolicyManager(address(this));
        pool.setStaking(address(staking));
        pool.setHouse(HOUSE);
        pool.setJuniorDepositor(HOUSE, true);
        pool.setParams(uint16(p.capBps), uint16(p.jMinBps), uint16(p.seniorPremiumBps), p.minJuniorForSenior);
        vm.prank(HOUSE);
        usdc.approve(address(pool), type(uint256).max);
    }

    function _step(Step memory s, Snap memory e, uint256 k) internal {
        vm.warp(s.ts);
        uint32 day = uint32(s.day);
        bytes32 op = keccak256(bytes(s.op));
        bool ok;
        bytes memory err;
        int256 result;
        if (op == keccak256("depositJunior") || op == keccak256("depositSenior")) {
            usdc.mint(s.actor, s.amount);
            vm.prank(s.actor);
            usdc.approve(address(pool), type(uint256).max);
            vm.prank(s.actor);
            (ok, err) = address(pool).call(
                abi.encodeCall(op == keccak256("depositJunior") ? pool.depositJunior : pool.depositSenior, (s.amount))
            );
            if (ok) result = int256(abi.decode(err, (uint256)));
        } else if (op == keccak256("reserve")) {
            (ok, err) = address(pool).call(abi.encodeCall(pool.reserve, (day, s.amount)));
        } else if (op == keccak256("release")) {
            (ok, err) = address(pool).call(abi.encodeCall(pool.release, (day, s.amount)));
        } else if (op == keccak256("creditPremium")) {
            usdc.mint(address(pool), s.amount); // the PolicyManager transfers first
            (ok, err) = address(pool).call(abi.encodeCall(pool.creditPremium, (day, s.amount)));
            if (ok) result = int256(_senior(err));
        } else if (op == keccak256("absorbLoss")) {
            uint256 j0 = pool.juniorAssets();
            (ok, err) = address(pool).call(abi.encodeCall(pool.absorbLoss, (day, s.released, s.loss, s.actor)));
            if (ok) result = int256(j0 - pool.juniorAssets());
        } else if (op == keccak256("fundHouse")) {
            vm.prank(HOUSE);
            (ok, err) = address(pool).call(abi.encodeCall(pool.fundHouse, (day, s.amount)));
        } else if (op == keccak256("returnFromHouse")) {
            usdc.mint(HOUSE, s.amount);
            vm.prank(HOUSE);
            (ok, err) = address(pool).call(abi.encodeCall(pool.returnFromHouse, (day, s.amount)));
            if (ok) result = abi.decode(err, (int256));
        } else if (op == keccak256("writeOffHouse")) {
            uint256 dep = pool.deployedByDay(day);
            (ok, err) = address(pool).call(abi.encodeCall(pool.writeOffHouse, (day)));
            if (ok) result = int256(dep);
        } else if (op == keccak256("requestWithdraw")) {
            IPoolVault.Tranche t = _eqStr(s.tranche, "junior") ? IPoolVault.Tranche.Junior : IPoolVault.Tranche.Senior;
            vm.prank(s.actor);
            (ok, err) = address(pool).call(abi.encodeCall(pool.requestWithdraw, (t, s.shares)));
            if (ok) result = int256(abi.decode(err, (uint256)));
        } else if (op == keccak256("claimWithdraw")) {
            (ok, err) = address(pool).call(abi.encodeCall(pool.claimWithdraw, (s.requestId)));
            if (ok) result = int256(abi.decode(err, (uint256)));
        } else if (op == keccak256("cancelWithdraw") || op == keccak256("lapseWithdraw")) {
            vm.prank(s.actor);
            (ok, err) = address(pool).call(
                abi.encodeCall(op == keccak256("cancelWithdraw") ? pool.cancelWithdraw : pool.lapseWithdraw, (s.requestId))
            );
        } else if (op == keccak256("closeDay")) {
            (ok, err) = address(pool).call(abi.encodeCall(pool.closeDay, (day)));
            if (ok) result = int256(uint256(abi.decode(err, (uint16))));
        } else {
            revert(string.concat("unknown op ", s.op));
        }
        string memory at = string.concat(caseName, " step ", vm.toString(k), " ", s.op);
        if (bytes(e.revertName).length == 0) {
            assertTrue(ok, string.concat(at, ": reverted, engine accepted"));
        } else {
            assertFalse(ok, string.concat(at, ": accepted, engine reverted ", e.revertName));
            assertEq(_revertName(err), _sel(e.revertName), string.concat(at, ": wrong revert, want ", e.revertName));
        }
        assertEq(result, e.result, string.concat(at, ": result"));
        assertEq(pool.seniorAssets(), e.senior, string.concat(at, ": senior"));
        assertEq(pool.juniorAssets(), e.junior, string.concat(at, ": junior"));
        assertEq(pool.reserved(), e.reserved, string.concat(at, ": reserved"));
        assertEq(pool.deployed(), e.deployed, string.concat(at, ": deployed"));
        assertEq(pool.cash(), e.cash, string.concat(at, ": cash"));
        assertEq(usdc.balanceOf(address(pool)), e.cash, string.concat(at, ": pool USDC balance"));
        assertEq(pool.senior().totalSupply(), e.seniorSupply, string.concat(at, ": seniorSupply"));
        assertEq(pool.totalJuniorShares(), e.juniorSupply, string.concat(at, ": juniorSupply"));
        assertEq(pool.senior().balanceOf(s.actor), e.actorSeniorShares, string.concat(at, ": actor senior shares"));
        assertEq(pool.juniorSharesOf(s.actor), e.actorJuniorShares, string.concat(at, ": actor junior shares"));
        assertEq(pool.dayPnl(day), e.dayPnl, string.concat(at, ": dayPnl"));
        assertEq(pool.openPolicies(day), e.openPolicies, string.concat(at, ": openPolicies"));
        assertEq(pool.deployedByDay(day), e.deployedByDay, string.concat(at, ": deployedByDay"));
    }

    function _senior(bytes memory ret) internal pure returns (uint256 s) {
        (s,) = abi.decode(ret, (uint256, uint256));
    }
}
