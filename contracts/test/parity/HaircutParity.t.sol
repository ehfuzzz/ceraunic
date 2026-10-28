// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {FixtureReader} from "./FixtureReader.sol";
import {MockUSDC} from "../../src/MockUSDC.sol";
import {WIToken} from "../../src/WIToken.sol";
import {PoolVault} from "../../src/PoolVault.sol";
import {WIStaking} from "../../src/WIStaking.sol";

/// @dev Test-only: sets the junior ledger and a day's P&L directly (the waterfall that produces them
///      is covered by WaterfallParity); closeDay and the staking haircut run unmodified.
contract PoolVaultHarness is PoolVault {
    constructor(IERC20 usdc_) PoolVault(usdc_, msg.sender, 12 days, 10 days) {}

    function forceDay(uint32 day, uint256 junior, int256 pnl) external {
        juniorAssets = junior;
        dayPnl[day] = pnl;
    }
}

/// @notice SPEC 14 haircut parity (haircut_cases.json): PoolVault.closeDay -> WIStaking.haircut gives
///         the engine's bps, burned amount, totals, and per-owner active / cooldown shares and values
///         (cooldown value = what claimUnstake actually pays).
contract HaircutParity is FixtureReader {
    uint32 constant D = 20_000;

    struct Pos {
        uint256 activeShares;
        uint256 activeValue;
        uint256 cooldownShares;
        uint256 cooldownValue;
        address owner;
    }

    WIStaking staking;
    PoolVaultHarness pool;
    string caseName;

    function test_haircutParity() public {
        (bool ok, string memory json) = _fixture("haircut_cases.json");
        if (!ok) return;
        uint256 n = _count(json, ".cases");
        assertGe(n, 10, "SPEC 14 wants >= 10 haircut cases");
        for (uint256 i; i < n; ++i) _case(json, string.concat(".cases[", vm.toString(i), "]"));
    }

    function _case(string memory json, string memory base) internal {
        caseName = vm.parseJsonString(json, string.concat(base, ".name"));
        vm.warp(uint256(D) * 1 days);
        WIToken wi = new WIToken(address(this), 1e40);
        staking = new WIStaking(address(wi), address(this), 12 days);
        staking.setHaircutCapBps(uint16(vm.parseJsonUint(json, string.concat(base, ".haircutCapBps"))));
        pool = new PoolVaultHarness(IERC20(address(new MockUSDC())));
        pool.setStaking(address(staking));
        staking.setPool(address(pool));
        uint256 ns = _count(json, string.concat(base, ".stakes"));
        for (uint256 k; k < ns; ++k) {
            string memory sb = string.concat(base, ".stakes[", vm.toString(k), "]");
            address o = vm.parseJsonAddress(json, string.concat(sb, ".owner"));
            uint256 amt = vm.parseJsonUint(json, string.concat(sb, ".amount"));
            wi.transfer(o, amt);
            vm.startPrank(o);
            wi.approve(address(staking), amt);
            staking.stake(amt);
            vm.stopPrank();
        }
        uint256 nc = _count(json, string.concat(base, ".cooldowns"));
        for (uint256 k; k < nc; ++k) {
            string memory cb = string.concat(base, ".cooldowns[", vm.toString(k), "]");
            address o = vm.parseJsonAddress(json, string.concat(cb, ".owner"));
            uint256 div = vm.parseJsonUint(json, string.concat(cb, ".shareDivisor"));
            uint256 sh = staking.sharesOf(o) / div;
            vm.prank(o);
            staking.requestUnstake(sh);
        }
        pool.forceDay(
            D,
            vm.parseJsonUint(json, string.concat(base, ".juniorAssetsAtClose")),
            vm.parseJsonInt(json, string.concat(base, ".dayPnl"))
        );
        uint256 before = staking.totalStaked();
        vm.warp(uint256(D + 1) * 1 days);
        uint16 bps = pool.closeDay(D);
        string memory eb = string.concat(base, ".expected");
        assertEq(bps, vm.parseJsonUint(json, string.concat(eb, ".haircutBps")), string.concat(caseName, ": bps"));
        assertEq(before, vm.parseJsonUint(json, string.concat(eb, ".totalStakedBefore")), string.concat(caseName, ": staked before"));
        assertEq(staking.totalBurned(), vm.parseJsonUint(json, string.concat(eb, ".burned")), string.concat(caseName, ": burned"));
        assertEq(staking.totalStaked(), vm.parseJsonUint(json, string.concat(eb, ".totalStakedAfter")), string.concat(caseName, ": staked after"));
        assertEq(staking.totalShares(), vm.parseJsonUint(json, string.concat(eb, ".totalShares")), string.concat(caseName, ": total shares"));
        Pos[] memory ps = abi.decode(vm.parseJson(json, string.concat(eb, ".positions")), (Pos[]));
        for (uint256 k; k < ps.length; ++k) _position(ps[k]);
    }

    function _position(Pos memory p) internal {
        string memory at = string.concat(caseName, ": ", vm.toString(p.owner));
        assertEq(staking.sharesOf(p.owner), p.activeShares, string.concat(at, " active shares"));
        assertEq(staking.votingPower(p.owner), p.activeValue, string.concat(at, " active value"));
        uint256[] memory ids = staking.unstakeIdsOf(p.owner);
        uint256 coolShares;
        for (uint256 j; j < ids.length; ++j) coolShares += staking.getUnstakeRequest(ids[j]).shares;
        assertEq(coolShares, p.cooldownShares, string.concat(at, " cooldown shares"));
        if (ids.length == 0) {
            assertEq(p.cooldownValue, 0);
            return;
        }
        uint256 snap = vm.snapshotState();
        vm.warp(block.timestamp + staking.unstakeCooldown());
        uint256 paid = staking.claimUnstake(ids[0]); // one request per owner in the fixture
        vm.revertToState(snap);
        assertEq(paid, p.cooldownValue, string.concat(at, " cooldown value (claimUnstake)"));
    }
}
