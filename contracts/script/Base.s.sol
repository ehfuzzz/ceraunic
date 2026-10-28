// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Script} from "forge-std/Script.sol";
import {MockUSDC} from "../src/MockUSDC.sol";
import {WIToken} from "../src/WIToken.sol";
import {OracleAdapter} from "../src/OracleAdapter.sol";
import {PoolVault} from "../src/PoolVault.sol";
import {SeniorShare} from "../src/SeniorShare.sol";
import {WIStaking} from "../src/WIStaking.sol";
import {PolicyManager} from "../src/PolicyManager.sol";
import {BatchAuction} from "../src/BatchAuction.sol";
import {Lens} from "../src/Lens.sol";

/// @notice Shared address book loader for Configure / Smoke / E2E / Warp.
abstract contract Base is Script {
    uint256 internal constant UNIT = 1_000_000;

    string internal book;
    address internal deployer;
    uint256 internal startBlock;
    uint256 internal wiSupply;
    MockUSDC internal usdc;
    WIToken internal wi;
    OracleAdapter internal oracle;
    PoolVault internal pool;
    SeniorShare internal senior;
    WIStaking internal staking;
    PolicyManager internal pm;
    BatchAuction internal auction;
    Lens internal lens;

    function _bookPath() internal view returns (string memory) {
        return string.concat(vm.projectRoot(), "/deployments/", vm.toString(block.chainid), ".json");
    }

    function _load() internal {
        book = vm.readFile(_bookPath());
        require(vm.parseJsonUint(book, ".chainId") == block.chainid, "address book is for another chain");
        deployer = vm.parseJsonAddress(book, ".deployer");
        startBlock = vm.parseJsonUint(book, ".startBlock");
        wiSupply = vm.parseJsonUint(book, ".wiSupply");
        usdc = MockUSDC(vm.parseJsonAddress(book, ".MockUSDC"));
        wi = WIToken(vm.parseJsonAddress(book, ".WIToken"));
        oracle = OracleAdapter(vm.parseJsonAddress(book, ".OracleAdapter"));
        pool = PoolVault(vm.parseJsonAddress(book, ".PoolVault"));
        senior = SeniorShare(vm.parseJsonAddress(book, ".SeniorShare"));
        staking = WIStaking(vm.parseJsonAddress(book, ".WIStaking"));
        pm = PolicyManager(vm.parseJsonAddress(book, ".PolicyManager"));
        auction = BatchAuction(vm.parseJsonAddress(book, ".BatchAuction"));
        lens = Lens(vm.parseJsonAddress(book, ".Lens"));
    }

    function _id(string memory name) internal pure returns (bytes32) {
        return keccak256(bytes(name));
    }

    /// @dev Index names registered by Configure (SPEC 3). Windows: CLI 12h fetch lag, 24h dispute,
    ///      72h void grace.
    function _indexNames() internal pure returns (string[10] memory n) {
        n = [
            "CLI:NYC:TMAX:v1",
            "CLI:LGA:TMAX:v1",
            "CLI:JFK:TMAX:v1",
            "CLI:EWR:TMAX:v1",
            "CLI:NYC:PRCP:v1",
            "CLI:LGA:PRCP:v1",
            "PAIR:LGA-NYC:TMAX:v1",
            "PAIR:JFK-NYC:TMAX:v1",
            "PAIR:EWR-NYC:TMAX:v1",
            "RAIN:LGA-NYC:IND:v1"
        ];
    }
}
