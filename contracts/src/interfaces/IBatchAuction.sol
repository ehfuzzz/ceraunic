// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @title IBatchAuction
/// @notice Open uniform-price call auction per market (keyed by marketId, not station). Open to any
///         wallet. Revised to docs/SPEC.md section 5 (plan 07-01). Signatures and NatSpec only.
/// @dev Ticks 1..99 = cents per scalar unit (1 tick = 1e4 base units, one unit settles to at most
///      1e6). Clearing picks p* maximising min(D, S), then minimising |D - S|, then the lower
///      midpoint (lo + hi) / 2 of the tied tick range; at the marginal tick fills are price-time
///      priority through the per-order `ahead` offset. clear() loops over the 99 ticks only; claim()
///      computes one order's fill in O(1). Everyone pays or receives p*. No cancels. At most
///      MAX_ORDERS (200) non-house orders per market, MAX_ORDERS_PER_TRADER (20) per non-house address,
///      each with escrow >= MIN_ORDER_ESCROW (1 USDC); house orders are exempt. The Python engine (wi.auction.clear) is the reference;
///      parity is asserted on contracts/test/fixtures/auction_cases.json.
///      Escrow: bid qty * (tick * 1e4 + auctionFeePerUnit); offer qty * ((100 - tick) * 1e4 + fee).
interface IBatchAuction {
    struct Order {
        address trader;
        bytes32 market;
        bool isBid; // buys long units
        uint8 tick; // 1..99
        bool claimed;
        uint128 qty;
        uint128 ahead; // qty already queued at (market, side, tick) when placed
    }

    struct Book {
        uint64 houseCutoff; // house address may not place at or after this
        uint64 cutoff; // nobody may place at or after this; clear() allowed from here
        uint16 orderCount;
        bool opened;
        bool cleared;
        uint8 pStar; // 0 if nothing crossed
        uint8 tb; // marginal bid tick
        uint8 to; // marginal offer tick
        uint128 qStar;
        uint128 mb; // units filled at tb
        uint128 mo; // units filled at to
    }

    event BookOpened(bytes32 indexed market, uint64 houseCutoff, uint64 cutoff);
    event OrderPlaced(
        uint256 indexed orderId, bytes32 indexed market, address indexed trader, bool isBid, uint8 tick, uint128 qty, uint128 ahead, uint256 escrow
    );
    event AuctionCleared(bytes32 indexed market, uint8 pStar, uint128 qStar, uint8 tb, uint8 to, uint128 mb, uint128 mo);
    event OrderClaimed(uint256 indexed orderId, uint128 fill, uint256 cost, uint256 fee, uint256 refund);

    /// @notice PolicyManager only, from createMarket(auctioned = true).
    function openBook(bytes32 market, uint64 houseCutoff, uint64 cutoff) external;

    /// @notice Place a limit order, pulling escrow. Reverts: book not open, at/after cutoff, house
    ///         at/after houseCutoff, tick outside 1..99, qty == 0 or qty > MAX_ORDER_QTY (2^64 - 1); non-house only: escrow below
    ///         MIN_ORDER_ESCROW, MAX_ORDERS or MAX_ORDERS_PER_TRADER reached.
    function placeOrder(bytes32 market, bool isBid, uint8 tick, uint128 qty) external returns (uint256 orderId);

    /// @notice Anyone, once, at/after cutoff. Computes (p*, Q*, tb, mb, to, mo) and moves Q* * 1e6
    ///         to PolicyManager.fundMarket. Q* == 0: nothing moves, every order refunds in full.
    function clear(bytes32 market) external;

    /// @notice Anyone, once per order, after clear. Records the fill in PolicyManager and sends
    ///         escrow - cost - fee to the trader; fee to treasury.
    function claim(uint256 orderId) external returns (uint128 fill, uint256 refund);

    /// @notice Fill of an order after clear (0 before). Used by PolicyManager.bind.
    function fillOf(uint256 orderId) external view returns (uint128);

    function getOrder(uint256 orderId) external view returns (Order memory);

    function getBook(bytes32 market) external view returns (Book memory);

    /// @notice The house (pool agent) address subject to houseCutoff.
    function house() external view returns (address);

    function auctionFeePerUnit() external view returns (uint256);
}
