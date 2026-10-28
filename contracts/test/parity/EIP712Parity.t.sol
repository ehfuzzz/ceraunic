// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {FixtureReader} from "./FixtureReader.sol";
import {OracleAdapter} from "../../src/OracleAdapter.sol";
import {PolicyManager} from "../../src/PolicyManager.sol";
import {IPolicyManager} from "../../src/interfaces/IPolicyManager.sol";
import {IPoolVault} from "../../src/interfaces/IPoolVault.sol";
import {IOracleAdapter} from "../../src/interfaces/IOracleAdapter.sol";

/// @notice SPEC 14 EIP-712 parity (eip712_cases.json): the contracts, deployed at the fixture's
///         verifyingContract on its chainId, produce the engine's typeHash and digest for Report,
///         Quote and RfqQuote, and the engine's signatures recover to the expected anvil signer.
contract EIP712Parity is FixtureReader {
    function test_eip712Parity() public {
        (bool ok, string memory json) = _fixture("eip712_cases.json");
        if (!ok) return;
        uint256 n = _count(json, ".cases");
        assertGe(n, 9, "SPEC 14 wants >= 3 cases per type");
        for (uint256 i; i < n; ++i) _case(json, string.concat(".cases[", vm.toString(i), "]"), i);
    }

    function _case(string memory json, string memory b, uint256 i) internal {
        string memory t = vm.parseJsonString(json, string.concat(b, ".type"));
        string memory at = string.concat("eip712 case ", vm.toString(i), " ", t);
        uint256 snap = vm.snapshotState();
        vm.chainId(vm.parseJsonUint(json, string.concat(b, ".domain.chainId")));
        bytes32 typeHash = vm.parseJsonBytes32(json, string.concat(b, ".expected.typeHash"));
        assertEq(keccak256(bytes(vm.parseJsonString(json, string.concat(b, ".typeString")))), typeHash, at);
        bytes32 digest = _eqStr(t, "Report") ? _reportDigest(json, b, typeHash, at) : _policyDigest(json, b, t, typeHash, at);
        assertEq(digest, vm.parseJsonBytes32(json, string.concat(b, ".expected.digest")), string.concat(at, ": digest"));
        bytes memory sig = vm.parseJsonBytes(json, string.concat(b, ".expected.signature"));
        assertEq(ECDSA.recover(digest, sig), vm.parseJsonAddress(json, string.concat(b, ".expected.signer")), string.concat(at, ": signer"));
        vm.revertToState(snap);
    }

    function _reportDigest(string memory json, string memory b, bytes32 typeHash, string memory at)
        internal
        returns (bytes32)
    {
        address vc = vm.parseJsonAddress(json, string.concat(b, ".domain.verifyingContract"));
        deployCodeTo("OracleAdapter.sol:OracleAdapter", abi.encode(address(this), uint64(1 days)), vc);
        OracleAdapter o = OracleAdapter(vc);
        assertEq(o.REPORT_TYPEHASH(), typeHash, string.concat(at, ": typeHash"));
        assertEq(
            o.domainSeparator(),
            vm.parseJsonBytes32(json, string.concat(b, ".expected.domainSeparator")),
            string.concat(at, ": domainSeparator")
        );
        string memory m = string.concat(b, ".message");
        return o.reportDigest(
            vm.parseJsonBytes32(json, string.concat(m, ".indexId")),
            uint32(vm.parseJsonUint(json, string.concat(m, ".day"))),
            int64(vm.parseJsonInt(json, string.concat(m, ".value"))),
            uint16(vm.parseJsonUint(json, string.concat(m, ".revision"))),
            uint64(vm.parseJsonUint(json, string.concat(m, ".asOf")))
        );
    }

    function _policyDigest(string memory json, string memory b, string memory t, bytes32 typeHash, string memory at)
        internal
        returns (bytes32)
    {
        address vc = vm.parseJsonAddress(json, string.concat(b, ".domain.verifyingContract"));
        deployCodeTo(
            "PolicyManager.sol:PolicyManager",
            abi.encode(address(1), address(2), address(3), address(4), address(5), address(6), address(this)),
            vc
        );
        PolicyManager pm = PolicyManager(vc);
        string memory m = string.concat(b, ".message");
        if (_eqStr(t, "Quote")) {
            assertEq(pm.QUOTE_TYPEHASH(), typeHash, string.concat(at, ": typeHash"));
            return pm.quoteDigest(_quote(json, m));
        }
        assertEq(pm.RFQ_TYPEHASH(), typeHash, string.concat(at, ": typeHash"));
        return pm.rfqDigest(_rfq(json, m));
    }

    function _quote(string memory json, string memory m) internal pure returns (IPolicyManager.Quote memory q) {
        q.market = vm.parseJsonBytes32(json, string.concat(m, ".market"));
        q.buyer = vm.parseJsonAddress(json, string.concat(m, ".buyer"));
        q.isLong = vm.parseJsonBool(json, string.concat(m, ".isLong"));
        q.units = uint128(vm.parseJsonUint(json, string.concat(m, ".units")));
        q.premium = uint128(vm.parseJsonUint(json, string.concat(m, ".premium")));
        q.fee = uint128(vm.parseJsonUint(json, string.concat(m, ".fee")));
        q.expiry = uint64(vm.parseJsonUint(json, string.concat(m, ".expiry")));
        q.nonce = vm.parseJsonUint(json, string.concat(m, ".nonce"));
    }

    function _rfq(string memory json, string memory m) internal pure returns (IPolicyManager.RfqQuote memory q) {
        q.requestId = vm.parseJsonBytes32(json, string.concat(m, ".requestId"));
        q.market = vm.parseJsonBytes32(json, string.concat(m, ".market"));
        q.maker = vm.parseJsonAddress(json, string.concat(m, ".maker"));
        q.taker = vm.parseJsonAddress(json, string.concat(m, ".taker"));
        q.takerLong = vm.parseJsonBool(json, string.concat(m, ".takerLong"));
        q.tick = uint8(vm.parseJsonUint(json, string.concat(m, ".tick")));
        q.maxQty = uint128(vm.parseJsonUint(json, string.concat(m, ".maxQty")));
        q.validUntil = uint64(vm.parseJsonUint(json, string.concat(m, ".validUntil")));
        q.nonce = vm.parseJsonUint(json, string.concat(m, ".nonce"));
    }
}
