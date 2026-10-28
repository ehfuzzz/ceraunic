// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Script, console} from "forge-std/Script.sol";

/// @notice ANVIL ONLY. Moves anvil's clock to the E2E phase target and mines a block. No broadcast.
contract Warp is Script {
    function run(uint256 phase) external {
        require(block.chainid == 31337, "anvil only");
        string memory e = vm.readFile(string.concat(vm.projectRoot(), "/deployments/e2e-31337.json"));
        uint256 ts = vm.parseJsonUint(e, string.concat(".warp", vm.toString(phase)));
        vm.rpc("evm_setNextBlockTimestamp", string.concat("[", vm.toString(ts), "]"));
        vm.rpc("evm_mine", "[]");
        console.log("anvil time ->", ts);
    }
}
