// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ProtocolFixture} from "./ProtocolFixture.sol";
import {MockUSDC} from "../src/MockUSDC.sol";
import {WIToken} from "../src/WIToken.sol";
import {PoolVault} from "../src/PoolVault.sol";
import {WIStaking} from "../src/WIStaking.sol";
import {PolicyManager} from "../src/PolicyManager.sol";
import {BatchAuction} from "../src/BatchAuction.sol";
import {IPolicyManager} from "../src/interfaces/IPolicyManager.sol";
import {IPoolVault} from "../src/interfaces/IPoolVault.sol";

/// @notice 08-HARDEN: money failures found in the 08-AUDIT code review, one test per failure.
contract Hardening is ProtocolFixture {
    address alice = address(0xA11);
    address bob = address(0xB0B0);
    address stranger = address(0x5717);

    function setUp() public {
        _deploy();
        _seedPool(10_000 * UNIT, 40_000 * UNIT);
        _fund(alice, 10_000 * UNIT);
        _fund(bob, 10_000 * UNIT);
        _fund(house, 10_000 * UNIT);
    }

    /// #1 Squatting: a stranger who creates tomorrow's basis market as non-auctioned first stops the
    /// house from opening its auction book, so no residual leg can be placed and no policy downsized.
    function test_marketCreation_houseOnlyBeforeCutoff() public {
        vm.prank(stranger);
        try pm.createMarket(IDX_BASIS, D, -50, 50, false) {} catch {}
        vm.prank(house);
        bytes32 m = pm.createMarket(IDX_BASIS, D, -50, 50, true);
        vm.prank(house);
        auction.placeOrder(m, true, 68, 6); // the residual leg goes in
        // once the house cutoff has passed (the house cannot trade the day any more) anyone may create
        vm.warp(pm.getMarket(m).houseCutoff);
        vm.prank(stranger);
        pm.createMarket(IDX_LGA, D, 880, 940, false);
    }

    /// A withdrawal delay or unstake cooldown shorter than houseReturnWindow + 2 d lets a leaver exit
    /// before an unreturned house day is written off, so the loss and the haircut miss them.
    function test_windows_delayAndCooldownMustOutlastHouseReturnWindow() public {
        vm.expectRevert(PoolVault.BadWindows.selector);
        this.newVault(12 days - 1, 10 days);

        PoolVault v = PoolVault(this.newVault(12 days, 10 days));
        WIStaking shortCooldown = new WIStaking(address(new WIToken(address(this), 1e24)), address(this), 11 days);
        vm.expectRevert(PoolVault.BadWindows.selector);
        v.setStaking(address(shortCooldown));

        vm.startPrank(admin);
        vm.expectRevert(PoolVault.BadWindows.selector);
        pool.setWindows(12 days, 10 days + 1);
        vm.expectRevert(WIStaking.BadWindows.selector);
        staking.setUnstakeCooldown(12 days - 1);
        vm.stopPrank();
    }

    /// #2 Order-cap exhaustion: fully refunded cheap orders from one wallet filled all 200 slots of a
    /// book, locking out every other trader and the house's residual legs (policies then bind unhedged).
    function test_orderCap_cheapSpamCannotLockOutTradersOrHouse() public {
        vm.prank(admin);
        bytes32 m = pm.createMarket(IDX_BASIS, D, -50, 50, true);
        _fund(stranger, 10_000 * UNIT);
        vm.startPrank(stranger);
        for (uint256 i; i < 200; ++i) {
            try auction.placeOrder(m, true, 1, 1) {} catch {} // 0.01 USDC escrow, refunded in full
            try auction.placeOrder(m, true, 1, 100) {} catch {} // 1 USDC escrow, refunded in full
        }
        vm.stopPrank();
        vm.prank(alice);
        auction.placeOrder(m, true, 60, 5); // an honest trader still gets in
        // many wallets can still fill every public slot; the house keeps room for its legs
        for (uint160 k; k < 12; ++k) {
            address w = address(0x5000 + k);
            _fund(w, 100 * UNIT);
            vm.startPrank(w);
            for (uint256 j; j < 25; ++j) {
                try auction.placeOrder(m, false, 99, 100) {} catch {}
            }
            vm.stopPrank();
        }
        vm.prank(house);
        auction.placeOrder(m, true, 68, 6);
    }

    /// #3 qStar was stored as uint128 unchecked. With open MockUSDC minting, orders whose crossing volume
    /// is exactly 2^128 store qStar = 0: every order then refunds in full although 2^128 x UNIT already
    /// moved to the PolicyManager, so the last claimers find the auction empty. Here the attacker claims
    /// first and an honest trader's escrow is stranded.
    function test_auctionClear_oversizedOrdersCannotStrandEscrow() public {
        vm.prank(admin);
        bytes32 m = pm.createMarket(IDX_BASIS, D, -50, 50, true);
        uint256 aliceStart = usdc.balanceOf(alice);
        vm.prank(alice);
        uint256 aliceOrder = auction.placeOrder(m, false, 30, 2); // honest offer, 1.4 USDC escrow
        uint128 h = uint128(1) << 127;
        usdc.mint(stranger, 1e60);
        vm.startPrank(stranger);
        usdc.approve(address(auction), type(uint256).max);
        uint256[4] memory ids;
        try auction.placeOrder(m, true, 70, h) returns (uint256 id) { ids[0] = id; } catch {}
        try auction.placeOrder(m, true, 71, h) returns (uint256 id) { ids[1] = id; } catch {}
        try auction.placeOrder(m, false, 40, h) returns (uint256 id) { ids[2] = id; } catch {}
        try auction.placeOrder(m, false, 41, h - 1) returns (uint256 id) { ids[3] = id; } catch {}
        vm.stopPrank();
        vm.warp(auction.getBook(m).cutoff);
        auction.clear(m);
        if (ids[2] != 0) try auction.claim(ids[2]) {} catch {} // attacker claims first
        auction.claim(aliceOrder);
        assertEq(usdc.balanceOf(alice), aliceStart, "honest trader lost escrow");
        for (uint256 i; i < 4; ++i) {
            if (ids[i] != 0 && !auction.getOrder(ids[i]).claimed) auction.claim(ids[i]);
        }
        assertEq(usdc.balanceOf(address(auction)), 0, "escrow stranded in the auction");
    }

    /// #4 After a void, anyone could still bind an unbound policy (after bindBy), which turned the buyer's
    /// full refund into keptPremium - keptFee: the buyer lost the fee on a day with no settlement.
    function test_bind_revertsOnVoidDay_unboundBuyerGetsFullPremium() public {
        vm.prank(admin);
        bytes32 mCall = pm.createMarket(IDX_LGA, D, 880, 940, false);
        uint256 start = usdc.balanceOf(alice);
        uint256 p = _buy(mCall, alice, true, 6, 2_500_000, 18_000, 1);
        vm.warp(oracle.finalizeAt(IDX_LGA, D) + 72 hours); // no report ever came: the day is void
        oracle.voidDay(IDX_LGA, D);
        vm.prank(stranger);
        try pm.bind(p, 0) {} catch {}
        pm.settlePolicy(p);
        assertEq(usdc.balanceOf(alice), start, "unbound buyer must get the full premium back");
        assertEq(pm.policyEscrow(), 0);
    }

    /// #5 fundHouse took any day. Money booked on a far-future day cannot be written off until that day +
    /// houseReturnWindow, so a lost deployment stayed out of NAV for years and leavers exited at full NAV.
    function test_fundHouse_dayWithinTodayMinus1ToPlus2() public {
        uint32 today = uint32(block.timestamp / 1 days);
        vm.startPrank(house);
        try pool.fundHouse(today + 400, 1_000 * UNIT) {} catch {}
        vm.stopPrank();
        vm.warp(block.timestamp + pool.houseReturnWindow() + 3 days);
        if (pool.deployed() != 0) pool.writeOffHouse(today + 400);
        assertEq(pool.deployed(), 0, "a house deployment escaped write-off");

        // the edges: today - 1 and today + 2 are accepted, today - 2 and today + 3 are not
        today = uint32(block.timestamp / 1 days);
        vm.startPrank(house);
        pool.fundHouse(today - 1, 1 * UNIT);
        pool.fundHouse(today + 2, 1 * UNIT);
        vm.expectRevert(PoolVault.BadDay.selector);
        pool.fundHouse(today - 2, 1 * UNIT);
        vm.expectRevert(PoolVault.BadDay.selector);
        pool.fundHouse(today + 3, 1 * UNIT);
        vm.stopPrank();
    }

    /// #6 A matured withdrawal request stayed claimable forever: an LP could request once, wait, and leave
    /// at full NAV the moment a loss became visible but before it was booked. Claims now close 3 days
    /// after maturity.
    function test_withdrawClaim_closesThreeDaysAfterMaturity() public {
        uint256 shares = pool.senior().balanceOf(admin) / 10;
        vm.prank(admin);
        uint256 rid = pool.requestWithdraw(IPoolVault.Tranche.Senior, shares);
        uint64 at = pool.getWithdrawRequest(rid).claimableAt;
        vm.warp(uint256(at) + 3 days); // window over; a loss is now visible but not yet booked
        vm.expectRevert(PoolVault.ClaimWindowClosed.selector);
        pool.claimWithdraw(rid);
    }

    /// A lapsed request hands its shares back: the tranche keeps the money, nothing leaves the pool, and
    /// the request can be neither claimed nor lapsed again.
    function test_withdrawLapse_returnsSharesToTrancheAndNothingLeavesPool() public {
        uint256 sShares = pool.senior().balanceOf(admin) / 10;
        uint256 jShares = pool.juniorSharesOf(admin) / 10;
        vm.startPrank(admin);
        uint256 rs = pool.requestWithdraw(IPoolVault.Tranche.Senior, sShares);
        uint256 rj = pool.requestWithdraw(IPoolVault.Tranche.Junior, jShares);
        vm.stopPrank();
        (uint256 sBal, uint256 jBal) = (pool.senior().balanceOf(admin), pool.juniorSharesOf(admin));
        (uint256 cash0, uint256 held0) = (pool.cash(), usdc.balanceOf(address(pool)));
        (uint256 sa0, uint256 ja0, uint256 ss0, uint256 js0) =
            (pool.seniorAssets(), pool.juniorAssets(), pool.senior().totalSupply(), pool.totalJuniorShares());
        uint256 endAt = uint256(pool.getWithdrawRequest(rs).claimableAt) + pool.CLAIM_WINDOW();
        vm.warp(endAt - 1);
        vm.expectRevert(PoolVault.NotLapsed.selector);
        pool.lapseWithdraw(rs);
        vm.warp(endAt);
        vm.startPrank(stranger); // anyone may lapse; the shares go to the owner
        pool.lapseWithdraw(rs);
        pool.lapseWithdraw(rj);
        vm.stopPrank();
        assertEq(pool.senior().balanceOf(admin), sBal + sShares, "senior shares not returned");
        assertEq(pool.juniorSharesOf(admin), jBal + jShares, "junior shares not returned");
        assertEq(pool.senior().balanceOf(address(pool)), 0, "shares left in escrow");
        assertEq(pool.cash(), cash0);
        assertEq(usdc.balanceOf(address(pool)), held0, "USDC left the pool on a lapse");
        assertEq(pool.seniorAssets(), sa0);
        assertEq(pool.juniorAssets(), ja0);
        assertEq(pool.senior().totalSupply(), ss0);
        assertEq(pool.totalJuniorShares(), js0);
        vm.expectRevert(PoolVault.AlreadyClaimed.selector);
        pool.claimWithdraw(rs);
        vm.expectRevert(PoolVault.AlreadyClaimed.selector);
        pool.lapseWithdraw(rj);
    }

    /// The last second of the window still pays, at claim-time NAV, to the owner.
    function test_withdrawClaim_insideWindowPays() public {
        uint256 shares = pool.senior().balanceOf(admin) / 10;
        vm.prank(admin);
        uint256 rid = pool.requestWithdraw(IPoolVault.Tranche.Senior, shares);
        vm.warp(uint256(pool.getWithdrawRequest(rid).claimableAt) + pool.CLAIM_WINDOW() - 1);
        uint256 expected = shares * (pool.seniorAssets() + 1) / (pool.senior().totalSupply() + 1e6);
        uint256 before = usdc.balanceOf(admin);
        vm.prank(stranger);
        uint256 paid = pool.claimWithdraw(rid);
        assertEq(paid, expected);
        assertEq(usdc.balanceOf(admin) - before, expected, "owner not paid");
        assertEq(pool.senior().balanceOf(address(pool)), 0, "escrowed shares not burned");
    }

    /// Before maturity only the owner can cancel, and the shares come back; from maturity on, no cancel.
    function test_withdrawCancel_beforeMaturityRestoresShares() public {
        uint256 shares = pool.senior().balanceOf(admin) / 10;
        uint256 bal0 = pool.senior().balanceOf(admin);
        vm.startPrank(admin);
        uint256 r1 = pool.requestWithdraw(IPoolVault.Tranche.Senior, shares);
        uint256 r2 = pool.requestWithdraw(IPoolVault.Tranche.Senior, shares);
        vm.stopPrank();
        uint256 at = pool.getWithdrawRequest(r1).claimableAt;
        vm.warp(at - 1);
        vm.prank(stranger);
        vm.expectRevert(PoolVault.NotRequestOwner.selector);
        pool.cancelWithdraw(r1);
        uint256 cash0 = pool.cash();
        vm.prank(admin);
        pool.cancelWithdraw(r1);
        assertEq(pool.senior().balanceOf(admin), bal0 - shares, "cancelled shares not restored");
        assertEq(pool.cash(), cash0);
        vm.warp(at);
        vm.expectRevert(PoolVault.AlreadyClaimed.selector); // a cancelled request never pays
        pool.claimWithdraw(r1);
        vm.prank(admin);
        vm.expectRevert(PoolVault.NotCancellable.selector);
        pool.cancelWithdraw(r2);
    }

    /// @dev External so vm.expectRevert sees the constructor revert as one call.
    function newVault(uint64 withdrawDelay_, uint64 houseReturnWindow_) external returns (address) {
        return address(new PoolVault(IERC20(address(new MockUSDC())), address(this), withdrawDelay_, houseReturnWindow_));
    }
}
