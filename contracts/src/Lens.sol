// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {IPolicyManager} from "./interfaces/IPolicyManager.sol";
import {IBatchAuction} from "./interfaces/IBatchAuction.sol";
import {IOracleAdapter} from "./interfaces/IOracleAdapter.sol";
import {IPoolVault} from "./interfaces/IPoolVault.sol";
import {PoolVault} from "./PoolVault.sol";
import {PolicyManager} from "./PolicyManager.sol";
import {BatchAuction} from "./BatchAuction.sol";
import {WIStaking} from "./WIStaking.sol";
import {Payoff} from "./lib/Payoff.sol";

/// @title Lens
/// @notice Read-only aggregation so the API/portal gets a user's policies, orders, positions, pool
///         and staking state in one eth_call. Holds no funds and no state besides addresses.
contract Lens {
    uint256 internal constant UNIT = 1_000_000;

    IERC20 public immutable usdc;
    PoolVault public immutable pool;
    PolicyManager public immutable pm;
    BatchAuction public immutable auction;
    IOracleAdapter public immutable oracle;
    WIStaking public immutable staking;

    struct Settle {
        bool posted;
        bool finalized;
        bool voided;
        int64 value;
        uint16 revision;
    }

    struct PoolView {
        uint256 seniorAssets;
        uint256 juniorAssets;
        uint256 capital;
        uint256 cash;
        uint256 reserved;
        uint256 deployed;
        uint256 seniorSupply;
        uint256 juniorSupply;
        uint16 capBps;
        uint16 jMinBps;
        uint16 seniorPremiumBps;
    }

    struct PolicyView {
        uint256 policyId;
        IPolicyManager.Policy policy;
        IPolicyManager.Market market;
        Settle settle;
        uint256 residualOrderId;
        uint256 maxPayout; // boundUnits (or units if unbound) * UNIT
        uint256 payoutIfSettledNow; // 0 unless the index-day is final and the policy is Bound
    }

    struct OrderView {
        uint256 orderId;
        IBatchAuction.Order order;
        bool cleared;
        uint8 pStar;
        uint128 fill;
    }

    struct PositionView {
        bytes32 marketId;
        IPolicyManager.Market market;
        IPolicyManager.Position position;
        Settle settle;
        uint256 claimable; // final: payout; void: paid; else 0
    }

    struct UserView {
        address user;
        uint256 usdcBalance;
        uint256 wiBalance;
        uint256 seniorShares;
        uint256 juniorShares;
        uint256 stakedShares;
        uint256 votingPower;
        uint256 marginBalance;
        PoolView pool;
        PolicyView[] policies;
        OrderView[] orders;
        PositionView[] positions;
        uint256[] withdrawRequestIds;
        uint256[] unstakeRequestIds;
    }

    constructor(IERC20 usdc_, PoolVault pool_, PolicyManager pm_, BatchAuction auction_, IOracleAdapter oracle_, WIStaking staking_) {
        (usdc, pool, pm, auction, oracle, staking) = (usdc_, pool_, pm_, auction_, oracle_, staking_);
    }

    function userView(address user) external view returns (UserView memory u) {
        u.user = user;
        u.usdcBalance = usdc.balanceOf(user);
        u.wiBalance = IERC20(staking.wi()).balanceOf(user);
        u.seniorShares = IERC20(pool.seniorShare()).balanceOf(user);
        u.juniorShares = pool.juniorSharesOf(user);
        u.stakedShares = staking.sharesOf(user);
        u.votingPower = staking.votingPower(user);
        u.marginBalance = pm.marginOf(user);
        u.pool = poolView();
        u.policies = policiesOf(user);
        u.orders = ordersOf(user);
        u.positions = positionsOf(user);
        u.withdrawRequestIds = pool.withdrawIdsOf(user);
        u.unstakeRequestIds = staking.unstakeIdsOf(user);
    }

    function poolView() public view returns (PoolView memory v) {
        v.seniorAssets = pool.seniorAssets();
        v.juniorAssets = pool.juniorAssets();
        v.capital = pool.capital();
        v.cash = pool.cash();
        v.reserved = pool.reserved();
        v.deployed = pool.deployed();
        v.seniorSupply = IERC20(pool.seniorShare()).totalSupply();
        v.juniorSupply = pool.totalJuniorShares();
        v.capBps = pool.capBps();
        v.jMinBps = pool.jMinBps();
        v.seniorPremiumBps = pool.seniorPremiumBps();
    }

    function policiesOf(address user) public view returns (PolicyView[] memory out) {
        uint256[] memory ids = pm.policyIdsOf(user);
        out = new PolicyView[](ids.length);
        for (uint256 i; i < ids.length; ++i) {
            PolicyView memory v = out[i];
            v.policyId = ids[i];
            v.policy = pm.getPolicy(ids[i]);
            v.market = pm.getMarket(v.policy.market);
            v.settle = _settle(v.market);
            v.residualOrderId = pm.residualOrderOf(ids[i]);
            uint256 units = v.policy.status == IPolicyManager.PolicyStatus.Bought ? v.policy.units : v.policy.boundUnits;
            v.maxPayout = units * UNIT;
            if (v.settle.finalized && v.policy.status == IPolicyManager.PolicyStatus.Bound) {
                uint256 l = Payoff.L(v.settle.value, v.market.lo, v.market.hi);
                v.payoutIfSettledNow = uint256(v.policy.boundUnits) * (v.policy.isLong ? l : UNIT - l);
            }
        }
    }

    function ordersOf(address user) public view returns (OrderView[] memory out) {
        uint256[] memory ids = auction.orderIdsOf(user);
        out = new OrderView[](ids.length);
        for (uint256 i; i < ids.length; ++i) {
            OrderView memory v = out[i];
            v.orderId = ids[i];
            v.order = auction.getOrder(ids[i]);
            IBatchAuction.Book memory b = auction.getBook(v.order.market);
            v.cleared = b.cleared;
            v.pStar = b.pStar;
            v.fill = auction.fillOf(ids[i]);
        }
    }

    function positionsOf(address user) public view returns (PositionView[] memory out) {
        bytes32[] memory ms = pm.marketsOf(user);
        out = new PositionView[](ms.length);
        for (uint256 i; i < ms.length; ++i) {
            PositionView memory v = out[i];
            v.marketId = ms[i];
            v.market = pm.getMarket(ms[i]);
            v.position = pm.positionOf(ms[i], user);
            v.settle = _settle(v.market);
            if (!v.position.claimed) {
                if (v.settle.voided) {
                    v.claimable = v.position.paid;
                } else if (v.settle.finalized) {
                    v.claimable = Payoff.payout(
                        v.position.longQty, v.position.shortQty, Payoff.L(v.settle.value, v.market.lo, v.market.hi)
                    );
                }
            }
        }
    }

    function _settle(IPolicyManager.Market memory m) internal view returns (Settle memory s) {
        IOracleAdapter.Observation memory o = oracle.observation(m.indexId, m.day);
        (s.posted, s.finalized, s.voided, s.value, s.revision) = (o.posted, o.finalized, o.voided, o.value, o.revision);
    }
}
