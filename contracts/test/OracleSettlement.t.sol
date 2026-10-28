// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ProtocolFixture} from "./ProtocolFixture.sol";
import {OracleAdapter} from "../src/OracleAdapter.sol";
import {PolicyManager} from "../src/PolicyManager.sol";
import {IOracleAdapter} from "../src/interfaces/IOracleAdapter.sol";

/// @notice M4: settlement on a stale, unsigned, tampered, replayed, foreign or unfinal value.
///         M5: double settlement. Each case asserts the specific revert.
contract OracleSettlement is ProtocolFixture {
    bytes32 mCall;
    uint256 policyId;
    address buyer = address(0xB1);

    function setUp() public {
        _deploy();
        _seedPool(10_000 * UNIT, 40_000 * UNIT);
        vm.prank(admin);
        mCall = pm.createMarket(IDX_LGA, D, 880, 940, false);
        _fund(buyer, 100 * UNIT);
        policyId = _buy(mCall, buyer, true, 6, 2_500_000, 18_000, 1);
        vm.prank(house);
        pm.bind(policyId, 0);
        vm.warp(oracle.fetchAt(IDX_LGA, D));
    }

    function testFuzz_rejectsReportsNotSignedByAReporter(uint256 pk) public {
        pk = bound(pk, 1, 1e70);
        vm.assume(pk != REPORTER_PK);
        uint64 asOf = uint64(block.timestamp);
        bytes memory sig = _signReport(IDX_LGA, D, 910, 0, asOf, pk);
        vm.expectRevert(OracleAdapter.BadSigner.selector);
        oracle.post(IDX_LGA, D, 910, 0, asOf, bytes32(0), sig);
    }

    function testFuzz_rejectsTamperedValue(int64 forged) public {
        vm.assume(forged != 910);
        uint64 asOf = uint64(block.timestamp);
        bytes memory sig = _signReport(IDX_LGA, D, 910, 0, asOf, REPORTER_PK);
        vm.expectRevert(OracleAdapter.BadSigner.selector);
        oracle.post(IDX_LGA, D, forged, 0, asOf, bytes32(0), sig);
    }

    function test_rejectsTamperedRevisionAsOfDayOrIndex() public {
        vm.warp(block.timestamp + 1 hours);
        uint64 asOf = uint64(block.timestamp - 10);
        bytes memory sig = _signReport(IDX_LGA, D, 910, 1, asOf, REPORTER_PK);
        vm.expectRevert(OracleAdapter.BadSigner.selector);
        oracle.post(IDX_LGA, D, 910, 2, asOf, bytes32(0), sig);
        vm.expectRevert(OracleAdapter.BadSigner.selector);
        oracle.post(IDX_LGA, D, 910, 1, asOf + 1, bytes32(0), sig);
        vm.expectRevert(OracleAdapter.BadSigner.selector);
        oracle.post(IDX_BASIS, D, 910, 1, asOf, bytes32(0), sig);
        vm.warp(block.timestamp - 1 hours - 1 days); // day D-1's window: signature is for day D
        vm.expectRevert(OracleAdapter.BadSigner.selector);
        oracle.post(IDX_LGA, D - 1, 910, 1, uint64(block.timestamp), bytes32(0), sig);
    }

    function test_rejectsForeignChainAndForeignDeployment() public {
        uint64 asOf = uint64(block.timestamp);
        bytes memory sig = _signReport(IDX_LGA, D, 910, 0, asOf, REPORTER_PK); // domain chainId 31337
        uint256 snap = vm.snapshotState();
        vm.chainId(998);
        vm.expectRevert(OracleAdapter.BadSigner.selector);
        oracle.post(IDX_LGA, D, 910, 0, asOf, bytes32(0), sig);
        vm.revertToState(snap);
        // same chain, another OracleAdapter deployment with the same reporter
        vm.startPrank(admin);
        OracleAdapter other = new OracleAdapter(admin, 24 hours);
        other.setReporter(reporter, true);
        other.registerIndex(
            IDX_LGA, IOracleAdapter.IndexConfig({fetchLag: 12 hours, disputeWindow: 24 hours, voidGrace: 72 hours, active: true})
        );
        vm.stopPrank();
        vm.expectRevert(OracleAdapter.BadSigner.selector);
        other.post(IDX_LGA, D, 910, 0, asOf, bytes32(0), sig);
    }

    function test_windowAndReplayPredicates() public {
        uint64 fAt = oracle.fetchAt(IDX_LGA, D);
        // P3: a value "as of" before the fetch time (day not over / not published)
        bytes memory sig1 = _signReport(IDX_LGA, D, 910, 0, fAt - 1, REPORTER_PK);
        vm.expectRevert(OracleAdapter.AsOfBeforeFetch.selector);
        oracle.post(IDX_LGA, D, 910, 0, fAt - 1, bytes32(0), sig1);
        // P4: from the future
        bytes memory sig2 = _signReport(IDX_LGA, D, 910, 0, fAt + 1, REPORTER_PK);
        vm.expectRevert(OracleAdapter.AsOfInFuture.selector);
        oracle.post(IDX_LGA, D, 910, 0, fAt + 1, bytes32(0), sig2);
        // accepted revision 0, then replay of the very same signed report
        bytes memory sig0 = _signReport(IDX_LGA, D, 905, 0, fAt, REPORTER_PK);
        oracle.post(IDX_LGA, D, 905, 0, fAt, bytes32(0), sig0);
        vm.expectRevert(OracleAdapter.RevisionNotNewer.selector);
        oracle.post(IDX_LGA, D, 905, 0, fAt, bytes32(0), sig0);
        // P5: stale (asOf older than maxReportAge). With the CLI windows (asOf >= fetchAt, now <
        // fetchAt + 24h) and maxReportAge = 24h, P5 cannot bind; it matters once maxReportAge <
        // disputeWindow, so shorten it here.
        vm.prank(admin);
        oracle.setMaxReportAge(1 hours);
        vm.warp(fAt + 1 hours + 1);
        bytes memory sig3 = _signReport(IDX_LGA, D, 910, 1, fAt, REPORTER_PK);
        vm.expectRevert(OracleAdapter.ReportStale.selector);
        oracle.post(IDX_LGA, D, 910, 1, fAt, bytes32(0), sig3);
        // a correct revision 1 inside the window is accepted
        uint64 asOf1 = uint64(block.timestamp);
        oracle.post(IDX_LGA, D, 910, 1, asOf1, bytes32(0), _signReport(IDX_LGA, D, 910, 1, asOf1, REPORTER_PK));
        // P6: window closed at finalizeAt
        vm.warp(oracle.finalizeAt(IDX_LGA, D));
        uint64 asOf2 = uint64(block.timestamp);
        bytes memory sig4 = _signReport(IDX_LGA, D, 999, 2, asOf2, REPORTER_PK);
        vm.expectRevert(OracleAdapter.WindowClosed.selector);
        oracle.post(IDX_LGA, D, 999, 2, asOf2, bytes32(0), sig4);
        // P1: an inactive index takes no reports
        vm.prank(admin);
        oracle.setIndexActive(IDX_BASIS, false);
        bytes memory sig5 = _signReport(IDX_BASIS, D, 1, 0, asOf2, REPORTER_PK);
        vm.expectRevert(OracleAdapter.IndexNotActive.selector);
        oracle.post(IDX_BASIS, D, 1, 0, asOf2, bytes32(0), sig5);
    }

    function test_settlementReadsOnlyTheFinalValue() public {
        _post(IDX_LGA, D, 905, 0);
        vm.warp(block.timestamp + 1 hours);
        _post(IDX_LGA, D, 910, 1);
        vm.expectRevert(OracleAdapter.NotFinal.selector);
        pm.settlePolicy(policyId);
        vm.expectRevert(OracleAdapter.TooEarly.selector);
        oracle.finalize(IDX_LGA, D);
        vm.warp(oracle.finalizeAt(IDX_LGA, D));
        oracle.finalize(IDX_LGA, D);
        vm.expectRevert(OracleAdapter.AlreadyFinal.selector);
        oracle.finalize(IDX_LGA, D);
        uint64 asOf = uint64(block.timestamp);
        bytes memory sig6 = _signReport(IDX_LGA, D, 999, 2, asOf, REPORTER_PK);
        vm.expectRevert(OracleAdapter.AlreadyFinal.selector);
        oracle.post(IDX_LGA, D, 999, 2, asOf, bytes32(0), sig6);
        assertEq(oracle.getFinal(IDX_LGA, D), 910);
        uint256 before = usdc.balanceOf(buyer);
        uint256 payout = pm.settlePolicy(policyId);
        assertEq(payout, 6 * 500_000, "settled on the last accepted revision (910 -> L = 0.5)");
        assertEq(usdc.balanceOf(buyer) - before, payout);
        vm.expectRevert(PolicyManager.NotSettleable.selector);
        pm.settlePolicy(policyId);
    }

    function test_voidOnlyWithoutReportAndAfterGrace() public {
        vm.expectRevert(OracleAdapter.NothingPosted.selector);
        oracle.finalize(IDX_LGA, D);
        uint256 voidAt = uint256(oracle.finalizeAt(IDX_LGA, D)) + 72 hours;
        vm.warp(voidAt - 1);
        vm.expectRevert(OracleAdapter.TooEarly.selector);
        oracle.voidDay(IDX_LGA, D);
        vm.warp(voidAt);
        oracle.voidDay(IDX_LGA, D);
        vm.expectRevert(OracleAdapter.NotFinal.selector);
        oracle.getFinal(IDX_LGA, D);
        uint64 asOf = uint64(block.timestamp);
        bytes memory sig7 = _signReport(IDX_LGA, D, 910, 0, asOf, REPORTER_PK);
        vm.expectRevert(OracleAdapter.DayVoided.selector);
        oracle.post(IDX_LGA, D, 910, 0, asOf, bytes32(0), sig7);
        // void refund of a bound policy = keptPremium - keptFee, once
        uint256 before = usdc.balanceOf(buyer);
        assertEq(pm.settlePolicy(policyId), 2_500_000 - 18_000);
        assertEq(usdc.balanceOf(buyer) - before, 2_500_000 - 18_000);
        vm.expectRevert(PolicyManager.NotSettleable.selector);
        pm.settlePolicy(policyId);
    }

    function test_cannotVoidAfterAReport() public {
        _post(IDX_LGA, D, 910, 0);
        vm.warp(uint256(oracle.finalizeAt(IDX_LGA, D)) + 72 hours);
        vm.expectRevert(OracleAdapter.AlreadyPosted.selector);
        oracle.voidDay(IDX_LGA, D);
    }
}
