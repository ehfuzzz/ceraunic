// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Test} from "forge-std/Test.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {MockUSDC} from "../src/MockUSDC.sol";
import {WIToken} from "../src/WIToken.sol";
import {OracleAdapter} from "../src/OracleAdapter.sol";
import {PoolVault} from "../src/PoolVault.sol";
import {WIStaking} from "../src/WIStaking.sol";
import {PolicyManager} from "../src/PolicyManager.sol";
import {BatchAuction} from "../src/BatchAuction.sol";
import {IPoolVault} from "../src/interfaces/IPoolVault.sol";
import {IOracleAdapter} from "../src/interfaces/IOracleAdapter.sol";
import {IPolicyManager} from "../src/interfaces/IPolicyManager.sol";
import {IBatchAuction} from "../src/interfaces/IBatchAuction.sol";

/// @notice Deploys and wires the protocol the way Configure does, with test keys. Not a test.
abstract contract ProtocolFixture is Test {
    uint256 internal constant UNIT = 1_000_000;
    uint256 internal constant TICK = 10_000;

    uint256 internal constant ADMIN_PK = 0xA11CE;
    uint256 internal constant HOUSE_PK = 0xB0B; // house + quoter + RFQ maker
    uint256 internal constant REPORTER_PK = 0xC0FFEE;
    address internal admin;
    address internal house;
    address internal reporter;
    address internal treasury = address(0x7EA5);

    MockUSDC internal usdc;
    WIToken internal wi;
    OracleAdapter internal oracle;
    PoolVault internal pool;
    WIStaking internal staking;
    PolicyManager internal pm;
    BatchAuction internal auction;

    // day D = 20,000 (2024-10-04); tests start at D-1 15:00Z
    uint32 internal constant D = 20_000;
    uint256 internal constant T0 = uint256(D) * 1 days - 9 hours;
    bytes32 internal IDX_LGA;
    bytes32 internal IDX_BASIS;

    function _deploy() internal {
        admin = vm.addr(ADMIN_PK);
        house = vm.addr(HOUSE_PK);
        reporter = vm.addr(REPORTER_PK);
        vm.warp(T0);
        vm.startPrank(admin);
        usdc = new MockUSDC();
        wi = new WIToken(admin, 1_000_000_000 ether);
        oracle = new OracleAdapter(admin, 24 hours);
        pool = new PoolVault(IERC20(address(usdc)), admin, 12 days, 10 days);
        staking = new WIStaking(address(wi), admin, 12 days);
        pm = new PolicyManager(
            IERC20(address(usdc)), IPoolVault(address(pool)), IOracleAdapter(address(oracle)), house, house, treasury, admin
        );
        auction = new BatchAuction(IERC20(address(usdc)), IPolicyManager(address(pm)), treasury, house, admin);
        pool.setPolicyManager(address(pm));
        pool.setStaking(address(staking));
        staking.setPool(address(pool));
        pm.setAuction(IBatchAuction(address(auction)));
        pool.setHouse(house);
        pool.setJuniorDepositor(admin, true);
        pool.setJuniorDepositor(house, true);
        oracle.setReporter(reporter, true);
        pm.setMaker(house, true);
        IDX_LGA = keccak256("CLI:LGA:TMAX:v1");
        IDX_BASIS = keccak256("PAIR:LGA-NYC:TMAX:v1");
        IOracleAdapter.IndexConfig memory cli =
            IOracleAdapter.IndexConfig({fetchLag: 12 hours, disputeWindow: 24 hours, voidGrace: 72 hours, active: true});
        oracle.registerIndex(IDX_LGA, cli);
        oracle.registerIndex(IDX_BASIS, cli);
        vm.stopPrank();
    }

    function _fund(address who, uint256 amount) internal {
        usdc.mint(who, amount);
        vm.startPrank(who);
        usdc.approve(address(pool), type(uint256).max);
        usdc.approve(address(pm), type(uint256).max);
        usdc.approve(address(auction), type(uint256).max);
        vm.stopPrank();
    }

    function _seedPool(uint256 junior, uint256 senior_) internal {
        _fund(admin, junior + senior_);
        vm.startPrank(admin);
        pool.depositJunior(junior);
        if (senior_ != 0) pool.depositSenior(senior_);
        vm.stopPrank();
    }

    function _signQuote(IPolicyManager.Quote memory q, uint256 pk) internal view returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, pm.quoteDigest(q));
        return abi.encodePacked(r, s, v);
    }

    function _quote(bytes32 market, address buyer, bool isLong, uint128 units, uint128 premium, uint128 fee, uint256 nonce)
        internal
        view
        returns (IPolicyManager.Quote memory q)
    {
        q = IPolicyManager.Quote(market, buyer, isLong, units, premium, fee, uint64(block.timestamp + 1 hours), nonce);
    }

    function _buy(bytes32 market, address buyer, bool isLong, uint128 units, uint128 premium, uint128 fee, uint256 nonce)
        internal
        returns (uint256 id)
    {
        IPolicyManager.Quote memory q = _quote(market, buyer, isLong, units, premium, fee, nonce);
        bytes memory sig = _signQuote(q, HOUSE_PK);
        vm.prank(buyer);
        id = pm.buyPolicy(q, sig);
    }

    function _signReport(bytes32 idx, uint32 day, int64 value, uint16 rev, uint64 asOf, uint256 pk)
        internal
        view
        returns (bytes memory)
    {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, oracle.reportDigest(idx, day, value, rev, asOf));
        return abi.encodePacked(r, s, v);
    }

    function _post(bytes32 idx, uint32 day, int64 value, uint16 rev) internal {
        uint64 asOf = uint64(block.timestamp);
        oracle.post(idx, day, value, rev, asOf, bytes32(0), _signReport(idx, day, value, rev, asOf, REPORTER_PK));
    }

    /// @dev Post at fetchAt, finalize at finalizeAt; leaves time at finalizeAt.
    function _finalizeValue(bytes32 idx, uint32 day, int64 value) internal {
        vm.warp(oracle.fetchAt(idx, day));
        _post(idx, day, value, 0);
        vm.warp(oracle.finalizeAt(idx, day));
        oracle.finalize(idx, day);
    }
}
