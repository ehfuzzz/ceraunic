// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable, Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {IPoolVault} from "./interfaces/IPoolVault.sol";
import {IWIStaking} from "./interfaces/IWIStaking.sol";
import {SeniorShare} from "./SeniorShare.sol";

/// @title PoolVault
/// @notice All claim-paying USDC (SPEC section 8). Internal ledgers only, never balanceOf:
///         capital = seniorAssets + juniorAssets; usdc.balanceOf(this) == capital - deployed.
///         Junior-first waterfall, caps C1/C2, request-then-claim withdrawals, house deployment per
///         day, day close with the WI staking haircut.
contract PoolVault is IPoolVault, Ownable2Step, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    uint256 internal constant BPS = 10_000;
    uint256 internal constant OFFSET = 1e6; // OZ ERC-4626 virtual offset 10**6
    uint256 internal constant DAY = 86_400;
    /// @dev SPEC 17 guard: withdrawDelay and unstakeCooldown >= houseReturnWindow + LEAVE_MARGIN, so a
    ///      leaver is still in the pool (and its stake still cuttable) when a house day is written off.
    uint256 internal constant LEAVE_MARGIN = 2 days;
    /// @notice A matured withdrawal request is claimable for this long, then lapses (SPEC 8.2).
    uint256 public constant CLAIM_WINDOW = 3 days;

    IERC20 public immutable usdc;
    SeniorShare public immutable senior;

    // ---- params ----
    uint16 public capBps = 8000; // C1 u_max
    uint16 public jMinBps = 2000; // C2
    uint16 public seniorPremiumBps = 30;
    uint256 public minJuniorForSenior = 1_000e6;
    uint64 public withdrawDelay;
    uint64 public houseReturnWindow;

    // ---- roles ----
    address public policyManager;
    address public staking;
    address public house;
    mapping(address => bool) public juniorDepositor;

    // ---- ledgers ----
    uint256 public override seniorAssets;
    uint256 public override juniorAssets;
    uint256 public override reserved;
    uint256 public override deployed;
    mapping(uint32 => uint256) public override deployedByDay;
    mapping(uint32 => uint256) public override openPolicies;
    mapping(uint32 => int256) public override dayPnl;
    mapping(uint32 => bool) public houseDone; // returned or written off: no more funding that day
    mapping(uint32 => bool) public dayClosed;

    // ---- junior shares (internal, non-transferable) ----
    mapping(address => uint256) internal _juniorShares;
    uint256 public override totalJuniorShares; // includes shares escrowed in withdraw requests

    // ---- withdrawals ----
    uint256 public nextRequestId;
    mapping(uint256 => WithdrawRequest) internal _requests;
    mapping(address => uint256[]) internal _requestIdsOf;

    event PolicyManagerSet(address pm);
    event StakingSet(address staking);
    event HouseSet(address house);
    event JuniorDepositorSet(address who, bool allowed);
    event ParamsSet(uint16 capBps, uint16 jMinBps, uint16 seniorPremiumBps, uint256 minJuniorForSenior);

    error ExposureCap(); // C1
    error JuniorMinimum(); // C2
    error NoJunior();
    error SeniorClosed();
    error OnlyPolicyManager();
    error OnlyHouse();
    error OnlyJuniorDepositor();
    error LossExceedsRelease();
    error HouseDayDone();
    error TooEarly();
    error NothingDeployed();
    error DayOpen();
    error DayAlreadyClosed();
    error NotClaimable();
    error AlreadyClaimed();
    error InsufficientCash();
    error ZeroAmount();
    error AlreadySet();
    error BadParam();
    error BadWindows();
    error BadDay();
    error ClaimWindowClosed();
    error NotLapsed();
    error NotCancellable();
    error NotRequestOwner();

    constructor(IERC20 usdc_, address owner_, uint64 withdrawDelay_, uint64 houseReturnWindow_) Ownable(owner_) {
        usdc = usdc_;
        senior = new SeniorShare();
        if (uint256(withdrawDelay_) < uint256(houseReturnWindow_) + LEAVE_MARGIN) revert BadWindows();
        withdrawDelay = withdrawDelay_;
        houseReturnWindow = houseReturnWindow_;
    }

    modifier onlyPM() {
        if (msg.sender != policyManager) revert OnlyPolicyManager();
        _;
    }

    modifier onlyHouse() {
        if (msg.sender != house) revert OnlyHouse();
        _;
    }

    // ---- admin ----

    function setPolicyManager(address pm) external onlyOwner {
        if (policyManager != address(0)) revert AlreadySet();
        policyManager = pm;
        emit PolicyManagerSet(pm);
    }

    function setStaking(address s) external onlyOwner {
        if (staking != address(0)) revert AlreadySet();
        if (uint256(IWIStaking(s).unstakeCooldown()) < uint256(houseReturnWindow) + LEAVE_MARGIN) revert BadWindows();
        staking = s;
        emit StakingSet(s);
    }

    function setHouse(address h) external onlyOwner {
        house = h;
        emit HouseSet(h);
    }

    function setJuniorDepositor(address who, bool allowed) external onlyOwner {
        juniorDepositor[who] = allowed;
        emit JuniorDepositorSet(who, allowed);
    }

    function setParams(uint16 capBps_, uint16 jMinBps_, uint16 seniorPremiumBps_, uint256 minJuniorForSenior_)
        external
        onlyOwner
    {
        if (capBps_ > BPS || jMinBps_ > BPS || seniorPremiumBps_ > BPS) revert BadParam();
        (capBps, jMinBps, seniorPremiumBps, minJuniorForSenior) =
            (capBps_, jMinBps_, seniorPremiumBps_, minJuniorForSenior_);
        emit ParamsSet(capBps_, jMinBps_, seniorPremiumBps_, minJuniorForSenior_);
    }

    function setWindows(uint64 withdrawDelay_, uint64 houseReturnWindow_) external onlyOwner {
        uint256 minLeave = uint256(houseReturnWindow_) + LEAVE_MARGIN;
        if (withdrawDelay_ < minLeave) revert BadWindows();
        if (staking != address(0) && IWIStaking(staking).unstakeCooldown() < minLeave) revert BadWindows();
        (withdrawDelay, houseReturnWindow) = (withdrawDelay_, houseReturnWindow_);
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    // ---- LPs ----

    function depositSenior(uint256 assets) external whenNotPaused nonReentrant returns (uint256 shares) {
        if (assets == 0) revert ZeroAmount();
        if (juniorAssets == 0 || juniorAssets < minJuniorForSenior) revert SeniorClosed();
        shares = Math.mulDiv(assets, senior.totalSupply() + OFFSET, seniorAssets + 1);
        if (shares == 0) revert ZeroAmount();
        usdc.safeTransferFrom(msg.sender, address(this), assets);
        seniorAssets += assets;
        _checkC2();
        senior.mint(msg.sender, shares);
        emit Deposited(msg.sender, Tranche.Senior, assets, shares);
    }

    function depositJunior(uint256 assets) external whenNotPaused nonReentrant returns (uint256 shares) {
        if (!juniorDepositor[msg.sender]) revert OnlyJuniorDepositor();
        if (assets == 0) revert ZeroAmount();
        shares = Math.mulDiv(assets, totalJuniorShares + OFFSET, juniorAssets + 1);
        if (shares == 0) revert ZeroAmount();
        usdc.safeTransferFrom(msg.sender, address(this), assets);
        juniorAssets += assets;
        totalJuniorShares += shares;
        _juniorShares[msg.sender] += shares;
        emit Deposited(msg.sender, Tranche.Junior, assets, shares);
    }

    function requestWithdraw(Tranche tranche, uint256 shares) external nonReentrant returns (uint256 requestId) {
        if (shares == 0) revert ZeroAmount();
        if (tranche == Tranche.Senior) {
            senior.vaultTransfer(msg.sender, address(this), shares);
        } else {
            _juniorShares[msg.sender] -= shares; // reverts if short; still counted in totalJuniorShares
        }
        requestId = ++nextRequestId;
        uint64 at = uint64(block.timestamp) + withdrawDelay;
        _requests[requestId] = WithdrawRequest(msg.sender, tranche, false, at, shares);
        _requestIdsOf[msg.sender].push(requestId);
        emit WithdrawRequested(requestId, msg.sender, tranche, shares, at);
    }

    /// @notice Anyone may trigger a matured claim inside [claimableAt, claimableAt + CLAIM_WINDOW); assets go
    ///         to the request owner. `claimed` marks a closed request (claimed, cancelled or lapsed).
    function claimWithdraw(uint256 requestId) external nonReentrant returns (uint256 assets) {
        WithdrawRequest storage r = _requests[requestId];
        if (r.owner == address(0) || block.timestamp < r.claimableAt) revert NotClaimable();
        if (r.claimed) revert AlreadyClaimed();
        if (block.timestamp >= uint256(r.claimableAt) + CLAIM_WINDOW) revert ClaimWindowClosed();
        r.claimed = true;
        if (r.tranche == Tranche.Senior) {
            assets = Math.mulDiv(r.shares, seniorAssets + 1, senior.totalSupply() + OFFSET);
            if (assets > _cash()) revert InsufficientCash();
            seniorAssets -= assets;
            senior.burn(address(this), r.shares);
        } else {
            assets = Math.mulDiv(r.shares, juniorAssets + 1, totalJuniorShares + OFFSET);
            if (assets > _cash()) revert InsufficientCash();
            juniorAssets -= assets;
            totalJuniorShares -= r.shares;
            _checkC2();
        }
        _checkC1();
        if (assets != 0) usdc.safeTransfer(r.owner, assets);
        emit Withdrawn(requestId, r.owner, assets);
    }

    /// @notice Owner only, before maturity: the escrowed shares go back to the owner (08-HARDEN #6).
    function cancelWithdraw(uint256 requestId) external nonReentrant {
        WithdrawRequest storage r = _requests[requestId];
        if (r.owner != msg.sender) revert NotRequestOwner();
        if (r.claimed) revert AlreadyClaimed();
        if (block.timestamp >= r.claimableAt) revert NotCancellable();
        r.claimed = true;
        _returnShares(r);
        emit WithdrawCancelled(requestId, r.owner, r.shares);
    }

    /// @notice Anyone, once the claim window is over: the escrowed shares go back to the owner, so the
    ///         money stays in the tranche and never leaves the pool (08-HARDEN #6).
    function lapseWithdraw(uint256 requestId) external nonReentrant {
        WithdrawRequest storage r = _requests[requestId];
        if (r.owner == address(0)) revert NotClaimable();
        if (r.claimed) revert AlreadyClaimed();
        if (block.timestamp < uint256(r.claimableAt) + CLAIM_WINDOW) revert NotLapsed();
        r.claimed = true;
        _returnShares(r);
        emit WithdrawLapsed(requestId, r.owner, r.shares);
    }

    // ---- PolicyManager ----

    function reserve(uint32 day, uint256 amount) external onlyPM whenNotPaused {
        if (dayClosed[day]) revert DayAlreadyClosed();
        if (juniorAssets == 0) revert NoJunior();
        reserved += amount;
        _checkC1();
        _checkC2();
        openPolicies[day] += 1;
        emit Reserved(day, amount);
    }

    function release(uint32 day, uint256 amount) external onlyPM {
        reserved -= amount;
        emit Released(day, amount);
    }

    /// @dev USDC already transferred in by the PolicyManager.
    function creditPremium(uint32 day, uint256 amount) external onlyPM returns (uint256 s, uint256 j) {
        s = Math.mulDiv(amount, seniorPremiumBps, BPS);
        j = amount - s;
        seniorAssets += s;
        juniorAssets += j;
        dayPnl[day] += int256(j);
        emit PremiumCredited(day, amount, s, j);
    }

    function absorbLoss(uint32 day, uint256 released, uint256 loss, address to) external onlyPM nonReentrant {
        if (loss > released) revert LossExceedsRelease();
        reserved -= released;
        openPolicies[day] -= 1;
        _loss(day, loss);
        if (loss != 0) usdc.safeTransfer(to, loss);
    }

    // ---- house deployment (SPEC 8.6) ----

    function fundHouse(uint32 day, uint256 amount) external onlyHouse whenNotPaused nonReentrant {
        if (houseDone[day] || dayClosed[day]) revert HouseDayDone();
        // Only days near today (08-HARDEN #5): a far-future day could not be written off for years.
        uint256 today = block.timestamp / DAY;
        if (uint256(day) + 1 < today || uint256(day) > today + 2) revert BadDay();
        if (amount == 0) revert ZeroAmount();
        deployedByDay[day] += amount;
        deployed += amount;
        _checkC1();
        _checkC2();
        usdc.safeTransfer(house, amount);
        emit HouseFunded(day, amount);
    }

    function returnFromHouse(uint32 day, uint256 amount) external onlyHouse nonReentrant returns (int256 pnl) {
        if (houseDone[day]) revert HouseDayDone();
        houseDone[day] = true;
        if (amount != 0) usdc.safeTransferFrom(msg.sender, address(this), amount);
        uint256 dep = deployedByDay[day];
        deployedByDay[day] = 0;
        deployed -= dep;
        pnl = int256(amount) - int256(dep);
        if (pnl >= 0) {
            juniorAssets += uint256(pnl);
            dayPnl[day] += pnl;
        } else {
            _loss(day, uint256(-pnl));
        }
        emit HouseReturned(day, amount, dep, pnl);
    }

    function writeOffHouse(uint32 day) external nonReentrant {
        if (block.timestamp < uint256(day) * DAY + houseReturnWindow) revert TooEarly();
        uint256 dep = deployedByDay[day];
        if (dep == 0) revert NothingDeployed();
        houseDone[day] = true;
        deployedByDay[day] = 0;
        deployed -= dep;
        _loss(day, dep);
        emit HouseWrittenOff(day, dep);
    }

    /// @notice Anyone, once per day, after the day's UTC end (so no policy can still be sold on it),
    ///         when no policy is open and nothing is deployed.
    function closeDay(uint32 day) external nonReentrant returns (uint16 haircutBps) {
        if (dayClosed[day]) revert DayAlreadyClosed();
        if (block.timestamp < (uint256(day) + 1) * DAY) revert TooEarly();
        if (openPolicies[day] != 0 || deployedByDay[day] != 0) revert DayOpen();
        dayClosed[day] = true;
        int256 pnl = dayPnl[day];
        if (pnl < 0 && staking != address(0)) {
            uint256 l = uint256(-pnl);
            uint256 bps = Math.mulDiv(l, BPS, juniorAssets + l);
            uint256 cap = IWIStaking(staking).haircutCapBps();
            haircutBps = uint16(bps < cap ? bps : cap);
            if (haircutBps != 0) IWIStaking(staking).haircut(day, haircutBps);
        }
        emit DayClosed(day, pnl, haircutBps);
    }

    // ---- views ----

    function capital() public view returns (uint256) {
        return seniorAssets + juniorAssets;
    }

    function cash() external view returns (uint256) {
        return _cash();
    }

    function juniorSharesOf(address owner_) external view returns (uint256) {
        return _juniorShares[owner_];
    }

    function seniorShare() external view returns (address) {
        return address(senior);
    }

    function getWithdrawRequest(uint256 requestId) external view returns (WithdrawRequest memory) {
        return _requests[requestId];
    }

    function withdrawIdsOf(address owner_) external view returns (uint256[] memory) {
        return _requestIdsOf[owner_];
    }

    // ---- internal ----

    /// @dev Escrowed shares never left the tranche supply, so returning them moves no assets.
    function _returnShares(WithdrawRequest storage r) internal {
        if (r.tranche == Tranche.Senior) senior.vaultTransfer(address(this), r.owner, r.shares);
        else _juniorShares[r.owner] += r.shares;
    }

    function _cash() internal view returns (uint256) {
        return seniorAssets + juniorAssets - deployed;
    }

    /// @dev Junior absorbs first; senior only once junior is 0. dayPnl carries the junior part.
    function _loss(uint32 day, uint256 l) internal {
        uint256 j = l < juniorAssets ? l : juniorAssets;
        juniorAssets -= j;
        seniorAssets -= l - j;
        dayPnl[day] -= int256(j);
        emit LossAbsorbed(day, l, j, l - j);
    }

    function _checkC1() internal view {
        if ((reserved + deployed) * BPS > uint256(capBps) * capital()) revert ExposureCap();
    }

    function _checkC2() internal view {
        if (juniorAssets * BPS < uint256(jMinBps) * capital()) revert JuniorMinimum();
    }
}
