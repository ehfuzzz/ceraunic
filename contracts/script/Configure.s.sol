// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {console} from "forge-std/Script.sol";
import {VmSafe} from "forge-std/Vm.sol";
import {Base} from "./Base.s.sol";
import {IOracleAdapter} from "../src/interfaces/IOracleAdapter.sol";
import {IBatchAuction} from "../src/interfaces/IBatchAuction.sol";

/// @notice Wiring, roles, params, MockUSDC seed, tranche seed, WI stake, index registry and demo
///         markets. Every transaction is small (run with big blocks OFF). Idempotent: re-running
///         skips what is already done. Broadcasts as the deployer (owner) only.
/// @dev Env (all optional): HOUSE, QUOTER, REPORTER, TREASURY (addresses; default deployer),
///      CAP_BPS, JMIN_BPS, SENIOR_PREMIUM_BPS, MIN_JUNIOR_FOR_SENIOR, JUNIOR_SEED, SENIOR_SEED,
///      HOUSE_USDC, USER_USDC, DEMO_USERS (comma-separated addresses), WI_STAKE, DEMO_DAY (epoch
///      day; default tomorrow UTC), DEMO_DAYS (default 1).
contract Configure is Base {
    address house;
    address quoter;
    address reporter;
    address treasury;
    string mk = "markets";
    string mjson;

    function run() external {
        _load();
        house = vm.envOr("HOUSE", deployer);
        quoter = vm.envOr("QUOTER", deployer);
        reporter = vm.envOr("REPORTER", deployer);
        treasury = vm.envOr("TREASURY", deployer);

        vm.startBroadcast();
        (, address sender,) = vm.readCallers();
        require(sender == deployer, "Configure must run as the deployer (owner)");
        _wire();
        _params();
        _indices();
        _seed();
        _markets();
        vm.stopBroadcast();
        _write();
    }

    function _wire() internal {
        if (pool.policyManager() == address(0)) pool.setPolicyManager(address(pm));
        if (pool.staking() == address(0)) pool.setStaking(address(staking));
        if (staking.pool() == address(0)) staking.setPool(address(pool));
        if (address(pm.auction()) == address(0)) pm.setAuction(IBatchAuction(address(auction)));
        if (pm.quoter() != quoter || pm.house() != house || pm.treasury() != treasury) {
            pm.setRoles(quoter, house, treasury);
        }
        if (auction.house() != house) auction.setHouse(house);
        if (auction.treasury() != treasury) auction.setTreasury(treasury);
        if (pool.house() != house) pool.setHouse(house);
        if (!pool.juniorDepositor(deployer)) pool.setJuniorDepositor(deployer, true);
        if (!pool.juniorDepositor(house)) pool.setJuniorDepositor(house, true);
        if (!oracle.isReporter(reporter)) oracle.setReporter(reporter, true);
        if (!pm.isMaker(house)) pm.setMaker(house, true);
    }

    function _params() internal {
        uint16 capBps = uint16(vm.envOr("CAP_BPS", uint256(8000)));
        uint16 jMinBps = uint16(vm.envOr("JMIN_BPS", uint256(2000)));
        uint16 spBps = uint16(vm.envOr("SENIOR_PREMIUM_BPS", uint256(30)));
        uint256 minJ = vm.envOr("MIN_JUNIOR_FOR_SENIOR", uint256(1_000 * UNIT));
        if (pool.capBps() != capBps || pool.jMinBps() != jMinBps || pool.seniorPremiumBps() != spBps
                || pool.minJuniorForSenior() != minJ) {
            pool.setParams(capBps, jMinBps, spBps, minJ);
        }
    }

    function _indices() internal {
        string[10] memory names = _indexNames();
        for (uint256 i; i < names.length; ++i) {
            bytes32 id = _id(names[i]);
            if (!oracle.registered(id)) {
                oracle.registerIndex(
                    id,
                    IOracleAdapter.IndexConfig({fetchLag: 12 hours, disputeWindow: 24 hours, voidGrace: 72 hours, active: true})
                );
            }
        }
    }

    function _seed() internal {
        uint256 juniorSeed = vm.envOr("JUNIOR_SEED", uint256(10_000 * UNIT));
        uint256 seniorSeed = vm.envOr("SENIOR_SEED", uint256(40_000 * UNIT));
        if (pool.juniorAssets() == 0 && juniorSeed != 0) {
            usdc.mint(deployer, juniorSeed + seniorSeed);
            usdc.approve(address(pool), juniorSeed + seniorSeed);
            pool.depositJunior(juniorSeed);
            if (seniorSeed != 0) pool.depositSenior(seniorSeed);
        }
        uint256 houseUsdc = vm.envOr("HOUSE_USDC", uint256(100_000 * UNIT));
        if (house != deployer && usdc.balanceOf(house) == 0 && houseUsdc != 0) usdc.mint(house, houseUsdc);
        address[] memory users = vm.envOr("DEMO_USERS", ",", new address[](0));
        uint256 userUsdc = vm.envOr("USER_USDC", uint256(10_000 * UNIT));
        for (uint256 i; i < users.length; ++i) {
            if (usdc.balanceOf(users[i]) == 0) usdc.mint(users[i], userUsdc);
        }
        uint256 wiStake = vm.envOr("WI_STAKE", uint256(1_000_000 ether));
        if (staking.totalStaked() == 0 && wiStake != 0) {
            wi.approve(address(staking), wiStake);
            staking.stake(wiStake);
        }
    }

    function _markets() internal {
        uint256 day0 = vm.envOr("DEMO_DAY", block.timestamp / 1 days + 1);
        uint256 n = vm.envOr("DEMO_DAYS", uint256(1));
        for (uint32 d = uint32(day0); d < uint32(day0 + n); ++d) {
            _market("CLI:NYC:TMAX:v1", d, 880, 940, false, "NYC_HEAT_CALL_88_94");
            _market("CLI:NYC:TMAX:v1", d, 650, 700, false, "NYC_COOL_PUT_65_70");
            _market("CLI:LGA:TMAX:v1", d, 880, 940, false, "LGA_HEAT_CALL_88_94");
            _market("CLI:LGA:PRCP:v1", d, 0, 1, false, "LGA_RAIN_DIGITAL");
            _market("PAIR:LGA-NYC:TMAX:v1", d, -50, 50, true, "BASIS_LGA_NYC");
            _market("PAIR:JFK-NYC:TMAX:v1", d, -50, 50, true, "BASIS_JFK_NYC");
            _market("PAIR:EWR-NYC:TMAX:v1", d, -50, 50, true, "BASIS_EWR_NYC");
            _market("RAIN:LGA-NYC:IND:v1", d, -1, 1, true, "RAIN_BASIS_LGA_NYC");
        }
        mjson = vm.serializeUint(mk, "day0", day0);
    }

    function _market(string memory idx, uint32 day, int64 lo, int64 hi, bool auctioned, string memory label)
        internal
    {
        bytes32 id = pm.marketIdOf(_id(idx), day, lo, hi);
        if (!pm.getMarket(id).exists) pm.createMarket(_id(idx), day, lo, hi, auctioned);
        vm.serializeBytes32(mk, string.concat(label, "_", vm.toString(uint256(day))), id);
    }

    function _write() internal {
        if (vm.isContext(VmSafe.ForgeContext.ScriptDryRun)) {
            console.log("dry run: not writing", _bookPath());
            return;
        }
        string memory k = "book";
        vm.serializeUint(k, "chainId", block.chainid);
        vm.serializeUint(k, "startBlock", startBlock);
        vm.serializeAddress(k, "deployer", deployer);
        vm.serializeAddress(k, "MockUSDC", address(usdc));
        vm.serializeAddress(k, "WIToken", address(wi));
        vm.serializeUint(k, "wiSupply", wiSupply);
        vm.serializeAddress(k, "OracleAdapter", address(oracle));
        vm.serializeAddress(k, "PoolVault", address(pool));
        vm.serializeAddress(k, "SeniorShare", address(senior));
        vm.serializeAddress(k, "WIStaking", address(staking));
        vm.serializeAddress(k, "PolicyManager", address(pm));
        vm.serializeAddress(k, "BatchAuction", address(auction));
        vm.serializeAddress(k, "Lens", address(lens));
        vm.serializeAddress(k, "house", house);
        vm.serializeAddress(k, "quoter", quoter);
        vm.serializeAddress(k, "reporter", reporter);
        vm.serializeAddress(k, "treasury", treasury);
        vm.serializeBool(k, "configured", true);
        string memory json = vm.serializeString(k, "markets", mjson);
        vm.writeJson(json, _bookPath());
        console.log("configured; wrote", _bookPath());
    }
}
