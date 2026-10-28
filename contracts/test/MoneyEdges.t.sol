// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ProtocolFixture} from "./ProtocolFixture.sol";
import {PolicyManager} from "../src/PolicyManager.sol";
import {BatchAuction} from "../src/BatchAuction.sol";
import {PoolVault} from "../src/PoolVault.sol";
import {IPolicyManager} from "../src/interfaces/IPolicyManager.sol";
import {IPoolVault} from "../src/interfaces/IPoolVault.sol";

/// @notice Directed cases for money failures the invariant handlers do not reach by chance.
contract MoneyEdges is ProtocolFixture {
    bytes32 mCall;
    bytes32 mBasis;
    address alice = address(0xA11);
    address bob = address(0xB0B0);

    function setUp() public {
        _deploy();
        _seedPool(10_000 * UNIT, 40_000 * UNIT);
        vm.startPrank(admin);
        mCall = pm.createMarket(IDX_LGA, D, 880, 940, false);
        mBasis = pm.createMarket(IDX_BASIS, D, -50, 50, true);
        vm.stopPrank();
        _fund(alice, 10_000 * UNIT);
        _fund(bob, 10_000 * UNIT);
        _fund(house, 10_000 * UNIT);
    }

    /// A fill claimed after its trader already claimed the position must still be paid, not stranded.
    function test_lateOrderClaimAfterPositionClaimIsPaid() public {
        vm.prank(alice);
        uint256 o1 = auction.placeOrder(mBasis, true, 60, 5);
        vm.prank(alice);
        uint256 o2 = auction.placeOrder(mBasis, true, 70, 5);
        vm.prank(bob);
        uint256 o3 = auction.placeOrder(mBasis, false, 40, 10);
        vm.warp(auction.getBook(mBasis).cutoff);
        auction.clear(mBasis);
        auction.claim(o1);
        auction.claim(o3);
        _finalizeValue(IDX_BASIS, D, 30); // L = 800,000
        vm.prank(alice);
        uint256 first = pm.claimPosition(mBasis);
        assertEq(first, 5 * 800_000);
        uint256 before = usdc.balanceOf(alice);
        auction.claim(o2); // late: fill 5 is paid out immediately
        uint256 cost = 5 * uint256(auction.getBook(mBasis).pStar) * TICK;
        assertEq(usdc.balanceOf(alice) - before, (5 * 70 * TICK - cost) + 5 * 800_000, "late fill stranded");
        vm.prank(bob);
        pm.claimPosition(mBasis);
        assertEq(pm.marketCollateral(mBasis), 0, "collateral must be fully paid out");
        assertEq(usdc.balanceOf(address(auction)), 0);
    }

    /// Donations never move share prices (ledgers ignore balanceOf).
    function test_donationDoesNotMoveSharePrice() public {
        vm.prank(house);
        pool.depositJunior(5_000 * UNIT); // room under C2 for new senior money
        vm.prank(alice);
        pool.depositSenior(1);
        usdc.mint(address(pool), 1_000_000 * UNIT); // donation / inflation attempt
        vm.prank(bob);
        uint256 shares = pool.depositSenior(1_000 * UNIT);
        vm.prank(bob);
        uint256 rid = pool.requestWithdraw(IPoolVault.Tranche.Senior, shares);
        vm.warp(block.timestamp + pool.withdrawDelay());
        pool.claimWithdraw(rid);
        assertGe(usdc.balanceOf(bob), 10_000 * UNIT - 1, "depositor lost value to a donation");
    }

    /// A loss during the withdrawal delay hits the leaver; a claim that would break C1 reverts.
    function test_withdrawalPaysClaimTimeNavAndRespectsCap() public {
        uint256 half = pool.senior().balanceOf(admin) / 2;
        vm.prank(admin);
        uint256 rid = pool.requestWithdraw(IPoolVault.Tranche.Senior, half);
        uint256 navAtRequest = 20_000 * UNIT;
        // a loss larger than junior hits senior before the claim
        vm.prank(house);
        pool.fundHouse(D, 15_000 * UNIT);
        vm.prank(house);
        pool.returnFromHouse(D, 0); // -15,000: junior 10,000 -> 0, senior -5,000
        vm.warp(block.timestamp + pool.withdrawDelay());
        uint256 before = usdc.balanceOf(admin);
        pool.claimWithdraw(rid);
        assertLt(usdc.balanceOf(admin) - before, navAtRequest, "leaver escaped the loss");
        // C1: a claim that would leave reserved + deployed above capBps * capital reverts
        uint256 rest = pool.senior().balanceOf(admin);
        vm.prank(admin);
        uint256 rid2 = pool.requestWithdraw(IPoolVault.Tranche.Senior, rest); // 17,500 USDC of NAV
        vm.prank(house);
        pool.depositJunior(10_000 * UNIT); // capital 27,500
        vm.prank(house);
        pool.fundHouse(uint32(block.timestamp / 1 days), 10_000 * UNIT); // cash 17,500 covers the claim, but C1 would break
        vm.warp(block.timestamp + pool.withdrawDelay());
        vm.expectRevert(PoolVault.ExposureCap.selector);
        pool.claimWithdraw(rid2);
    }

    /// Signed quotes cannot be replayed, redirected, forged, used late or overpriced past max payout.
    function test_quoteAbuseReverts() public {
        IPolicyManager.Quote memory q = _quote(mCall, alice, true, 6, 2_500_000, 18_000, 7);
        bytes memory sig = _signQuote(q, HOUSE_PK);
        bytes memory forged = _signQuote(q, ADMIN_PK);
        vm.prank(bob);
        vm.expectRevert(PolicyManager.NotBuyer.selector);
        pm.buyPolicy(q, sig);
        vm.prank(alice);
        vm.expectRevert(PolicyManager.BadSigner.selector);
        pm.buyPolicy(q, forged);
        vm.prank(alice);
        pm.buyPolicy(q, sig);
        vm.prank(alice);
        vm.expectRevert(PolicyManager.NonceUsed.selector);
        pm.buyPolicy(q, sig);
        IPolicyManager.Quote memory over = _quote(mCall, alice, true, 1, uint128(UNIT + 1), 0, 8);
        bytes memory sigOver = _signQuote(over, HOUSE_PK);
        vm.prank(alice);
        vm.expectRevert(PolicyManager.BadQuote.selector);
        pm.buyPolicy(over, sigOver);
        IPolicyManager.Quote memory late = _quote(mCall, alice, true, 1, 100_000, 0, 9);
        late.expiry = uint64(pm.getMarket(mCall).saleCutoff + 1 hours);
        bytes memory sigLate = _signQuote(late, HOUSE_PK);
        vm.warp(pm.getMarket(mCall).saleCutoff);
        vm.prank(alice);
        vm.expectRevert(PolicyManager.SalesClosed.selector);
        pm.buyPolicy(late, sigLate);
        uint256 snap = vm.snapshotState();
        vm.warp(T0);
        vm.chainId(998);
        vm.prank(alice);
        vm.expectRevert(PolicyManager.BadSigner.selector);
        pm.buyPolicy(late, sigLate);
        vm.revertToState(snap);
    }

    /// One house order binds at most one policy, only from the house, only same-day, only before bindBy.
    function test_bindAbuseReverts() public {
        uint256 p1 = _buy(mCall, alice, true, 6, 2_500_000, 18_000, 1);
        uint256 p2 = _buy(mCall, bob, true, 6, 2_500_000, 18_000, 2);
        vm.prank(house);
        uint256 hOrder = auction.placeOrder(mBasis, true, 68, 6);
        vm.prank(alice);
        uint256 aOrder = auction.placeOrder(mBasis, true, 72, 3);
        vm.prank(bob);
        auction.placeOrder(mBasis, false, 60, 4);
        vm.prank(bob);
        auction.placeOrder(mBasis, false, 66, 3);
        // the house is closed at houseCutoff; the public is not
        vm.warp(pm.getMarket(mCall).houseCutoff);
        vm.prank(house);
        vm.expectRevert(BatchAuction.HouseClosed.selector);
        auction.placeOrder(mBasis, true, 50, 1);
        vm.warp(auction.getBook(mBasis).cutoff);
        vm.prank(alice);
        vm.expectRevert(BatchAuction.BookClosed.selector);
        auction.placeOrder(mBasis, true, 50, 1);
        auction.clear(mBasis);
        vm.prank(alice);
        vm.expectRevert(PolicyManager.OnlyHouse.selector);
        pm.bind(p1, hOrder);
        vm.prank(house);
        vm.expectRevert(PolicyManager.NotHouseOrder.selector);
        pm.bind(p1, aOrder);
        uint256 aliceBefore = usdc.balanceOf(alice);
        vm.prank(house);
        uint128 bound = pm.bind(p1, hOrder); // SPEC 5 worked shape: house fill 4 of 6
        assertEq(bound, 4);
        assertEq(usdc.balanceOf(alice) - aliceBefore, uint256(2_500_000) - uint256(2_500_000) * 4 / 6, "refund for cut units");
        vm.prank(house);
        vm.expectRevert(PolicyManager.OrderUsed.selector);
        pm.bind(p2, hOrder);
        vm.warp(pm.getMarket(mCall).bindBy);
        vm.prank(house);
        vm.expectRevert(PolicyManager.BindWindowClosed.selector);
        pm.bind(p2, 99);
        vm.prank(address(0xDEAD));
        assertEq(pm.bind(p2, 0), 6, "after bindBy anyone binds at full units");
    }

    function test_bindRejectsOrderFromAnotherDay() public {
        vm.prank(admin);
        bytes32 mBasis2 = pm.createMarket(IDX_BASIS, D + 1, -50, 50, true);
        uint256 p1 = _buy(mCall, alice, true, 6, 2_500_000, 18_000, 1);
        vm.prank(house);
        uint256 o = auction.placeOrder(mBasis2, true, 68, 6);
        vm.warp(auction.getBook(mBasis2).cutoff);
        auction.clear(mBasis2);
        // day D's bindBy has passed by now, so use a fresh D+1 policy vs a day-D order instead
        assertTrue(block.timestamp >= pm.getMarket(mCall).bindBy);
        vm.warp(T0);
        vm.prank(house);
        uint256 oD = auction.placeOrder(mBasis, true, 68, 6);
        vm.warp(auction.getBook(mBasis).cutoff);
        auction.clear(mBasis);
        vm.prank(house);
        vm.expectRevert(PolicyManager.WrongDay.selector);
        pm.bind(p1, o);
        vm.prank(house);
        pm.bind(p1, oD);
    }

    function test_bookFullAt200PublicOrders() public {
        for (uint160 k; k < 10; ++k) {
            address w = address(0x6000 + k);
            _fund(w, 1_000 * UNIT);
            vm.startPrank(w);
            for (uint256 i; i < 20; ++i) auction.placeOrder(mBasis, i % 2 == 0, 50, 2); // 1 USDC escrow each
            if (k == 0) {
                vm.expectRevert(BatchAuction.TraderOrderCap.selector);
                auction.placeOrder(mBasis, true, 50, 2);
            }
            vm.stopPrank();
        }
        vm.prank(alice);
        vm.expectRevert(BatchAuction.BookFull.selector);
        auction.placeOrder(mBasis, true, 50, 2);
        vm.prank(house); // the house never competes for public slots
        auction.placeOrder(mBasis, true, 50, 1);
        assertEq(auction.getBook(mBasis).orderCount, 201);
    }

    /// RFQ: the maker's margin must cover its side; a quote cannot fill past maxQty; floors cancel.
    function test_rfqCollateralAndCancel() public {
        IPolicyManager.RfqQuote memory q = IPolicyManager.RfqQuote(
            keccak256("r"), mBasis, house, alice, true, 55, 10, uint64(block.timestamp + 1 hours), 1
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(HOUSE_PK, pm.rfqDigest(q));
        bytes memory sig = abi.encodePacked(r, s, v);
        vm.prank(alice);
        vm.expectRevert(PolicyManager.InsufficientMargin.selector);
        pm.acceptRfq(q, sig, 5);
        vm.prank(house);
        pm.depositMargin(10 * 45 * TICK);
        vm.prank(alice);
        pm.acceptRfq(q, sig, 6);
        vm.prank(alice);
        vm.expectRevert(PolicyManager.AboveMaxQty.selector);
        pm.acceptRfq(q, sig, 5);
        assertEq(pm.marketCollateral(mBasis), 6 * UNIT, "collateral == qty * UNIT");
        vm.prank(house);
        pm.bumpNonceFloor(2);
        vm.prank(alice);
        vm.expectRevert(PolicyManager.NonceBelowFloor.selector);
        pm.acceptRfq(q, sig, 1);
    }

    /// Pause stops new risk only: settlement, claims and withdrawals still work.
    function test_pauseNeverTrapsFunds() public {
        uint256 p1 = _buy(mCall, alice, true, 6, 2_500_000, 18_000, 1);
        vm.prank(house);
        pm.bind(p1, 0);
        vm.prank(alice);
        uint256 o = auction.placeOrder(mBasis, true, 60, 2);
        vm.prank(admin);
        uint256 rid = pool.requestWithdraw(IPoolVault.Tranche.Senior, 1e12);
        vm.startPrank(admin);
        pm.pause();
        auction.pause();
        pool.pause();
        vm.stopPrank();
        vm.prank(alice);
        vm.expectRevert();
        auction.placeOrder(mBasis, true, 60, 1);
        vm.warp(auction.getBook(mBasis).cutoff);
        auction.clear(mBasis);
        auction.claim(o);
        _finalizeValue(IDX_LGA, D, 910);
        assertEq(pm.settlePolicy(p1), 3_000_000);
        vm.warp(block.timestamp + pool.withdrawDelay());
        pool.claimWithdraw(rid);
    }

    /// Strips: a day priced above the cap or off-template is refused; one purchase per day.
    function test_stripLimits() public {
        vm.prank(alice);
        uint256 sid = pm.openStrip(IDX_LGA, 880, 940, true, 6, 2_000_000, D, D + 5);
        IPolicyManager.Quote memory q = _quote(mCall, alice, true, 6, 2_000_001, 10_000, 1);
        bytes memory sig = _signQuote(q, HOUSE_PK);
        vm.prank(house);
        vm.expectRevert(PolicyManager.StripMismatch.selector);
        pm.buyStripDay(sid, q, sig);
        q.premium = 2_000_000;
        sig = _signQuote(q, HOUSE_PK);
        vm.prank(house);
        pm.buyStripDay(sid, q, sig);
        IPolicyManager.Quote memory q2 = _quote(mCall, alice, true, 6, 1_000_000, 10_000, 2);
        bytes memory sig2 = _signQuote(q2, HOUSE_PK);
        vm.prank(house);
        vm.expectRevert(PolicyManager.StripDayDone.selector);
        pm.buyStripDay(sid, q2, sig2);
    }
}
