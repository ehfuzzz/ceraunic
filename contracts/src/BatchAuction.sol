// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable, Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {IBatchAuction} from "./interfaces/IBatchAuction.sol";
import {IPolicyManager} from "./interfaces/IPolicyManager.sol";

/// @title BatchAuction
/// @notice Open tick-bucketed uniform-price call auction, one book per market, lazy claims
///         (SPEC section 5; identical rule to wi.auction.clear). clear() is O(99), claim() is O(1).
contract BatchAuction is IBatchAuction, Ownable2Step, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    uint256 public constant TICKS = 99;
    uint256 public constant TICK = 10_000;
    uint256 public constant UNIT = 1_000_000;
    uint16 public constant MAX_ORDERS = 200; // public (non-house) orders per book; house orders are exempt
    uint16 public constant MAX_ORDERS_PER_TRADER = 20; // per (book, non-house address)
    uint256 public constant MIN_ORDER_ESCROW = 1_000_000; // 1 USDC per non-house order
    /// @dev 08-HARDEN #3: with orderCount a uint16, every level sum and Q* stay below 2^16 * 2^64 = 2^80,
    ///      so the uint128 book fields (qStar, mb, mo, level totals) can never truncate.
    uint128 public constant MAX_ORDER_QTY = type(uint64).max;

    IERC20 public immutable usdc;
    IPolicyManager public immutable pm;
    address public treasury;
    address public override house;
    uint256 public override auctionFeePerUnit;

    struct Level {
        uint128 bid;
        uint128 offer;
    }

    mapping(bytes32 => Book) internal _books;
    mapping(bytes32 => uint256) public bookFee; // auctionFeePerUnit snapshot at openBook
    mapping(bytes32 => Level[TICKS + 1]) internal _levels; // index 1..99
    mapping(uint256 => Order) internal _orders;
    mapping(address => uint256[]) internal _orderIdsOf;
    mapping(bytes32 => uint16) public publicOrderCount; // non-house orders in the book (<= MAX_ORDERS)
    mapping(bytes32 => mapping(address => uint16)) public traderOrderCount;
    uint256 public lastOrderId;

    event HouseSet(address house);
    event TreasurySet(address treasury);
    event AuctionFeeSet(uint256 feePerUnit);

    error OnlyPolicyManager();
    error BookExists();
    error BookClosed();
    error HouseClosed();
    error BadOrder();
    error BookFull();
    error TraderOrderCap();
    error BelowMinEscrow();
    error BookOpen();
    error AlreadyCleared();
    error NotCleared();
    error AlreadyClaimed();
    error NoOrder();

    constructor(IERC20 usdc_, IPolicyManager pm_, address treasury_, address house_, address owner_)
        Ownable(owner_)
    {
        usdc = usdc_;
        pm = pm_;
        treasury = treasury_;
        house = house_;
    }

    // ---- admin ----

    function setHouse(address h) external onlyOwner {
        house = h;
        emit HouseSet(h);
    }

    function setTreasury(address t) external onlyOwner {
        treasury = t;
        emit TreasurySet(t);
    }

    /// @notice Applies to books opened afterwards (each book snapshots its fee).
    function setAuctionFeePerUnit(uint256 fee) external onlyOwner {
        auctionFeePerUnit = fee;
        emit AuctionFeeSet(fee);
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    // ---- book ----

    function openBook(bytes32 market, uint64 houseCutoff, uint64 cutoff) external {
        if (msg.sender != address(pm)) revert OnlyPolicyManager();
        Book storage b = _books[market];
        if (b.opened) revert BookExists();
        b.opened = true;
        b.houseCutoff = houseCutoff;
        b.cutoff = cutoff;
        bookFee[market] = auctionFeePerUnit;
        emit BookOpened(market, houseCutoff, cutoff);
    }

    function placeOrder(bytes32 market, bool isBid, uint8 tick, uint128 qty)
        external
        whenNotPaused
        nonReentrant
        returns (uint256 orderId)
    {
        Book storage b = _books[market];
        if (!b.opened || block.timestamp >= b.cutoff) revert BookClosed();
        if (msg.sender == house && block.timestamp >= b.houseCutoff) revert HouseClosed();
        if (tick == 0 || tick > TICKS || qty == 0 || qty > MAX_ORDER_QTY) revert BadOrder();
        uint256 escrow = uint256(qty) * ((isBid ? uint256(tick) : 100 - uint256(tick)) * TICK + bookFee[market]);
        // Cheap fully-refunded orders must not fill the book (08-HARDEN #2): public orders carry a minimum
        // escrow and a per-address cap; the house's residual legs and schedule never compete for slots.
        if (msg.sender != house) {
            if (escrow < MIN_ORDER_ESCROW) revert BelowMinEscrow();
            if (publicOrderCount[market] >= MAX_ORDERS) revert BookFull();
            if (traderOrderCount[market][msg.sender] >= MAX_ORDERS_PER_TRADER) revert TraderOrderCap();
            publicOrderCount[market] += 1;
            traderOrderCount[market][msg.sender] += 1;
        }
        b.orderCount += 1;
        Level storage l = _levels[market][tick];
        uint128 ahead;
        if (isBid) {
            ahead = l.bid;
            l.bid = ahead + qty;
        } else {
            ahead = l.offer;
            l.offer = ahead + qty;
        }
        orderId = ++lastOrderId;
        _orders[orderId] = Order(msg.sender, market, isBid, tick, false, qty, ahead);
        _orderIdsOf[msg.sender].push(orderId);
        usdc.safeTransferFrom(msg.sender, address(this), escrow);
        emit OrderPlaced(orderId, market, msg.sender, isBid, tick, qty, ahead, escrow);
    }

    struct Clearing {
        uint256 pStar;
        uint256 qStar;
        uint256 tb;
        uint256 mb;
        uint256 to;
        uint256 mo;
    }

    function clear(bytes32 market) external nonReentrant {
        Book storage b = _books[market];
        if (!b.opened || block.timestamp < b.cutoff) revert BookOpen();
        if (b.cleared) revert AlreadyCleared();
        b.cleared = true;
        Clearing memory c = _compute(market);
        if (c.qStar == 0) {
            emit AuctionCleared(market, 0, 0, 0, 0, 0, 0);
            return; // nothing crosses: every order refunds in full
        }
        b.pStar = uint8(c.pStar);
        b.qStar = uint128(c.qStar); // < 2^80 by MAX_ORDER_QTY and the uint16 orderCount
        b.tb = uint8(c.tb);
        b.mb = uint128(c.mb);
        b.to = uint8(c.to);
        b.mo = uint128(c.mo);
        emit AuctionCleared(market, uint8(c.pStar), uint128(c.qStar), uint8(c.tb), uint8(c.to), uint128(c.mb), uint128(c.mo));
        usdc.safeTransfer(address(pm), c.qStar * UNIT);
        pm.fundMarket(market, c.qStar * UNIT);
    }

    /// @dev SPEC 5 clearing: scan 1..99; max V = min(D, S), then min |D - S|, then lower midpoint.
    function _compute(bytes32 market) internal view returns (Clearing memory c) {
        uint256[TICKS + 2] memory D; // D[p] = bids at ticks >= p; D[100] = 0
        uint256[TICKS + 1] memory O; // offers at tick p
        Level[TICKS + 1] storage lv = _levels[market];
        for (uint256 p = TICKS; p >= 1; --p) {
            Level memory l = lv[p];
            D[p] = D[p + 1] + l.bid;
            O[p] = l.offer;
        }
        uint256 s;
        uint256 bestV;
        uint256 bestImb = type(uint256).max;
        uint256 lo;
        uint256 hi;
        for (uint256 p = 1; p <= TICKS; ++p) {
            s += O[p];
            uint256 d = D[p];
            uint256 v = d < s ? d : s;
            uint256 imb = d > s ? d - s : s - d;
            if (v > bestV || (v == bestV && v != 0 && imb < bestImb)) {
                (bestV, bestImb, lo, hi) = (v, imb, p, p);
            } else if (v == bestV && v != 0 && imb == bestImb) {
                hi = p;
            }
        }
        if (bestV == 0) return c;
        c.qStar = bestV;
        c.pStar = (lo + hi) / 2;
        uint256 tb = TICKS;
        while (D[tb] < bestV) --tb;
        c.tb = tb;
        c.mb = bestV - D[tb + 1];
        uint256 below;
        uint256 to = 1;
        while (below + O[to] < bestV) {
            below += O[to];
            ++to;
        }
        c.to = to;
        c.mo = bestV - below;
    }

    function claim(uint256 orderId) external nonReentrant returns (uint128 fill, uint256 refund) {
        Order storage o = _orders[orderId];
        if (o.trader == address(0)) revert NoOrder();
        Book storage b = _books[o.market];
        if (!b.cleared) revert NotCleared();
        if (o.claimed) revert AlreadyClaimed();
        o.claimed = true;
        fill = _fill(o, b);
        uint256 feeUnit = bookFee[o.market];
        uint256 escrow = uint256(o.qty) * ((o.isBid ? uint256(o.tick) : 100 - uint256(o.tick)) * TICK + feeUnit);
        uint256 cost = uint256(fill) * (o.isBid ? uint256(b.pStar) : 100 - uint256(b.pStar)) * TICK;
        uint256 fee = uint256(fill) * feeUnit;
        refund = escrow - cost - fee;
        if (fill != 0) pm.recordFill(o.market, o.trader, o.isBid, fill, cost);
        if (fee != 0) usdc.safeTransfer(treasury, fee);
        if (refund != 0) usdc.safeTransfer(o.trader, refund);
        emit OrderClaimed(orderId, fill, cost, fee, refund);
    }

    // ---- views ----

    function fillOf(uint256 orderId) external view returns (uint128) {
        Order storage o = _orders[orderId];
        Book storage b = _books[o.market];
        if (!b.cleared) return 0;
        return _fill(o, b);
    }

    /// @notice Everything PolicyManager.bind needs in one call.
    function bindInfo(uint256 orderId)
        external
        view
        returns (address trader, bytes32 market, uint128 qty, bool cleared, uint128 fill)
    {
        Order storage o = _orders[orderId];
        Book storage b = _books[o.market];
        cleared = b.cleared;
        return (o.trader, o.market, o.qty, cleared, cleared ? _fill(o, b) : 0);
    }

    function getOrder(uint256 orderId) external view returns (Order memory) {
        return _orders[orderId];
    }

    function getBook(bytes32 market) external view returns (Book memory) {
        return _books[market];
    }

    function level(bytes32 market, uint8 tick) external view returns (uint128 bid, uint128 offer) {
        Level memory l = _levels[market][tick];
        return (l.bid, l.offer);
    }

    function orderIdsOf(address trader) external view returns (uint256[] memory) {
        return _orderIdsOf[trader];
    }

    function _fill(Order storage o, Book storage b) internal view returns (uint128) {
        if (b.qStar == 0) return 0;
        if (o.isBid) {
            if (o.tick > b.tb) return o.qty;
            if (o.tick == b.tb) return _slice(b.mb, o.ahead, o.qty);
            return 0;
        }
        if (o.tick < b.to) return o.qty;
        if (o.tick == b.to) return _slice(b.mo, o.ahead, o.qty);
        return 0;
    }

    function _slice(uint128 m, uint128 ahead, uint128 qty) internal pure returns (uint128) {
        if (m <= ahead) return 0;
        uint128 left = m - ahead;
        return left < qty ? left : qty;
    }
}
