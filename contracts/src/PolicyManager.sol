// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable, Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {IPolicyManager} from "./interfaces/IPolicyManager.sol";
import {IPoolVault} from "./interfaces/IPoolVault.sol";
import {IOracleAdapter} from "./interfaces/IOracleAdapter.sol";
import {IBatchAuction} from "./interfaces/IBatchAuction.sol";
import {Payoff} from "./lib/Payoff.sol";
import {BindMath} from "./lib/BindMath.sol";
import {BatchAuction} from "./BatchAuction.sol";
import {OracleAdapter} from "./OracleAdapter.sol";

/// @title PolicyManager
/// @notice Markets, house-quoted pool-backed policies, strips, auction and RFQ positions and their
///         settlement (SPEC sections 2, 4, 6, 10). Policy premiums sit in escrow here until bind();
///         claim-paying money for policies is in PoolVault; position collateral is held here.
contract PolicyManager is IPolicyManager, Ownable2Step, Pausable, ReentrancyGuard, EIP712 {
    using SafeERC20 for IERC20;

    uint256 internal constant UNIT = 1_000_000;
    uint256 internal constant TICK = 10_000;
    uint256 internal constant DAY = 86_400;

    bytes32 public constant QUOTE_TYPEHASH = keccak256(
        "Quote(bytes32 market,address buyer,bool isLong,uint128 units,uint128 premium,uint128 fee,uint64 expiry,uint256 nonce)"
    );
    bytes32 public constant RFQ_TYPEHASH = keccak256(
        "RfqQuote(bytes32 requestId,bytes32 market,address maker,address taker,bool takerLong,uint8 tick,uint128 maxQty,uint64 validUntil,uint256 nonce)"
    );

    IERC20 public immutable usdc;
    IPoolVault public immutable pool;
    IOracleAdapter public immutable oracle;
    IBatchAuction public auction;

    address public quoter;
    address public house;
    address public treasury;
    uint256 public rfqFeePerUnit;

    // Market time offsets after dayStart(D) (SPEC 4): 02:15Z / 02:30Z / 03:00Z / 04:30Z.
    uint32 public saleCutoffOffset = 8100;
    uint32 public houseCutoffOffset = 9000;
    uint32 public cutoffOffset = 10_800;
    uint32 public bindByOffset = 16_200;

    mapping(bytes32 => Market) internal _markets;

    uint256 public lastPolicyId;
    mapping(uint256 => Policy) internal _policies;
    mapping(address => uint256[]) internal _policyIdsOf;
    mapping(uint256 => uint256) public residualOrderOf; // policyId => bound house order (0 = none)
    mapping(uint256 => bool) public orderUsed; // house order already bound to a policy
    mapping(address => mapping(uint256 => uint256)) internal _nonceBits; // signer => word => bits
    uint256 public policyEscrow; // premiums held for Bought (unbound) policies

    uint256 public lastStripId;
    mapping(uint256 => Strip) internal _strips;
    mapping(uint256 => mapping(uint32 => bool)) public stripDayBought;

    mapping(address => bool) public isMaker;
    mapping(address => uint256) internal _margin;
    mapping(address => uint256) public nonceFloor;
    mapping(bytes32 => uint128) public rfqFilled;

    mapping(bytes32 => mapping(address => Position)) internal _positions;
    mapping(bytes32 => uint256) internal _collateral;
    mapping(address => bytes32[]) internal _marketsOf;
    uint256 public totalCollateral;
    uint256 public totalMargin;

    event AuctionSet(address auction);
    event RolesSet(address quoter, address house, address treasury);
    event MakerSet(address maker, bool allowed);
    event OffsetsSet(uint32 sale, uint32 houseCutoff, uint32 cutoff, uint32 bindBy);
    event RfqFeeSet(uint256 feePerUnit);
    event NonceFloorBumped(address indexed maker, uint256 floor);

    error AlreadySet();
    error NotAllowed();
    error BadRange();
    error IndexNotActive();
    error MarketExists();
    error NoMarket();
    error NotBuyer();
    error QuoteExpired();
    error SalesClosed();
    error BadQuote();
    error BadSigner();
    error NonceUsed();
    error NotBought();
    error OnlyHouse();
    error OrderUsed();
    error NotHouseOrder();
    error NotCleared();
    error WrongDay();
    error BindWindowClosed();
    error NotBound();
    error NotSettleable();
    error OnlyAuction();
    error StripClosed_();
    error StripMismatch();
    error StripDayDone();
    error NotMaker();
    error NotTaker();
    error MarketClosed();
    error NonceBelowFloor();
    error AboveMaxQty();
    error InsufficientMargin();
    error AlreadyClaimed();
    error NoPosition();
    error BadOffsets();
    error DayVoid();

    constructor(
        IERC20 usdc_,
        IPoolVault pool_,
        IOracleAdapter oracle_,
        address quoter_,
        address house_,
        address treasury_,
        address owner_
    ) Ownable(owner_) EIP712("wi-policy", "1") {
        usdc = usdc_;
        pool = pool_;
        oracle = oracle_;
        (quoter, house, treasury) = (quoter_, house_, treasury_);
    }

    modifier onlyAuction() {
        if (msg.sender != address(auction)) revert OnlyAuction();
        _;
    }

    // ================================================================ admin

    function setAuction(IBatchAuction a) external onlyOwner {
        if (address(auction) != address(0)) revert AlreadySet();
        auction = a;
        emit AuctionSet(address(a));
    }

    function setRoles(address quoter_, address house_, address treasury_) external onlyOwner {
        (quoter, house, treasury) = (quoter_, house_, treasury_);
        emit RolesSet(quoter_, house_, treasury_);
    }

    function setMaker(address maker, bool allowed) external onlyOwner {
        isMaker[maker] = allowed;
        emit MakerSet(maker, allowed);
    }

    /// @notice Applies to markets created afterwards; a market keeps the times it was created with.
    function setOffsets(uint32 sale, uint32 houseCutoff_, uint32 cutoff_, uint32 bindBy_) external onlyOwner {
        if (!(sale <= houseCutoff_ && houseCutoff_ <= cutoff_ && cutoff_ <= bindBy_ && bindBy_ < DAY)) {
            revert BadOffsets();
        }
        (saleCutoffOffset, houseCutoffOffset, cutoffOffset, bindByOffset) = (sale, houseCutoff_, cutoff_, bindBy_);
        emit OffsetsSet(sale, houseCutoff_, cutoff_, bindBy_);
    }

    function setRfqFeePerUnit(uint256 fee) external onlyOwner {
        rfqFeePerUnit = fee;
        emit RfqFeeSet(fee);
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    // ================================================================ markets

    function createMarket(bytes32 indexId, uint32 day, int64 lo, int64 hi, bool auctioned)
        external
        returns (bytes32 marketId)
    {
        if (lo >= hi) revert BadRange();
        if (!OracleAdapter(address(oracle)).isActive(indexId)) revert IndexNotActive();
        uint64 ds = uint64(day) * uint64(DAY);
        // Owner/house only until the day's house cutoff (then permissionless for non-auctioned markets), so
        // nobody can squat a basis market as non-auctioned before the house opens its book (08-HARDEN #1).
        if (msg.sender != owner() && msg.sender != house) {
            if (auctioned || block.timestamp < ds + houseCutoffOffset) revert NotAllowed();
        }
        marketId = marketIdOf(indexId, day, lo, hi);
        Market storage m = _markets[marketId];
        if (m.exists) revert MarketExists();
        m.indexId = indexId;
        m.day = day;
        m.lo = lo;
        m.hi = hi;
        m.saleCutoff = ds + saleCutoffOffset;
        m.houseCutoff = ds + houseCutoffOffset;
        m.cutoff = ds + cutoffOffset;
        m.bindBy = ds + bindByOffset;
        m.auctioned = auctioned;
        m.exists = true;
        emit MarketCreated(marketId, indexId, day, lo, hi, auctioned);
        if (auctioned) auction.openBook(marketId, m.houseCutoff, m.cutoff);
    }

    function marketIdOf(bytes32 indexId, uint32 day, int64 lo, int64 hi) public pure returns (bytes32) {
        return keccak256(abi.encode(indexId, day, lo, hi));
    }

    function getMarket(bytes32 marketId) external view returns (Market memory) {
        return _markets[marketId];
    }

    // ================================================================ policies

    function buyPolicy(Quote calldata q, bytes calldata sig)
        external
        whenNotPaused
        nonReentrant
        returns (uint256 policyId)
    {
        if (msg.sender != q.buyer) revert NotBuyer();
        return _buy(q, sig, msg.sender);
    }

    function _buy(Quote calldata q, bytes calldata sig, address payer) internal returns (uint256 policyId) {
        Market storage m = _markets[q.market];
        if (!m.exists) revert NoMarket();
        if (block.timestamp > q.expiry) revert QuoteExpired();
        if (block.timestamp >= m.saleCutoff) revert SalesClosed();
        if (q.units == 0 || q.fee > q.premium || uint256(q.premium) > uint256(q.units) * UNIT) revert BadQuote();
        bytes32 digest = _quoteDigest(q);
        address signer = ECDSA.recover(digest, sig);
        if (signer != quoter) revert BadSigner();
        _useNonce(signer, q.nonce);
        policyId = ++lastPolicyId;
        _policies[policyId] = Policy(q.buyer, q.market, q.isLong, PolicyStatus.Bought, q.units, 0, q.premium, q.fee);
        _policyIdsOf[q.buyer].push(policyId);
        policyEscrow += q.premium;
        usdc.safeTransferFrom(payer, address(this), q.premium);
        pool.reserve(m.day, uint256(q.units) * UNIT);
        emit PolicyBought(policyId, q.market, q.buyer, q.isLong, q.units, q.premium, q.fee, digest);
    }

    function bind(uint256 policyId, uint256 residualOrderId) external nonReentrant returns (uint128 boundUnits) {
        Policy storage p = _policies[policyId];
        if (p.status != PolicyStatus.Bought) revert NotBought();
        Market storage m = _markets[p.market];
        // A void day refunds an unbound policy's full premium (settlePolicy); binding it first would keep
        // the fee from the buyer (08-HARDEN #4).
        if (oracle.isVoid(m.indexId, m.day)) revert DayVoid();
        if (block.timestamp < m.bindBy) {
            if (msg.sender != house) revert OnlyHouse();
            if (residualOrderId == 0) {
                boundUnits = p.units;
            } else {
                if (orderUsed[residualOrderId]) revert OrderUsed();
                (address trader, bytes32 om, uint128 qty, bool cleared, uint128 fill) =
                    BatchAuction(address(auction)).bindInfo(residualOrderId);
                if (trader != house) revert NotHouseOrder();
                if (!cleared) revert NotCleared();
                if (_markets[om].day != m.day) revert WrongDay();
                orderUsed[residualOrderId] = true;
                residualOrderOf[policyId] = residualOrderId;
                boundUnits = uint128(BindMath.boundUnits(p.units, fill, qty));
            }
        } else {
            if (residualOrderId != 0) revert BindWindowClosed();
            boundUnits = p.units;
        }
        (, uint256 refund, uint256 keptFee, uint256 toPool) = BindMath.split(p.premium, p.fee, p.units, boundUnits);
        p.boundUnits = boundUnits;
        p.status = boundUnits == 0 ? PolicyStatus.Settled : PolicyStatus.Bound;
        policyEscrow -= p.premium;
        address buyer = p.buyer;
        if (refund != 0) usdc.safeTransfer(buyer, refund);
        if (keptFee != 0) usdc.safeTransfer(treasury, keptFee);
        if (toPool != 0) {
            usdc.safeTransfer(address(pool), toPool);
            pool.creditPremium(m.day, toPool);
        }
        if (boundUnits != 0) {
            if (boundUnits < p.units) pool.release(m.day, uint256(p.units - boundUnits) * UNIT);
        } else {
            pool.absorbLoss(m.day, uint256(p.units) * UNIT, 0, buyer);
        }
        emit PolicyBound(policyId, residualOrderId, boundUnits, refund, keptFee, toPool);
    }

    function settlePolicy(uint256 policyId) external nonReentrant returns (uint256 payout) {
        Policy storage p = _policies[policyId];
        Market storage m = _markets[p.market];
        PolicyStatus st = p.status;
        if (st != PolicyStatus.Bought && st != PolicyStatus.Bound) revert NotSettleable();
        bool isVoid_ = oracle.isVoid(m.indexId, m.day);
        if (st == PolicyStatus.Bought) {
            // Unbound: only a void day can close it here (anyone may bind after bindBy).
            if (!isVoid_) revert NotBound();
            p.status = PolicyStatus.Voided;
            payout = p.premium;
            policyEscrow -= payout;
            pool.absorbLoss(m.day, uint256(p.units) * UNIT, 0, p.buyer);
            usdc.safeTransfer(p.buyer, payout);
            emit PolicyVoided(policyId, payout);
            return payout;
        }
        uint256 released = uint256(p.boundUnits) * UNIT;
        if (isVoid_) {
            (,,, payout) = BindMath.split(p.premium, p.fee, p.units, p.boundUnits); // keptPremium - keptFee
            p.status = PolicyStatus.Voided;
            pool.absorbLoss(m.day, released, payout, p.buyer);
            emit PolicyVoided(policyId, payout);
        } else {
            int64 x = oracle.getFinal(m.indexId, m.day);
            uint256 l = Payoff.L(x, m.lo, m.hi);
            payout = uint256(p.boundUnits) * (p.isLong ? l : UNIT - l);
            p.status = PolicyStatus.Settled;
            pool.absorbLoss(m.day, released, payout, p.buyer);
            emit PolicySettled(policyId, x, payout);
        }
    }

    function getPolicy(uint256 policyId) external view returns (Policy memory) {
        return _policies[policyId];
    }

    function policyIdsOf(address buyer) external view returns (uint256[] memory) {
        return _policyIdsOf[buyer];
    }

    function quoteDigest(Quote calldata q) external view returns (bytes32) {
        return _quoteDigest(q);
    }

    function nonceUsed(address signer, uint256 nonce) external view returns (bool) {
        return _nonceBits[signer][nonce >> 8] & (1 << (nonce & 0xff)) != 0;
    }

    // ================================================================ strips

    function openStrip(
        bytes32 indexId,
        int64 lo,
        int64 hi,
        bool isLong,
        uint128 units,
        uint128 maxDailyPremium,
        uint32 startDay,
        uint32 endDay
    ) external whenNotPaused returns (uint256 stripId) {
        if (lo >= hi || units == 0 || startDay > endDay) revert BadRange();
        stripId = ++lastStripId;
        _strips[stripId] = Strip(msg.sender, indexId, lo, hi, isLong, true, startDay, endDay, units, maxDailyPremium);
        emit StripOpened(stripId, msg.sender, indexId);
    }

    function closeStrip(uint256 stripId) external {
        Strip storage s = _strips[stripId];
        if (msg.sender != s.owner) revert NotAllowed();
        s.open = false;
        emit StripClosed(stripId);
    }

    function buyStripDay(uint256 stripId, Quote calldata q, bytes calldata sig)
        external
        whenNotPaused
        nonReentrant
        returns (uint256 policyId)
    {
        if (msg.sender != quoter) revert NotAllowed();
        Strip storage s = _strips[stripId];
        if (!s.open) revert StripClosed_();
        Market storage m = _markets[q.market];
        if (
            q.buyer != s.owner || !m.exists || m.indexId != s.indexId || m.lo != s.lo || m.hi != s.hi
                || m.day < s.startDay || m.day > s.endDay || q.isLong != s.isLong || q.units > s.units
                || q.premium > s.maxDailyPremium
        ) revert StripMismatch();
        if (stripDayBought[stripId][m.day]) revert StripDayDone();
        stripDayBought[stripId][m.day] = true;
        return _buy(q, sig, s.owner);
    }

    function getStrip(uint256 stripId) external view returns (Strip memory) {
        return _strips[stripId];
    }

    // ================================================================ auction hooks

    function fundMarket(bytes32 market, uint256 amount) external onlyAuction {
        _collateral[market] += amount;
        totalCollateral += amount;
    }

    /// @dev A fill claimed after the trader already claimed the position is paid out at once
    ///      (otherwise it would be stranded as collateral).
    function recordFill(bytes32 market, address trader, bool isLong, uint128 qty, uint256 cost) external onlyAuction {
        Position storage pos = _positions[market][trader];
        if (pos.claimed) {
            Market storage m = _markets[market];
            uint256 amount;
            if (oracle.isVoid(m.indexId, m.day)) {
                amount = cost;
                emit PositionRefunded(market, trader, amount);
            } else {
                int64 x = oracle.getFinal(m.indexId, m.day);
                uint256 l = Payoff.L(x, m.lo, m.hi);
                amount = uint256(qty) * (isLong ? l : UNIT - l);
                emit PositionSettled(market, trader, isLong ? qty : 0, isLong ? 0 : qty, x, amount);
            }
            _payOut(market, trader, amount);
            return;
        }
        _addPosition(market, trader, isLong, qty, cost);
    }

    // ================================================================ RFQ

    function depositMargin(uint256 amount) external nonReentrant {
        _margin[msg.sender] += amount;
        totalMargin += amount;
        usdc.safeTransferFrom(msg.sender, address(this), amount);
        emit MarginDeposited(msg.sender, amount);
    }

    function withdrawMargin(uint256 amount) external nonReentrant {
        _margin[msg.sender] -= amount;
        totalMargin -= amount;
        usdc.safeTransfer(msg.sender, amount);
        emit MarginWithdrawn(msg.sender, amount);
    }

    function bumpNonceFloor(uint256 newFloor) external {
        if (newFloor <= nonceFloor[msg.sender]) revert BadQuote();
        nonceFloor[msg.sender] = newFloor;
        emit NonceFloorBumped(msg.sender, newFloor);
    }

    function acceptRfq(RfqQuote calldata q, bytes calldata sig, uint128 qty) external whenNotPaused nonReentrant {
        if (msg.sender != q.taker) revert NotTaker();
        if (!isMaker[q.maker]) revert NotMaker();
        bytes32 digest = _rfqDigest(q);
        if (ECDSA.recover(digest, sig) != q.maker) revert BadSigner();
        if (block.timestamp > q.validUntil) revert QuoteExpired();
        Market storage m = _markets[q.market];
        if (!m.exists) revert NoMarket();
        if (block.timestamp >= m.cutoff) revert MarketClosed();
        if (q.nonce < nonceFloor[q.maker]) revert NonceBelowFloor();
        if (q.tick == 0 || q.tick > 99 || qty == 0) revert BadQuote();
        if (uint256(rfqFilled[digest]) + qty > q.maxQty) revert AboveMaxQty();
        rfqFilled[digest] += qty;
        uint256 takerCost = uint256(qty) * (q.takerLong ? uint256(q.tick) : 100 - uint256(q.tick)) * TICK;
        uint256 makerCost = uint256(qty) * UNIT - takerCost;
        if (_margin[q.maker] < makerCost) revert InsufficientMargin();
        _margin[q.maker] -= makerCost;
        totalMargin -= makerCost;
        _collateral[q.market] += uint256(qty) * UNIT;
        totalCollateral += uint256(qty) * UNIT;
        _addPosition(q.market, q.taker, q.takerLong, qty, takerCost);
        _addPosition(q.market, q.maker, !q.takerLong, qty, makerCost);
        uint256 fee = uint256(qty) * rfqFeePerUnit;
        usdc.safeTransferFrom(msg.sender, address(this), takerCost + fee);
        if (fee != 0) usdc.safeTransfer(treasury, fee);
        emit RfqAccepted(digest, q.market, q.taker, q.maker, q.takerLong, q.tick, qty);
    }

    function rfqDigest(RfqQuote calldata q) external view returns (bytes32) {
        return _rfqDigest(q);
    }

    function marginOf(address maker) external view returns (uint256) {
        return _margin[maker];
    }

    // ================================================================ positions

    function claimPosition(bytes32 market) external nonReentrant returns (uint256 amount) {
        Position storage pos = _positions[market][msg.sender];
        if (pos.claimed) revert AlreadyClaimed();
        if (pos.longQty == 0 && pos.shortQty == 0) revert NoPosition();
        Market storage m = _markets[market];
        pos.claimed = true;
        if (oracle.isVoid(m.indexId, m.day)) {
            amount = pos.paid;
            emit PositionRefunded(market, msg.sender, amount);
        } else {
            int64 x = oracle.getFinal(m.indexId, m.day);
            amount = Payoff.payout(pos.longQty, pos.shortQty, Payoff.L(x, m.lo, m.hi));
            emit PositionSettled(market, msg.sender, pos.longQty, pos.shortQty, x, amount);
        }
        _payOut(market, msg.sender, amount);
    }

    function positionOf(bytes32 market, address trader) external view returns (Position memory) {
        return _positions[market][trader];
    }

    function marketCollateral(bytes32 market) external view returns (uint256) {
        return _collateral[market];
    }

    function marketsOf(address trader) external view returns (bytes32[] memory) {
        return _marketsOf[trader];
    }

    // ================================================================ internal

    function _addPosition(bytes32 market, address trader, bool isLong, uint128 qty, uint256 cost) internal {
        Position storage pos = _positions[market][trader];
        if (pos.longQty == 0 && pos.shortQty == 0) _marketsOf[trader].push(market);
        if (isLong) pos.longQty += qty;
        else pos.shortQty += qty;
        pos.paid += cost;
    }

    /// @dev Per-market underflow reverts: no market can pay out more than it was funded with.
    function _payOut(bytes32 market, address to, uint256 amount) internal {
        _collateral[market] -= amount;
        totalCollateral -= amount;
        if (amount != 0) usdc.safeTransfer(to, amount);
    }

    function _useNonce(address signer, uint256 nonce) internal {
        uint256 bit = 1 << (nonce & 0xff);
        uint256 word = _nonceBits[signer][nonce >> 8];
        if (word & bit != 0) revert NonceUsed();
        _nonceBits[signer][nonce >> 8] = word | bit;
    }

    function _quoteDigest(Quote calldata q) internal view returns (bytes32) {
        return _hashTypedDataV4(
            keccak256(
                abi.encode(QUOTE_TYPEHASH, q.market, q.buyer, q.isLong, q.units, q.premium, q.fee, q.expiry, q.nonce)
            )
        );
    }

    function _rfqDigest(RfqQuote calldata q) internal view returns (bytes32) {
        return _hashTypedDataV4(
            keccak256(
                abi.encode(
                    RFQ_TYPEHASH,
                    q.requestId,
                    q.market,
                    q.maker,
                    q.taker,
                    q.takerLong,
                    q.tick,
                    q.maxQty,
                    q.validUntil,
                    q.nonce
                )
            )
        );
    }
}
