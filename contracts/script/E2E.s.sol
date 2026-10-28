// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {console} from "forge-std/Script.sol";
import {Base} from "./Base.s.sol";
import {IPolicyManager} from "../src/interfaces/IPolicyManager.sol";
import {IPoolVault} from "../src/interfaces/IPoolVault.sol";
import {IOracleAdapter} from "../src/interfaces/IOracleAdapter.sol";

/// @notice ANVIL ONLY. Full protocol day under a 3,000,000 gas block limit, in five phases with
///         time jumps in between (script/Warp.s.sol). Actors are anvil's PUBLIC dev keys
///         (#0 admin, #1 house + quoter + RFQ maker, #2 reporter, #3 keeper/treasury, #4-#9 users).
///         Phase 5 asserts the money identities exactly and writes deployments/e2e-31337.json.
contract E2E is Base {
    string constant MNEMONIC = "test test test test test test test test test test test junk";

    uint256 pkAdmin;
    uint256 pkHouse;
    uint256 pkReporter;
    uint256 pkKeeper;
    uint256[6] pkUser;
    address house;
    address keeper;
    address[6] user;

    uint32 day;
    bytes32 mLgaCall;
    bytes32 mNycPut;
    bytes32 mBasisLga;
    bytes32 mBasisJfk;
    bytes32 mBasisEwr;
    bytes32 mRain;

    function _setup() internal {
        require(block.chainid == 31337, "E2E is anvil-only");
        _load();
        pkAdmin = vm.deriveKey(MNEMONIC, 0);
        pkHouse = vm.deriveKey(MNEMONIC, 1);
        pkReporter = vm.deriveKey(MNEMONIC, 2);
        pkKeeper = vm.deriveKey(MNEMONIC, 3);
        house = vm.addr(pkHouse);
        keeper = vm.addr(pkKeeper);
        for (uint256 i; i < 6; ++i) {
            pkUser[i] = vm.deriveKey(MNEMONIC, uint32(4 + i));
            user[i] = vm.addr(pkUser[i]);
        }
        day = uint32(vm.parseJsonUint(book, ".markets.day0"));
        mLgaCall = pm.marketIdOf(_id("CLI:LGA:TMAX:v1"), day, 880, 940);
        mNycPut = pm.marketIdOf(_id("CLI:NYC:TMAX:v1"), day, 650, 700);
        mBasisLga = pm.marketIdOf(_id("PAIR:LGA-NYC:TMAX:v1"), day, -50, 50);
        mBasisJfk = pm.marketIdOf(_id("PAIR:JFK-NYC:TMAX:v1"), day, -50, 50);
        mBasisEwr = pm.marketIdOf(_id("PAIR:EWR-NYC:TMAX:v1"), day, -50, 50);
        mRain = pm.marketIdOf(_id("RAIN:LGA-NYC:IND:v1"), day, -1, 1);
    }

    function _e2ePath() internal view returns (string memory) {
        return string.concat(vm.projectRoot(), "/deployments/e2e-", vm.toString(block.chainid), ".json");
    }

    function run(uint256 phase) external {
        _setup();
        if (phase == 1) _phase1();
        else if (phase == 2) _phase2();
        else if (phase == 3) _phase3();
        else if (phase == 4) _phase4();
        else if (phase == 5) _phase5();
        else revert("phase 1..5");
    }

    // ------------------------------------------------------------ phase 1: before saleCutoff
    function _phase1() internal {
        require(block.timestamp < pm.getMarket(mLgaCall).saleCutoff, "phase 1 must run before saleCutoff");
        uint256 firstOrder = auction.lastOrderId() + 1;

        // WI: user4 stakes, then puts half into cooldown (still cuttable).
        vm.startBroadcast(pkAdmin);
        wi.transfer(user[0], 100_000 ether);
        // LP: admin asks to withdraw 10% of its senior shares (claimed in phase 5 at claim-time NAV).
        pool.requestWithdraw(IPoolVault.Tranche.Senior, senior.balanceOf(vm.addr(pkAdmin)) / 10);
        vm.stopBroadcast();
        vm.startBroadcast(pkUser[0]);
        wi.approve(address(staking), 100_000 ether);
        uint256 sh = staking.stake(100_000 ether);
        staking.requestUnstake(sh / 2);
        vm.stopBroadcast();

        // Policies at house-signed quotes.
        uint256 p1 = _buy(pkUser[0], mLgaCall, true, 6, 2_500_000, 18_000, 1);
        uint256 p2 = _buy(pkUser[1], mNycPut, false, 10, 3_000_000, 30_000, 2);

        // House residual leg for p1 (h = 6 at tick 68) + public orders -> marginal split at 68.
        vm.startBroadcast(pkHouse);
        usdc.approve(address(auction), type(uint256).max);
        usdc.approve(address(pool), type(uint256).max);
        usdc.approve(address(pm), type(uint256).max);
        uint256 houseOrder = auction.placeOrder(mBasisLga, true, 68, 6);
        pool.fundHouse(day, 1_000 * UNIT);
        pm.depositMargin(100 * UNIT);
        vm.stopBroadcast();
        _order(pkUser[3], mBasisLga, true, 72, 3);
        _order(pkUser[2], mBasisLga, false, 60, 4);
        _order(pkUser[4], mBasisLga, false, 66, 3);

        // RFQ: house quotes, user9 takes 5 long at tick 55 on the JFK basis (voided later).
        IPolicyManager.RfqQuote memory q = IPolicyManager.RfqQuote({
            requestId: keccak256("rfq-1"),
            market: mBasisJfk,
            maker: house,
            taker: user[5],
            takerLong: true,
            tick: 55,
            maxQty: 10,
            validUntil: uint64(block.timestamp + 1 hours),
            nonce: 1
        });
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pkHouse, pm.rfqDigest(q));
        vm.startBroadcast(pkUser[5]);
        usdc.approve(address(pm), type(uint256).max);
        pm.acceptRfq(q, abi.encodePacked(r, s, v), 5);
        vm.stopBroadcast();

        // Worst-case book for the gas proof: 200 orders, every tick 1..99 populated on both sides.
        // Bids come from the house (exempt from the public limits); offers from six users, each at the
        // 1 USDC minimum escrow or more and at most 20 per user (08-HARDEN #2).
        for (uint256 i; i < 6; ++i) {
            vm.startBroadcast(pkUser[i]);
            usdc.approve(address(auction), type(uint256).max);
            vm.stopBroadcast();
        }
        vm.startBroadcast(pkHouse);
        for (uint256 t = 1; t <= 99; ++t) {
            auction.placeOrder(mBasisEwr, true, uint8(t), uint128(1 + t % 3));
        }
        auction.placeOrder(mBasisEwr, true, 50, 2);
        vm.stopBroadcast();
        for (uint256 t = 1; t <= 99; ++t) {
            _orderNoApprove(pkUser[(t + 3) % 6], mBasisEwr, false, uint8(t), uint128((199 - t) / (100 - t) + (t * 7) % 4));
        }
        _orderNoApprove(pkUser[1], mBasisEwr, false, 50, 2);
        require(auction.getBook(mBasisEwr).orderCount == 200, "worst-case book not full");

        string memory k = "e2e";
        vm.serializeUint(k, "day", day);
        vm.serializeUint(k, "policy1", p1);
        vm.serializeUint(k, "policy2", p2);
        vm.serializeUint(k, "houseOrder", houseOrder);
        vm.serializeUint(k, "firstOrder", firstOrder);
        vm.serializeUint(k, "lastOrder", auction.lastOrderId());
        uint256 ds = uint256(day) * 1 days;
        vm.serializeUint(k, "warp2", ds + 3 hours + 60); // after cutoff, before bindBy
        vm.serializeUint(k, "warp3", ds + 1 days + 12 hours + 60); // fetchAt(D) + 60
        vm.serializeUint(k, "warp4", ds + 2 days + 12 hours + 60); // finalizeAt(D) + 60
        string memory json = vm.serializeUint(k, "warp5", ds + 5 days + 12 hours + 60); // void allowed
        vm.writeJson(json, _e2ePath());
    }

    // ------------------------------------------------------------ phase 2: clear, bind, claim
    function _phase2() internal {
        string memory e = vm.readFile(_e2ePath());
        vm.startBroadcast(pkKeeper);
        auction.clear(mBasisLga);
        auction.clear(mBasisJfk);
        auction.clear(mBasisEwr);
        auction.clear(mRain);
        vm.stopBroadcast();
        vm.startBroadcast(pkHouse);
        uint128 bound = pm.bind(vm.parseJsonUint(e, ".policy1"), vm.parseJsonUint(e, ".houseOrder"));
        pm.bind(vm.parseJsonUint(e, ".policy2"), 0);
        vm.stopBroadcast();
        require(bound == 4, "expected downsizing 6 -> 4 (house fill 4 of 6)");
        uint256 last = vm.parseJsonUint(e, ".lastOrder");
        vm.startBroadcast(pkKeeper);
        for (uint256 id = vm.parseJsonUint(e, ".firstOrder"); id <= last; ++id) auction.claim(id);
        vm.stopBroadcast();
    }

    // ------------------------------------------------------------ phase 3: reports, house return
    function _phase3() internal {
        _post("CLI:LGA:TMAX:v1", 905, 0);
        _post("CLI:LGA:TMAX:v1", 910, 1); // same-vintage transcription fix
        _post("CLI:NYC:TMAX:v1", 670, 0);
        _post("PAIR:LGA-NYC:TMAX:v1", 30, 0);
        _post("PAIR:EWR-NYC:TMAX:v1", -12, 0);
        // nothing posted for PAIR:JFK-NYC -> void in phase 5
        vm.startBroadcast(pkHouse);
        pool.returnFromHouse(day, 950 * UNIT); // paper hedge lost 50 USDC -> junior loss -> WI haircut at closeDay
        vm.stopBroadcast();
    }

    // ------------------------------------------------------------ phase 4: finalize, settle, claim
    function _phase4() internal {
        string memory e = vm.readFile(_e2ePath());
        vm.startBroadcast(pkKeeper);
        oracle.finalize(_id("CLI:LGA:TMAX:v1"), day);
        oracle.finalize(_id("CLI:NYC:TMAX:v1"), day);
        oracle.finalize(_id("PAIR:LGA-NYC:TMAX:v1"), day);
        oracle.finalize(_id("PAIR:EWR-NYC:TMAX:v1"), day);
        pm.settlePolicy(vm.parseJsonUint(e, ".policy1"));
        pm.settlePolicy(vm.parseJsonUint(e, ".policy2"));
        vm.stopBroadcast();
        _claimAllPositions();
    }

    // ------------------------------------------------------------ phase 5: void, close, assert
    function _phase5() internal {
        vm.startBroadcast(pkKeeper);
        oracle.voidDay(_id("PAIR:JFK-NYC:TMAX:v1"), day);
        pool.claimWithdraw(1);
        vm.stopBroadcast();
        _claimAllPositions();
        vm.startBroadcast(pkKeeper);
        pool.closeDay(day); // haircut cuts user4's cooldown shares too
        vm.stopBroadcast();
        vm.startBroadcast(pkUser[0]);
        staking.claimUnstake(1);
        vm.stopBroadcast();
        _assertAndWrite();
    }

    // ------------------------------------------------------------ helpers
    function _buy(uint256 pk, bytes32 m, bool isLong, uint128 units, uint128 premium, uint128 fee, uint256 nonce)
        internal
        returns (uint256 id)
    {
        address buyer = vm.addr(pk);
        IPolicyManager.Quote memory q = IPolicyManager.Quote({
            market: m,
            buyer: buyer,
            isLong: isLong,
            units: units,
            premium: premium,
            fee: fee,
            expiry: uint64(block.timestamp + 1 hours),
            nonce: nonce
        });
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pkHouse, pm.quoteDigest(q)); // #1 is the quoter
        vm.startBroadcast(pk);
        usdc.approve(address(pm), type(uint256).max);
        id = pm.buyPolicy(q, abi.encodePacked(r, s, v));
        vm.stopBroadcast();
    }

    function _order(uint256 pk, bytes32 m, bool isBid, uint8 tick, uint128 qty) internal {
        vm.startBroadcast(pk);
        usdc.approve(address(auction), type(uint256).max);
        auction.placeOrder(m, isBid, tick, qty);
        vm.stopBroadcast();
    }

    function _orderNoApprove(uint256 pk, bytes32 m, bool isBid, uint8 tick, uint128 qty) internal {
        vm.startBroadcast(pk);
        auction.placeOrder(m, isBid, tick, qty);
        vm.stopBroadcast();
    }

    function _post(string memory idx, int64 value, uint16 revision) internal {
        bytes32 id = _id(idx);
        uint64 asOf = uint64(block.timestamp);
        bytes32 vintage = keccak256(abi.encode(idx, day, "fixture-vintage"));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pkReporter, oracle.reportDigest(id, day, value, revision, asOf));
        vm.startBroadcast(pkKeeper); // anyone relays
        oracle.post(id, day, value, revision, asOf, vintage, abi.encodePacked(r, s, v));
        vm.stopBroadcast();
    }

    function _claimAllPositions() internal {
        _claimFor(pkHouse);
        for (uint256 i; i < 6; ++i) _claimFor(pkUser[i]);
    }

    function _claimFor(uint256 pk) internal {
        address who = vm.addr(pk);
        bytes32[] memory ms = pm.marketsOf(who);
        for (uint256 i; i < ms.length; ++i) {
            if (pm.positionOf(ms[i], who).claimed) continue;
            IPolicyManager.Market memory m = pm.getMarket(ms[i]);
            IOracleAdapter.Observation memory o = oracle.observation(m.indexId, m.day);
            if (!o.finalized && !o.voided) continue;
            vm.startBroadcast(pk);
            pm.claimPosition(ms[i]);
            vm.stopBroadcast();
        }
    }

    function _assertAndWrite() internal {
        // exact money identities (no donations on this chain)
        require(usdc.balanceOf(address(auction)) == 0, "auction must hold 0 after all claims");
        require(pm.totalCollateral() == 0, "all market collateral paid out");
        require(pm.policyEscrow() == 0, "no unbound premium left");
        require(usdc.balanceOf(address(pm)) == pm.totalMargin(), "pm holds exactly the maker margin");
        require(usdc.balanceOf(address(pool)) == pool.capital() - pool.deployed(), "pool cash identity");
        require(pool.reserved() == 0 && pool.deployed() == 0 && pool.openPolicies(day) == 0, "pool day open");
        require(pool.dayClosed(day), "day closed");
        require(wi.totalSupply() + staking.totalBurned() == wiSupply, "WI conservation");
        require(wi.balanceOf(address(staking)) == staking.totalStaked(), "staking balance");

        address[16] memory who = [
            vm.addr(pkAdmin), house, vm.addr(pkReporter), keeper, user[0], user[1], user[2], user[3], user[4],
            user[5], address(pool), address(pm), address(auction), address(staking), address(wi), address(lens)
        ];
        uint256 sum;
        string memory b = "balances";
        string memory bj;
        for (uint256 i; i < who.length; ++i) {
            uint256 bal = usdc.balanceOf(who[i]);
            sum += bal;
            bj = vm.serializeUint(b, vm.toString(who[i]), bal);
        }
        require(sum == usdc.totalSupply(), "USDC left the known actor set");

        string memory e = vm.readFile(_e2ePath());
        string memory k = "e2e";
        vm.serializeUint(k, "day", day);
        vm.serializeUint(k, "policy1", vm.parseJsonUint(e, ".policy1"));
        vm.serializeUint(k, "policy2", vm.parseJsonUint(e, ".policy2"));
        vm.serializeUint(k, "policy1BoundUnits", pm.getPolicy(vm.parseJsonUint(e, ".policy1")).boundUnits);
        vm.serializeUint(k, "houseOrder", vm.parseJsonUint(e, ".houseOrder"));
        vm.serializeUint(k, "firstOrder", vm.parseJsonUint(e, ".firstOrder"));
        vm.serializeUint(k, "lastOrder", vm.parseJsonUint(e, ".lastOrder"));
        vm.serializeUint(k, "worstBookQStar", auction.getBook(mBasisEwr).qStar);
        vm.serializeUint(k, "worstBookPStar", auction.getBook(mBasisEwr).pStar);
        vm.serializeUint(k, "usdcTotalSupply", usdc.totalSupply());
        vm.serializeUint(k, "seniorAssets", pool.seniorAssets());
        vm.serializeUint(k, "juniorAssets", pool.juniorAssets());
        vm.serializeInt(k, "dayPnl", pool.dayPnl(day));
        vm.serializeUint(k, "wiBurned", staking.totalBurned());
        vm.serializeUint(k, "wiTotalStaked", staking.totalStaked());
        vm.serializeBool(k, "identitiesHold", true);
        string memory json = vm.serializeString(k, "usdcBalances", bj);
        vm.writeJson(json, _e2ePath());
        console.log("E2E OK. junior", pool.juniorAssets(), "senior", pool.seniorAssets());
        console.log("  WI burned", staking.totalBurned());
    }
}
