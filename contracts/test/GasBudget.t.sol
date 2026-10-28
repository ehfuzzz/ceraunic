// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {console} from "forge-std/console.sol";
import {ProtocolFixture} from "./ProtocolFixture.sol";
import {Lens} from "../src/Lens.sol";
import {IPolicyManager} from "../src/interfaces/IPolicyManager.sol";
import {IPoolVault} from "../src/interfaces/IPoolVault.sol";
import {IOracleAdapter} from "../src/interfaces/IOracleAdapter.sol";

/// @notice Worst-case gas per non-deploy call (SPEC 15: every call <= 2.0M so forge's x1.3 fits a
///         3M HyperEVM small block; clear <= 1.5M with all 99 ticks populated). The same flow runs
///         for real under a 3,000,000 block gas limit on anvil (make anvil-e2e).
contract GasBudget is ProtocolFixture {
    uint256 constant BUDGET = 2_000_000;
    bytes32 mCall;
    bytes32 mBasis;
    address[10] users;
    uint256 worst;

    function setUp() public {
        _deploy();
        _seedPool(10_000 * UNIT, 40_000 * UNIT);
        vm.startPrank(admin);
        mCall = pm.createMarket(IDX_LGA, D, 880, 940, false);
        mBasis = pm.createMarket(IDX_BASIS, D, -50, 50, true);
        wi.approve(address(staking), 1_000_000 ether);
        staking.stake(1_000_000 ether);
        vm.stopPrank();
        for (uint256 i; i < 10; ++i) {
            users[i] = address(uint160(0x5000 + i));
            _fund(users[i], 1_000_000 * UNIT);
        }
        _fund(house, 1_000_000 * UNIT);
    }

    function _check(string memory what, uint256 used, uint256 budget) internal {
        console.log(what, used);
        assertLe(used, budget, what);
        if (used > worst) worst = used;
    }

    uint256 p1;
    uint256 hOrder;

    function test_worstCaseGasPerCall() public {
        _sell();
        _clearBindClaim();
        _oracleSettle();
        _lpAndVoid();
        console.log("worst non-deploy call", worst);
    }

    function _sell() internal {
        uint256 g;
        // policies (quote + reserve), then the house residual leg as the first order at its tick
        IPolicyManager.Quote memory q = _quote(mCall, users[0], true, 6, 2_500_000, 18_000, 1);
        bytes memory sig = _signQuote(q, HOUSE_PK);
        vm.prank(users[0]);
        g = gasleft();
        p1 = pm.buyPolicy(q, sig);
        _check("buyPolicy", g - gasleft(), BUDGET);
        vm.prank(house);
        hOrder = auction.placeOrder(mBasis, true, 68, 6);

        // 199 more (public) orders: every tick 1..99 has a bid and an offer -> the longest clear scan.
        // Each clears the 1 USDC minimum escrow; no user places more than 20 (per-address cap).
        uint256 maxPlace;
        for (uint256 t = 1; t <= 99; ++t) {
            vm.prank(users[t % 10]);
            g = gasleft();
            auction.placeOrder(mBasis, true, uint8(t), uint128((99 + t) / t + t % 3));
            uint256 u = g - gasleft();
            if (u > maxPlace) maxPlace = u;
            if (t == 99) break;
            vm.prank(users[(t + 3) % 10]);
            auction.placeOrder(mBasis, false, uint8(t), uint128((199 - t) / (100 - t) + (t * 7) % 4));
        }
        vm.prank(users[0]);
        auction.placeOrder(mBasis, false, 99, 100);
        vm.prank(users[2]);
        auction.placeOrder(mBasis, true, 50, 2);
        _check("placeOrder (max of 100)", maxPlace, BUDGET);
        assertEq(auction.getBook(mBasis).orderCount, 200);

        // RFQ on the same market before cutoff
        vm.prank(house);
        pm.depositMargin(1_000 * UNIT);
        IPolicyManager.RfqQuote memory rq =
            IPolicyManager.RfqQuote(keccak256("r"), mBasis, house, users[5], true, 55, 10, uint64(block.timestamp + 1 hours), 1);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(HOUSE_PK, pm.rfqDigest(rq));
        vm.prank(users[5]);
        g = gasleft();
        pm.acceptRfq(rq, abi.encodePacked(r, s, v), 5);
        _check("acceptRfq", g - gasleft(), BUDGET);

        vm.prank(house);
        g = gasleft();
        pool.fundHouse(D, 1_000 * UNIT);
        _check("fundHouse", g - gasleft(), BUDGET);

    }

    function _clearBindClaim() internal {
        uint256 g;
        vm.warp(auction.getBook(mBasis).cutoff);
        g = gasleft();
        auction.clear(mBasis);
        _check("clear (200 orders, 99 ticks both sides)", g - gasleft(), 1_500_000);

        vm.prank(house);
        g = gasleft();
        pm.bind(p1, hOrder);
        _check("bind (with residual order)", g - gasleft(), BUDGET);

        uint256 maxClaim;
        for (uint256 id = 1; id <= 200; ++id) {
            g = gasleft();
            auction.claim(id);
            uint256 u = g - gasleft();
            if (u > maxClaim) maxClaim = u;
        }
        _check("claim (max of 200)", maxClaim, BUDGET);

    }

    function _oracleSettle() internal {
        uint256 g;
        vm.warp(oracle.fetchAt(IDX_LGA, D));
        uint64 asOf = uint64(block.timestamp);
        bytes memory rs = _signReport(IDX_LGA, D, 910, 0, asOf, REPORTER_PK);
        g = gasleft();
        oracle.post(IDX_LGA, D, 910, 0, asOf, bytes32(uint256(1)), rs);
        _check("post", g - gasleft(), BUDGET);
        _post(IDX_BASIS, D, 30, 0);
        vm.prank(house);
        g = gasleft();
        pool.returnFromHouse(D, 900 * UNIT);
        _check("returnFromHouse", g - gasleft(), BUDGET);
        vm.warp(oracle.finalizeAt(IDX_LGA, D));
        g = gasleft();
        oracle.finalize(IDX_LGA, D);
        _check("finalize", g - gasleft(), BUDGET);
        oracle.finalize(IDX_BASIS, D);

        g = gasleft();
        pm.settlePolicy(p1);
        _check("settlePolicy", g - gasleft(), BUDGET);
        uint256 maxPos;
        for (uint256 i; i < 6; ++i) {
            if (pm.positionOf(mBasis, users[i]).longQty + pm.positionOf(mBasis, users[i]).shortQty == 0) continue;
            vm.prank(users[i]);
            g = gasleft();
            pm.claimPosition(mBasis);
            uint256 u = g - gasleft();
            if (u > maxPos) maxPos = u;
        }
        _check("claimPosition (max)", maxPos, BUDGET);

        g = gasleft();
        pool.closeDay(D);
        _check("closeDay (with WI haircut)", g - gasleft(), BUDGET);

    }

    function _lpAndVoid() internal {
        uint256 g;
        vm.prank(admin);
        g = gasleft();
        uint256 rid = pool.requestWithdraw(IPoolVault.Tranche.Senior, 1e15);
        _check("requestWithdraw", g - gasleft(), BUDGET);
        vm.warp(block.timestamp + pool.withdrawDelay());
        g = gasleft();
        pool.claimWithdraw(rid);
        _check("claimWithdraw", g - gasleft(), BUDGET);
        vm.warp(uint256(oracle.finalizeAt(IDX_LGA, D + 5)) + 72 hours);
        g = gasleft();
        oracle.voidDay(IDX_LGA, D + 5);
        _check("voidDay", g - gasleft(), BUDGET);
        uint32 wd = uint32(block.timestamp / 1 days);
        vm.prank(house);
        pool.fundHouse(wd, 100 * UNIT);
        vm.warp(uint256(wd) * 1 days + pool.houseReturnWindow());
        g = gasleft();
        pool.writeOffHouse(wd);
        _check("writeOffHouse", g - gasleft(), BUDGET);

        // the Lens is an eth_call, but keep it inside the same budget for a heavy user
        Lens lens = new Lens(usdc, pool, pm, auction, IOracleAdapter(address(oracle)), staking);
        g = gasleft();
        lens.userView(users[3]);
        _check("Lens.userView (eth_call, ~34 orders)", g - gasleft(), BUDGET);
    }
}
