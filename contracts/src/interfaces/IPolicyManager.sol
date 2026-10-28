// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @title IPolicyManager
/// @notice Markets, pool-backed policies (house-signed quotes), strips, auction/RFQ positions and
///         their settlement. Revised to docs/SPEC.md sections 2, 6 and 10 (plan 07-01). Signatures
///         and NatSpec only.
/// @dev One instrument everywhere: a market is (indexId, day, lo, hi) with lo < hi; one scalar unit
///      pays the long L(x) = clamp((x - lo) * 1e6 / (hi - lo), 0, 1e6) USDC base units (division
///      truncates; quotient is positive on the unclamped branch) and the short 1e6 - L(x).
///      marketId = keccak256(abi.encode(bytes32 indexId, uint32 day, int64 lo, int64 hi)).
///      Units: money uint128 USDC base units; index values int64 in the index scale (tenths of degF,
///      hundredths of inch, or -1/0/1); day = uint32 epoch day of the climate date.
///      EIP-712 domain: name "wi-policy", version "1", chainId, verifyingContract = this.
///      Quote type string (exact):
///        Quote(bytes32 market,address buyer,bool isLong,uint128 units,uint128 premium,uint128 fee,uint64 expiry,uint256 nonce)
///      RfqQuote type string (exact):
///        RfqQuote(bytes32 requestId,bytes32 market,address maker,address taker,bool takerLong,uint8 tick,uint128 maxQty,uint64 validUntil,uint256 nonce)
interface IPolicyManager {
    enum PolicyStatus {
        None,
        Bought, // premium escrowed here, reserve taken in the pool
        Bound, // bind() done: kept premium credited to the pool, fee to treasury
        Settled, // paid from the pool (or closed at 0 bound units)
        Voided // index-day void: refunded
    }

    /// @notice Market times are derived at creation from owner-set offsets (SPEC section 4), never
    ///         passed by the caller.
    struct Market {
        bytes32 indexId;
        uint32 day;
        int64 lo;
        int64 hi;
        uint64 saleCutoff; // last second for buyPolicy / strips (exclusive)
        uint64 houseCutoff; // house address stops placing auction orders (exclusive)
        uint64 cutoff; // public auction / RFQ cutoff (exclusive)
        uint64 bindBy; // house-only bind window ends; afterwards anyone binds at full units
        bool auctioned;
        bool exists;
    }

    /// @notice House-signed price for a pool-backed policy. `isLong` = buyer holds the long side
    ///         (calls, digital-above); false = buyer holds the short side (puts, digital-below).
    ///         `fee` (treasury cut, included in `premium`) = notional fee + margin fee (SPEC 6.6).
    struct Quote {
        bytes32 market;
        address buyer;
        bool isLong;
        uint128 units;
        uint128 premium;
        uint128 fee;
        uint64 expiry;
        uint256 nonce;
    }

    struct Policy {
        address buyer;
        bytes32 market;
        bool isLong;
        PolicyStatus status;
        uint128 units;
        uint128 boundUnits;
        uint128 premium;
        uint128 fee;
    }

    /// @notice Auto-renewing daily cover (floating day-ahead price, capped per day).
    struct Strip {
        address owner;
        bytes32 indexId;
        int64 lo;
        int64 hi;
        bool isLong;
        bool open;
        uint32 startDay;
        uint32 endDay;
        uint128 units;
        uint128 maxDailyPremium;
    }

    /// @notice Firm maker quote for a bespoke residual (no last look). Price is a tick in 1..99
    ///         (cents per scalar unit); the taker pays tick*1e4 per unit if long, (100-tick)*1e4 if
    ///         short, the maker's margin balance pays the complement.
    struct RfqQuote {
        bytes32 requestId;
        bytes32 market;
        address maker;
        address taker;
        bool takerLong;
        uint8 tick;
        uint128 maxQty;
        uint64 validUntil;
        uint256 nonce;
    }

    /// @notice Per (market, trader) position from auction fills and RFQ trades. `paid` = sum of
    ///         entry costs, refunded exactly on a void index-day.
    struct Position {
        uint128 longQty;
        uint128 shortQty;
        uint256 paid;
        bool claimed;
    }

    event MarketCreated(
        bytes32 indexed marketId, bytes32 indexed indexId, uint32 indexed day, int64 lo, int64 hi, bool auctioned
    );
    event PolicyBought(
        uint256 indexed policyId,
        bytes32 indexed market,
        address indexed buyer,
        bool isLong,
        uint128 units,
        uint128 premium,
        uint128 fee,
        bytes32 quoteDigest
    );
    event PolicyBound(
        uint256 indexed policyId, uint256 residualOrderId, uint128 boundUnits, uint256 refund, uint256 keptFee, uint256 toPool
    );
    event PolicySettled(uint256 indexed policyId, int64 x, uint256 payout);
    event PolicyVoided(uint256 indexed policyId, uint256 refund);
    event StripOpened(uint256 indexed stripId, address indexed owner, bytes32 indexed indexId);
    event StripClosed(uint256 indexed stripId);
    event MarginDeposited(address indexed maker, uint256 amount);
    event MarginWithdrawn(address indexed maker, uint256 amount);
    event RfqAccepted(
        bytes32 indexed digest, bytes32 indexed market, address indexed taker, address maker, bool takerLong, uint8 tick, uint128 qty
    );
    event PositionSettled(bytes32 indexed market, address indexed trader, uint128 longQty, uint128 shortQty, int64 x, uint256 payout);
    event PositionRefunded(bytes32 indexed market, address indexed trader, uint256 refund);

    // ---- markets ----

    /// @notice Create a market. Owner or house only until the day's houseCutoff; after it, anyone may
    ///         create a non-auctioned market (moves no money). Auctioned markets only by owner or house,
    ///         and they open a book in the BatchAuction. The index
    ///         must be registered and active in the OracleAdapter; lo < hi; reverts if it exists.
    function createMarket(bytes32 indexId, uint32 day, int64 lo, int64 hi, bool auctioned)
        external
        returns (bytes32 marketId);

    function marketIdOf(bytes32 indexId, uint32 day, int64 lo, int64 hi) external pure returns (bytes32);

    function getMarket(bytes32 marketId) external view returns (Market memory);

    // ---- pool-backed policies (house-hedge path; also overlay basis policies) ----

    /// @notice Buy a policy at a quoter-signed Quote. Requires msg.sender == q.buyer,
    ///         block.timestamp <= q.expiry and < market.saleCutoff, unused nonce, signer == quoter,
    ///         q.fee <= q.premium <= q.units * 1e6, q.units >= 1. Escrows the premium here and calls
    ///         pool.reserve(day, units * 1e6) (reverts on the exposure cap or the junior minimum).
    function buyPolicy(Quote calldata q, bytes calldata sig) external returns (uint256 policyId);

    /// @notice Bind a Bought policy after its auction cleared (SPEC 6.3). Before bindBy: house only,
    ///         `residualOrderId` = the house order carrying this policy's residual leg (0 = none);
    ///         the order must be the house's, cleared, same day, and not used for another policy.
    ///         boundUnits = units if residualOrderId == 0 else mulDiv(units, fill, order.qty).
    ///         From bindBy: anyone, residualOrderId must be 0 (full units). Refunds the premium for
    ///         cut units, sends the kept fee to treasury, credits the rest to the pool, releases the
    ///         reserve for cut units (or closes the policy through absorbLoss at 0 bound units).
    ///         Reverts once the index-day is void: the unbound policy then refunds its full premium.
    function bind(uint256 policyId, uint256 residualOrderId) external returns (uint128 boundUnits);

    /// @notice Settle a Bound policy from oracle.getFinal (or refund keptPremium - keptFee if the
    ///         index-day is void; unbound policies on a void day get their escrow back). Once only.
    function settlePolicy(uint256 policyId) external returns (uint256 payout);

    function getPolicy(uint256 policyId) external view returns (Policy memory);

    function quoteDigest(Quote calldata q) external view returns (bytes32);

    // ---- strips ----

    /// @notice Open an auto-renewing strip. The owner keeps a USDC allowance to this contract; each
    ///         day's premium is pulled by buyStripDay.
    function openStrip(
        bytes32 indexId,
        int64 lo,
        int64 hi,
        bool isLong,
        uint128 units,
        uint128 maxDailyPremium,
        uint32 startDay,
        uint32 endDay
    ) external returns (uint256 stripId);

    function closeStrip(uint256 stripId) external;

    /// @notice Quoter only. Buys one day of a strip: q.buyer == strip owner, q.market ==
    ///         marketIdOf(strip.indexId, day, strip.lo, strip.hi) for a day in range, q.isLong ==
    ///         strip.isLong, q.units <= strip.units, q.premium <= strip.maxDailyPremium; then as
    ///         buyPolicy. A day priced above the cap is skipped by the house, never partially filled.
    function buyStripDay(uint256 stripId, Quote calldata q, bytes calldata sig) external returns (uint256 policyId);

    function getStrip(uint256 stripId) external view returns (Strip memory);

    // ---- auction hooks (BatchAuction only) ----

    /// @notice Receives exactly qStar * 1e6 of escrow at clear as the market's collateral.
    function fundMarket(bytes32 market, uint256 amount) external;

    /// @notice Records a claimed fill: long (bid) or short (offer) qty and the entry cost paid.
    function recordFill(bytes32 market, address trader, bool isLong, uint128 qty, uint256 cost) external;

    // ---- RFQ (SPEC 10) ----

    function depositMargin(uint256 amount) external;

    function withdrawMargin(uint256 amount) external;

    /// @notice Invalidate every RfqQuote of msg.sender with nonce < newFloor. Floors only rise.
    function bumpNonceFloor(uint256 newFloor) external;

    /// @notice Taker accepts a firm maker quote for `qty` (partial allowed up to maxQty across
    ///         calls). Requires msg.sender == q.taker, signer == q.maker, maker whitelisted,
    ///         block.timestamp <= q.validUntil and < market.cutoff, q.nonce >= maker's floor.
    ///         Market collateral increases by qty * 1e6.
    function acceptRfq(RfqQuote calldata q, bytes calldata sig, uint128 qty) external;

    function rfqDigest(RfqQuote calldata q) external view returns (bytes32);

    function marginOf(address maker) external view returns (uint256);

    // ---- positions ----

    /// @notice After the index-day is final: pays longQty * L(x) + shortQty * (1e6 - L(x)) to
    ///         msg.sender, once. On a void index-day pays back `paid`.
    function claimPosition(bytes32 market) external returns (uint256 amount);

    function positionOf(bytes32 market, address trader) external view returns (Position memory);

    /// @notice Collateral held for a market = sum of `paid` = 1e6 * total long = 1e6 * total short.
    function marketCollateral(bytes32 market) external view returns (uint256);
}
