// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ProtocolFixture} from "./ProtocolFixture.sol";
import {PoolVault} from "../src/PoolVault.sol";

/// @notice WI haircut on a closed day's net junior loss (SPEC 8.7): never above the cap, burns exactly
///         the pro-rata amount (cooldown shares included), conserves WI, one close per day.
contract StakingHaircut is ProtocolFixture {
    address a = address(0xA1);
    address b = address(0xB1);

    function setUp() public {
        _deploy();
    }

    function _value(uint256 shares) internal view returns (uint256) {
        return shares * (staking.totalStaked() + 1) / (staking.totalShares() + 1e6);
    }

    function testFuzz_haircutCappedProRataAndConserving(uint256 junior, uint256 lossBps, uint256 sa, uint256 sb, uint16 cap)
        public
    {
        junior = bound(junior, 1_000 * UNIT, 1_000_000 * UNIT);
        sa = bound(sa, 1 ether, 100_000_000 ether);
        sb = bound(sb, 1 ether, 100_000_000 ether);
        cap = uint16(bound(cap, 0, 10_000));
        vm.prank(admin);
        staking.setHaircutCapBps(cap);
        _seedPool(junior, 0);
        vm.startPrank(admin);
        wi.transfer(a, sa);
        wi.transfer(b, sb);
        vm.stopPrank();
        vm.startPrank(a);
        wi.approve(address(staking), sa);
        uint256 shA = staking.stake(sa);
        vm.stopPrank();
        vm.startPrank(b);
        wi.approve(address(staking), sb);
        uint256 shB = staking.stake(sb);
        staking.requestUnstake(shB); // all of b's shares in cooldown: still cuttable
        vm.stopPrank();

        // house loses `loss` of the day's deployment (<= 80% of capital under C1)
        uint256 loss = junior * bound(lossBps, 1, 8_000) / 10_000;
        vm.startPrank(house);
        pool.fundHouse(D, loss);
        pool.returnFromHouse(D, 0);
        vm.stopPrank();

        uint256 stakedBefore = staking.totalStaked();
        uint256 supplyBefore = wi.totalSupply();
        uint256 va = _value(shA);
        uint256 vb = _value(shB);
        vm.warp(uint256(D + 1) * 1 days);
        uint16 bps = pool.closeDay(D);
        uint256 burned = stakedBefore - staking.totalStaked();

        assertLe(bps, cap, "haircut above cap");
        assertLe(burned * 10_000, stakedBefore * cap, "burned more than the cap allows");
        assertEq(burned, stakedBefore * bps / 10_000, "burn is not the pro-rata amount");
        assertEq(supplyBefore - wi.totalSupply(), burned, "WI not actually burned");
        assertEq(wi.totalSupply() + staking.totalBurned(), 1_000_000_000 ether, "WI conservation");
        assertEq(wi.balanceOf(address(staking)), staking.totalStaked());
        // each position (cooldown included) loses at most its pro-rata share, +1 base unit of rounding
        assertLe(va - _value(shA), va * bps / 10_000 + 1);
        assertLe(vb - _value(shB), vb * bps / 10_000 + 1);
        assertGe(va - _value(shA) + 1, va * bps / 10_000 >= 1 ? va * bps / 10_000 - 1 : 0);
        // once per day
        vm.expectRevert(PoolVault.DayAlreadyClosed.selector);
        pool.closeDay(D);
    }

    function test_dayWithNetGainBurnsNothing() public {
        _seedPool(10_000 * UNIT, 0);
        vm.startPrank(admin);
        wi.approve(address(staking), 1_000 ether);
        staking.stake(1_000 ether);
        vm.stopPrank();
        _fund(house, 2_000 * UNIT);
        vm.startPrank(house);
        pool.fundHouse(D, 1_000 * UNIT);
        pool.returnFromHouse(D, 1_100 * UNIT);
        vm.stopPrank();
        vm.warp(uint256(D + 1) * 1 days);
        assertEq(pool.closeDay(D), 0);
        assertEq(staking.totalBurned(), 0);
    }

    function test_cannotCloseBeforeDayEndOrWithOpenRisk() public {
        _seedPool(10_000 * UNIT, 0);
        vm.prank(house);
        pool.fundHouse(D, 100 * UNIT);
        vm.warp(uint256(D + 1) * 1 days - 1);
        vm.expectRevert(PoolVault.TooEarly.selector);
        pool.closeDay(D);
        vm.warp(uint256(D + 1) * 1 days);
        vm.expectRevert(PoolVault.DayOpen.selector);
        pool.closeDay(D);
    }
}
