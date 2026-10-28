// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Script, console} from "forge-std/Script.sol";
import {VmSafe} from "forge-std/Vm.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {MockUSDC} from "../src/MockUSDC.sol";
import {WIToken} from "../src/WIToken.sol";
import {OracleAdapter} from "../src/OracleAdapter.sol";
import {PoolVault} from "../src/PoolVault.sol";
import {WIStaking} from "../src/WIStaking.sol";
import {PolicyManager} from "../src/PolicyManager.sol";
import {BatchAuction} from "../src/BatchAuction.sol";
import {Lens} from "../src/Lens.sol";
import {IPoolVault} from "../src/interfaces/IPoolVault.sol";
import {IOracleAdapter} from "../src/interfaces/IOracleAdapter.sol";
import {IPolicyManager} from "../src/interfaces/IPolicyManager.sol";

/// @notice CREATE-only deploy (run with big blocks ON on HyperEVM). No wiring here: every call
///         after the CREATEs lives in Configure.s.sol (small blocks). Writes
///         deployments/<chainId>.json with addresses and startBlock.
/// @dev Signer comes from the CLI: `--account <keystore>` on testnet, anvil's public key locally.
///      Roles are set to the deployer here and re-pointed by Configure from env.
contract Deploy is Script {
    MockUSDC usdc;
    WIToken wi;
    OracleAdapter oracle;
    PoolVault pool;
    WIStaking staking;
    PolicyManager pm;
    BatchAuction auction;
    Lens lens;
    address deployer;

    function run() external {
        uint256 startBlock = block.number;
        uint256 wiSupply = vm.envOr("WI_SUPPLY", uint256(1_000_000_000 ether));
        vm.startBroadcast();
        (, deployer,) = vm.readCallers();
        _deploy(wiSupply);
        vm.stopBroadcast();
        _write(startBlock, wiSupply);
    }

    function _deploy(uint256 wiSupply) internal {
        uint64 withdrawDelay = uint64(vm.envOr("WITHDRAW_DELAY_S", uint256(12 days)));
        uint64 houseReturnWindow = uint64(vm.envOr("HOUSE_RETURN_WINDOW_S", uint256(10 days)));
        uint64 unstakeCooldown = uint64(vm.envOr("UNSTAKE_COOLDOWN_S", uint256(12 days)));
        uint64 maxReportAge = uint64(vm.envOr("MAX_REPORT_AGE_S", uint256(24 hours)));
        // SPEC 17 guard: a leaver (LP or staker) must still be inside the pool when an unreturned house
        // deployment is written off, or the loss / haircut misses them. PoolVault enforces it too.
        require(withdrawDelay >= houseReturnWindow + 2 days, "WITHDRAW_DELAY_S < HOUSE_RETURN_WINDOW_S + 2 days");
        require(unstakeCooldown >= houseReturnWindow + 2 days, "UNSTAKE_COOLDOWN_S < HOUSE_RETURN_WINDOW_S + 2 days");
        usdc = new MockUSDC();
        wi = new WIToken(deployer, wiSupply);
        oracle = new OracleAdapter(deployer, maxReportAge);
        pool = new PoolVault(IERC20(address(usdc)), deployer, withdrawDelay, houseReturnWindow);
        staking = new WIStaking(address(wi), deployer, unstakeCooldown);
        pm = new PolicyManager(
            IERC20(address(usdc)),
            IPoolVault(address(pool)),
            IOracleAdapter(address(oracle)),
            deployer,
            deployer,
            deployer,
            deployer
        );
        auction = new BatchAuction(IERC20(address(usdc)), IPolicyManager(address(pm)), deployer, deployer, deployer);
        lens = new Lens(IERC20(address(usdc)), pool, pm, auction, IOracleAdapter(address(oracle)), staking);
    }

    function _bookPathForLog() internal view returns (string memory) {
        return string.concat("deployments/", vm.toString(block.chainid), ".json");
    }

    function _write(uint256 startBlock, uint256 wiSupply) internal {
        if (vm.isContext(VmSafe.ForgeContext.ScriptDryRun)) {
            console.log("dry run: not writing", _bookPathForLog());
            return;
        }
        string memory k = "deploy";
        vm.serializeUint(k, "chainId", block.chainid);
        vm.serializeUint(k, "startBlock", startBlock);
        vm.serializeAddress(k, "deployer", deployer);
        vm.serializeAddress(k, "MockUSDC", address(usdc));
        vm.serializeAddress(k, "WIToken", address(wi));
        vm.serializeUint(k, "wiSupply", wiSupply);
        vm.serializeAddress(k, "OracleAdapter", address(oracle));
        vm.serializeAddress(k, "PoolVault", address(pool));
        vm.serializeAddress(k, "SeniorShare", address(pool.senior()));
        vm.serializeAddress(k, "WIStaking", address(staking));
        vm.serializeAddress(k, "PolicyManager", address(pm));
        vm.serializeAddress(k, "BatchAuction", address(auction));
        string memory json = vm.serializeAddress(k, "Lens", address(lens));
        string memory path = string.concat(vm.projectRoot(), "/deployments/", vm.toString(block.chainid), ".json");
        vm.writeJson(json, path);
        console.log("wrote", path);
    }
}
