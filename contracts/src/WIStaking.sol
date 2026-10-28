// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ERC20Burnable} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import {Ownable, Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {IWIStaking} from "./interfaces/IWIStaking.sol";

interface IHouseReturnWindow {
    function houseReturnWindow() external view returns (uint64);
}

/// @title WIStaking
/// @notice Staked WI = governance weight, cut pro rata (burned) when the junior ledger loses money
///         on a closed day (SPEC 8.7). Shares carry the pool's virtual offset; a haircut lowers
///         totalStaked, so every position, cooldown included, is cut in O(1). Stakers earn nothing.
contract WIStaking is IWIStaking, Ownable2Step, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    uint256 internal constant BPS = 10_000;
    uint256 internal constant OFFSET = 1e6;

    address public immutable override wi;
    address public pool;
    uint64 public override unstakeCooldown;
    uint16 public override haircutCapBps = 3000;

    uint256 public override totalStaked;
    uint256 public override totalShares; // includes shares in cooldown
    mapping(address => uint256) public override sharesOf; // not in cooldown
    mapping(uint32 => bool) public haircutDone;
    uint256 public totalBurned;

    uint256 public nextRequestId;
    mapping(uint256 => UnstakeRequest) internal _requests;
    mapping(address => uint256[]) internal _requestIdsOf;

    error OnlyPool();
    error AlreadySet();
    error ZeroAmount();
    error AboveCap();
    error HaircutDone();
    error NotClaimable();
    error AlreadyClaimed();
    error BadParam();
    error BadWindows();

    constructor(address wi_, address owner_, uint64 unstakeCooldown_) Ownable(owner_) {
        wi = wi_;
        unstakeCooldown = unstakeCooldown_;
    }

    function setPool(address pool_) external onlyOwner {
        if (pool != address(0)) revert AlreadySet();
        pool = pool_;
    }

    function setHaircutCapBps(uint16 bps) external onlyOwner {
        if (bps > BPS) revert BadParam();
        haircutCapBps = bps;
    }

    /// @notice SPEC 17 guard: once the pool is set, the cooldown stays >= its houseReturnWindow + 2 days.
    function setUnstakeCooldown(uint64 s) external onlyOwner {
        if (pool != address(0) && uint256(s) < uint256(IHouseReturnWindow(pool).houseReturnWindow()) + 2 days) {
            revert BadWindows();
        }
        unstakeCooldown = s;
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    function stake(uint256 amount) external whenNotPaused nonReentrant returns (uint256 shares) {
        if (amount == 0) revert ZeroAmount();
        shares = Math.mulDiv(amount, totalShares + OFFSET, totalStaked + 1);
        if (shares == 0) revert ZeroAmount();
        IERC20(wi).safeTransferFrom(msg.sender, address(this), amount);
        totalStaked += amount;
        totalShares += shares;
        sharesOf[msg.sender] += shares;
        emit Staked(msg.sender, amount, shares);
    }

    function requestUnstake(uint256 shares) external nonReentrant returns (uint256 requestId) {
        if (shares == 0) revert ZeroAmount();
        sharesOf[msg.sender] -= shares; // stays in totalShares: still cuttable
        requestId = ++nextRequestId;
        uint64 at = uint64(block.timestamp) + unstakeCooldown;
        _requests[requestId] = UnstakeRequest(msg.sender, false, at, shares);
        _requestIdsOf[msg.sender].push(requestId);
        emit UnstakeRequested(requestId, msg.sender, shares, at);
    }

    function claimUnstake(uint256 requestId) external nonReentrant returns (uint256 amount) {
        UnstakeRequest storage r = _requests[requestId];
        if (r.owner == address(0) || block.timestamp < r.claimableAt) revert NotClaimable();
        if (r.claimed) revert AlreadyClaimed();
        r.claimed = true;
        amount = Math.mulDiv(r.shares, totalStaked + 1, totalShares + OFFSET);
        totalStaked -= amount;
        totalShares -= r.shares;
        if (amount != 0) IERC20(wi).safeTransfer(r.owner, amount);
        emit UnstakeClaimed(requestId, r.owner, amount);
    }

    function haircut(uint32 day, uint16 bps) external nonReentrant returns (uint256 burned) {
        if (msg.sender != pool) revert OnlyPool();
        if (bps > haircutCapBps) revert AboveCap();
        if (haircutDone[day]) revert HaircutDone();
        haircutDone[day] = true;
        burned = Math.mulDiv(totalStaked, bps, BPS);
        totalStaked -= burned;
        totalBurned += burned;
        if (burned != 0) ERC20Burnable(wi).burn(burned);
        emit Haircut(day, bps, burned);
    }

    function votingPower(address owner_) external view returns (uint256) {
        return Math.mulDiv(sharesOf[owner_], totalStaked + 1, totalShares + OFFSET);
    }

    function getUnstakeRequest(uint256 requestId) external view returns (UnstakeRequest memory) {
        return _requests[requestId];
    }

    function unstakeIdsOf(address owner_) external view returns (uint256[] memory) {
        return _requestIdsOf[owner_];
    }
}
