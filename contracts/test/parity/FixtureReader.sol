// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Test, console} from "forge-std/Test.sol";

/// @notice Loads a Phase 7 engine parity file from test/fixtures. If the file is absent the test is
///         skipped with a message (never replaced by a Solidity-generated fixture: that would be a mirror).
abstract contract FixtureReader is Test {
    function _fixture(string memory file) internal returns (bool ok, string memory json) {
        string memory path = string.concat(vm.projectRoot(), "/test/fixtures/", file);
        if (!vm.exists(path)) {
            string memory why = string.concat("parity fixture not found (written by the Phase 7 engine): ", path);
            console.log("SKIP:", why);
            vm.skip(true, why);
            return (false, "");
        }
        return (true, vm.readFile(path));
    }

    function _count(string memory json, string memory arrayPath) internal view returns (uint256 n) {
        while (vm.keyExistsJson(json, string.concat(arrayPath, "[", vm.toString(n), "]"))) ++n;
    }

    function _eqStr(string memory a, string memory b) internal pure returns (bool) {
        return keccak256(bytes(a)) == keccak256(bytes(b));
    }

    /// @dev Revert data -> custom error name check: expected "" means success.
    function _revertName(bytes memory data) internal pure returns (bytes4 sel) {
        if (data.length >= 4) {
            assembly {
                sel := mload(add(data, 32))
            }
        }
    }

    function _sel(string memory errorName) internal pure returns (bytes4) {
        return bytes4(keccak256(bytes(string.concat(errorName, "()"))));
    }
}
