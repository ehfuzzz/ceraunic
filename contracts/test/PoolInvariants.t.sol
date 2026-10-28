// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {StdInvariant} from "forge-std/StdInvariant.sol";
import {ProtocolFixture} from "./ProtocolFixture.sol";
import {PoolHandler} from "./handlers/PoolHandler.sol";

/// @notice M2 (senior hit while junior has capital), M3a (exposure cap), M5 (double settlement,
///         over-payment), I10 (bind identities), pool cash identity with donations.
/// forge-config: default.invariant.depth = 200
contract PoolInvariants is StdInvariant, ProtocolFixture {
    PoolHandler handler;
    uint256 seeded;

    function setUp() public {
        _deploy();
        _seedPool(10_000 * UNIT, 40_000 * UNIT);
        seeded = 50_000 * UNIT;
        vm.startPrank(admin);
        for (uint32 d = D; d < D + 8; ++d) {
            pm.createMarket(IDX_LGA, d, 880, 940, false);
            pm.createMarket(IDX_LGA, d, 650, 700, false);
            pm.createMarket(IDX_BASIS, d, -50, 50, true);
        }
        vm.stopPrank();
        handler = new PoolHandler(usdc, pool, pm, auction, oracle, HOUSE_PK, REPORTER_PK, treasury, IDX_LGA, IDX_BASIS, D);
        targetContract(address(handler));
    }

    function invariant_juniorFirst() public view {
        assertEq(handler.seniorHitWhileJuniorLeft(), 0, "senior absorbed a loss while junior > 0");
        assertEq(handler.juniorHitMismatch(), 0, "junior drop != min(loss, junior)");
    }

    function invariant_exposureCapAlwaysHolds() public view {
        // C1 holds after every step, including losses (a loss is at most its released reserve)
        assertLe((pool.reserved() + pool.deployed()) * 10_000, uint256(pool.capBps()) * pool.capital());
        assertEq(handler.capBrokenAfterVoluntary(), 0, "C1/C2 broken after a voluntary action");
        // every reserved payout is payable from cash
        assertGe(pool.capital() - pool.deployed(), pool.reserved());
    }

    function invariant_cashIdentity() public view {
        assertEq(usdc.balanceOf(address(pool)), pool.capital() - pool.deployed() + handler.donated());
        assertEq(usdc.balanceOf(address(pm)), pm.policyEscrow() + pm.totalCollateral() + pm.totalMargin());
        // nothing leaves the known set of wallets and contracts
        assertEq(handler.knownBalances(), seeded + handler.minted());
        assertEq(handler.lapseMovedCash(), 0, "a withdrawal cancel or lapse moved pool cash");
    }

    function invariant_policiesPaidOnceAndBounded() public view {
        assertEq(handler.doubleSettled(), 0, "policy settled twice");
        assertEq(handler.overPaidPolicy(), 0, "policy paid more than boundUnits * UNIT or wrong amount");
        assertEq(handler.bindIdentityBroken(), 0, "bind split does not add up");
    }
}
