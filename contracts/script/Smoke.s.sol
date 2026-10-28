// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {console} from "forge-std/Script.sol";
import {Base} from "./Base.s.sol";

/// @notice Read-only post-deploy checks. Sends no transaction. Reverts on the first failed check.
contract Smoke is Base {
    function run() external {
        _load();
        require(vm.keyExistsJson(book, ".configured"), "not configured: run Configure first");
        address house = vm.parseJsonAddress(book, ".house");
        address quoter = vm.parseJsonAddress(book, ".quoter");
        address reporter = vm.parseJsonAddress(book, ".reporter");
        address treasury = vm.parseJsonAddress(book, ".treasury");

        // code at every address
        address[9] memory all = [
            address(usdc), address(wi), address(oracle), address(pool), address(senior), address(staking),
            address(pm), address(auction), address(lens)
        ];
        for (uint256 i; i < all.length; ++i) require(all[i].code.length > 0, "missing code");

        // wiring
        require(pool.policyManager() == address(pm), "pool.policyManager");
        require(pool.staking() == address(staking), "pool.staking");
        require(staking.pool() == address(pool), "staking.pool");
        require(address(pm.auction()) == address(auction), "pm.auction");
        require(address(auction.pm()) == address(pm), "auction.pm");
        require(address(pool.senior()) == address(senior) && senior.vault() == address(pool), "senior share");
        require(address(pm.pool()) == address(pool) && address(pm.oracle()) == address(oracle), "pm deps");
        require(staking.wi() == address(wi), "staking.wi");
        // roles
        require(pm.house() == house && auction.house() == house && pool.house() == house, "house");
        require(pm.quoter() == quoter, "quoter");
        require(pm.treasury() == treasury && auction.treasury() == treasury, "treasury");
        require(oracle.isReporter(reporter), "reporter");
        require(pool.juniorDepositor(house), "junior depositor");
        // ownership
        require(pool.owner() == deployer && pm.owner() == deployer && auction.owner() == deployer, "owner");
        require(oracle.owner() == deployer && staking.owner() == deployer, "owner");
        require(!pool.paused() && !pm.paused() && !auction.paused(), "paused");

        // money identities
        uint256 cap = pool.capital();
        require(pool.juniorAssets() > 0, "junior not seeded");
        // >= rather than ==: anyone can donate MockUSDC on a public testnet; ledgers ignore donations.
        require(usdc.balanceOf(address(pool)) >= cap - pool.deployed(), "pool cash identity");
        require((pool.reserved() + pool.deployed()) * 10_000 <= uint256(pool.capBps()) * cap, "C1");
        require(pool.juniorAssets() * 10_000 >= uint256(pool.jMinBps()) * cap, "C2");
        require(
            usdc.balanceOf(address(pm)) >= pm.policyEscrow() + pm.totalCollateral() + pm.totalMargin(),
            "pm balance identity"
        );
        require(wi.totalSupply() + staking.totalBurned() == wiSupply, "WI supply");
        require(wi.balanceOf(address(staking)) == staking.totalStaked(), "staking balance");

        // registry + demo markets
        string[10] memory names = _indexNames();
        for (uint256 i; i < names.length; ++i) require(oracle.isActive(_id(names[i])), "index not active");
        uint256 day0 = vm.parseJsonUint(book, ".markets.day0");
        bytes32 basis = pm.marketIdOf(_id("PAIR:LGA-NYC:TMAX:v1"), uint32(day0), -50, 50);
        require(pm.getMarket(basis).exists && auction.getBook(basis).opened, "demo basis market");
        lens.userView(house); // the one-call view works

        console.log("smoke OK: chain", block.chainid);
        console.log("  capital (USDC base units)", cap);
        console.log("  junior", pool.juniorAssets());
        console.log("  senior", pool.seniorAssets());
        console.log("  WI staked", staking.totalStaked());
    }
}
