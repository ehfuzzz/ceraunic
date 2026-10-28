// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {FixtureReader} from "./FixtureReader.sol";
import {OracleAdapter} from "../../src/OracleAdapter.sol";
import {IOracleAdapter} from "../../src/interfaces/IOracleAdapter.sol";

/// @notice SPEC 14 oracle parity: report acceptance P1-P8, finalize and void timing in
///         oracle_cases.json replayed on a real OracleAdapter; revert name, status, value and
///         revision after every step equal the engine's. engineOnly cases (vintage checks the chain
///         cannot make, because vintageHash is not signed) are skipped.
contract OracleParity is FixtureReader {
    string constant MNEMONIC = "test test test test test test test test test test test junk";

    struct Step {
        bool active;
        uint256 asOf;
        string op;
        uint256 revision;
        address signer;
        uint256 ts;
        int256 value;
        bytes32 vintageHash;
    }

    OracleAdapter oracle;
    uint256 reporterPk;
    address reporter;
    string caseName;

    function test_oracleParity() public {
        (bool ok, string memory json) = _fixture("oracle_cases.json");
        if (!ok) return;
        reporterPk = vm.deriveKey(MNEMONIC, 2);
        reporter = vm.addr(reporterPk);
        uint256 n = _count(json, ".cases");
        uint256 ran;
        for (uint256 i; i < n; ++i) {
            string memory base = string.concat(".cases[", vm.toString(i), "]");
            if (vm.parseJsonBool(json, string.concat(base, ".engineOnly"))) continue;
            caseName = vm.parseJsonString(json, string.concat(base, ".name"));
            bytes32 idx = vm.parseJsonBytes32(json, string.concat(base, ".indexId"));
            uint32 day = uint32(vm.parseJsonUint(json, string.concat(base, ".day")));
            oracle = new OracleAdapter(address(this), uint64(vm.parseJsonUint(json, string.concat(base, ".maxReportAge"))));
            oracle.setReporter(reporter, true);
            oracle.registerIndex(
                idx,
                IOracleAdapter.IndexConfig({
                    fetchLag: uint32(vm.parseJsonUint(json, string.concat(base, ".config.fetchLag"))),
                    disputeWindow: uint32(vm.parseJsonUint(json, string.concat(base, ".config.disputeWindow"))),
                    voidGrace: uint32(vm.parseJsonUint(json, string.concat(base, ".config.voidGrace"))),
                    active: true
                })
            );
            assertEq(oracle.fetchAt(idx, day), vm.parseJsonUint(json, string.concat(base, ".windows.fetchAt")));
            assertEq(oracle.finalizeAt(idx, day), vm.parseJsonUint(json, string.concat(base, ".windows.finalizeAt")));
            Step[] memory steps = abi.decode(vm.parseJson(json, string.concat(base, ".steps")), (Step[]));
            for (uint256 k; k < steps.length; ++k) {
                _step(json, string.concat(base, ".expected[", vm.toString(k), "]"), idx, day, steps[k], k);
            }
            ++ran;
        }
        assertGt(ran, 0);
    }

    function _post(bytes32 idx, uint32 day, Step memory s) internal returns (bool ok, bytes memory err) {
        // the engine's non-reporter signer has no key here: any non-allow-listed key is the same case
        uint256 pk = s.signer == reporter ? reporterPk : 0xBAD;
        bytes memory sig = _sig(pk, oracle.reportDigest(idx, day, int64(s.value), uint16(s.revision), uint64(s.asOf)));
        (ok, err) = address(oracle).call(
            abi.encodeCall(
                oracle.post, (idx, day, int64(s.value), uint16(s.revision), uint64(s.asOf), s.vintageHash, sig)
            )
        );
    }

    function _sig(uint256 pk, bytes32 digest) internal pure returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 sg) = vm.sign(pk, digest);
        return abi.encodePacked(r, sg, v);
    }

    function _step(string memory json, string memory eb, bytes32 idx, uint32 day, Step memory s, uint256 k) internal {
        vm.warp(s.ts);
        if (oracle.indexConfig(idx).active != s.active) oracle.setIndexActive(idx, s.active);
        bool ok;
        bytes memory err;
        bytes32 op = keccak256(bytes(s.op));
        if (op == keccak256("post")) {
            (ok, err) = _post(idx, day, s);
        } else if (op == keccak256("finalize")) {
            (ok, err) = address(oracle).call(abi.encodeCall(oracle.finalize, (idx, day)));
        } else if (op == keccak256("void")) {
            (ok, err) = address(oracle).call(abi.encodeCall(oracle.voidDay, (idx, day)));
        } else {
            revert(string.concat("unknown op ", s.op));
        }
        _check(json, eb, idx, day, ok, err, string.concat(caseName, " step ", vm.toString(k), " ", s.op));
    }

    function _check(
        string memory json,
        string memory eb,
        bytes32 idx,
        uint32 day,
        bool ok,
        bytes memory err,
        string memory at
    ) internal view {
        string memory want = vm.parseJsonString(json, string.concat(eb, ".revert"));
        if (bytes(want).length == 0) {
            assertTrue(ok, string.concat(at, ": reverted, engine accepted"));
        } else {
            assertFalse(ok, string.concat(at, ": accepted, engine reverted ", want));
            assertEq(_revertName(err), _sel(want), string.concat(at, ": wrong revert, want ", want));
        }
        IOracleAdapter.Observation memory o = oracle.observation(idx, day);
        string memory status = o.voided ? "void" : o.finalized ? "final" : o.posted ? "posted" : "none";
        assertEq(status, vm.parseJsonString(json, string.concat(eb, ".status")), string.concat(at, ": status"));
        assertEq(int256(o.value), vm.parseJsonInt(json, string.concat(eb, ".value")), string.concat(at, ": value"));
        int256 rev = o.posted ? int256(uint256(o.revision)) : int256(-1);
        assertEq(rev, vm.parseJsonInt(json, string.concat(eb, ".revision")), string.concat(at, ": revision"));
    }
}
