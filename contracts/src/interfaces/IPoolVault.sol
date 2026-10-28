// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @title IPoolVault
/// @notice One vault holding all claim-paying USDC, with a senior ledger (outside LPs, SeniorShare
///         ERC-20, decimals 12) and a junior ledger (protocol-owned, internal non-transferable
///         shares; v0 deposits from juniorDepositor addresses only). Revised to docs/SPEC.md
///         section 8 (plan 07-01). Signatures and NatSpec only.
/// @dev Ledgers, never balanceOf: capital = seniorAssets + juniorAssets;
///      usdc.balanceOf(this) == capital - deployed (absent donations).
///      Shares (OZ ERC-4626 virtual offset 1e6): mint mulDiv(assets, supply + 1e6, trancheAssets + 1),
///      redeem mulDiv(shares, trancheAssets + 1, supply + 1e6), both floor.
///      Caps: C1 (reserved + deployed) * 1e4 <= capBps * capital on reserve / fundHouse / withdraw
///      claim; C2 juniorAssets * 1e4 >= jMinBps * capital for new risk, senior deposits and junior
///      withdrawals. Losses hit junior first; senior only once junior is 0. Premium is split by
///      seniorPremiumBps; junior gets the rest and all hedge P&L. Per-day books (dayPnl,
///      openPolicies, deployedByDay) drive closeDay and the WI staking haircut.
interface IPoolVault {
    enum Tranche {
        Senior,
        Junior
    }

    struct WithdrawRequest {
        address owner;
        Tranche tranche;
        bool claimed; // closed: claimed, cancelled (before claimableAt) or lapsed (claim window over)
        uint64 claimableAt; // request time + withdrawDelay; claimable until claimableAt + CLAIM_WINDOW (3 d)
        uint256 shares; // escrowed at request, burned at claim at claim-time NAV
    }

    event Deposited(address indexed owner, Tranche indexed tranche, uint256 assets, uint256 shares);
    event WithdrawRequested(uint256 indexed requestId, address indexed owner, Tranche tranche, uint256 shares, uint64 claimableAt);
    event Withdrawn(uint256 indexed requestId, address indexed owner, uint256 assets);
    event WithdrawCancelled(uint256 indexed requestId, address indexed owner, uint256 shares);
    event WithdrawLapsed(uint256 indexed requestId, address indexed owner, uint256 shares);
    event Reserved(uint32 indexed day, uint256 amount);
    event Released(uint32 indexed day, uint256 amount);
    event PremiumCredited(uint32 indexed day, uint256 amount, uint256 senior, uint256 junior);
    event LossAbsorbed(uint32 indexed day, uint256 loss, uint256 juniorHit, uint256 seniorHit);
    event HouseFunded(uint32 indexed day, uint256 amount);
    event HouseReturned(uint32 indexed day, uint256 amount, uint256 deployed, int256 pnl);
    event HouseWrittenOff(uint32 indexed day, uint256 deployed);
    event DayClosed(uint32 indexed day, int256 juniorPnl, uint16 haircutBps);

    // ---- LPs ----

    function depositSenior(uint256 assets) external returns (uint256 shares);

    /// @notice juniorDepositor only (v0: owner / house).
    function depositJunior(uint256 assets) external returns (uint256 shares);

    function requestWithdraw(Tranche tranche, uint256 shares) external returns (uint256 requestId);

    /// @notice In [claimableAt, claimableAt + 3 days). Pays from cash at claim-time NAV; reverts if C1
    ///         or (junior) C2 would break afterwards.
    function claimWithdraw(uint256 requestId) external returns (uint256 assets);

    /// @notice Request owner, before claimableAt: the escrowed shares go back to the owner.
    function cancelWithdraw(uint256 requestId) external;

    /// @notice Anyone, from claimableAt + 3 days: an unclaimed request lapses and its escrowed shares go
    ///         back to the owner (the money never leaves the pool).
    function lapseWithdraw(uint256 requestId) external;

    // ---- PolicyManager only ----

    /// @notice Reserve a policy's max payout for `day`; checks C1 and C2; openPolicies[day] += 1.
    function reserve(uint32 day, uint256 amount) external;

    /// @notice Release reserve for downsized units (no change to openPolicies).
    function release(uint32 day, uint256 amount) external;

    /// @notice Credit kept premium (USDC already transferred in). senior = amount * seniorPremiumBps
    ///         / 1e4 (floor), junior = rest; dayPnl[day] += junior.
    function creditPremium(uint32 day, uint256 amount) external returns (uint256 senior, uint256 junior);

    /// @notice Close one policy: reserved -= released; pay `loss` (<= released) to `to`, junior
    ///         first; dayPnl[day] -= junior hit; openPolicies[day] -= 1.
    function absorbLoss(uint32 day, uint256 released, uint256 loss, address to) external;

    // ---- house (pool agent) deployment, SPEC 8.6 ----

    /// @notice House only. Cash to the house wallet for day `day`'s hedges; deployedByDay += amount;
    ///         C1 and C2 apply. `day` must lie in [today - 1, today + 2] (today = block.timestamp / 1 days).
    function fundHouse(uint32 day, uint256 amount) external;

    /// @notice House only, once per day. Pulls `amount` from the caller and closes the day's
    ///         deployment: pnl = amount - deployedByDay[day]; gain to junior, loss junior first.
    function returnFromHouse(uint32 day, uint256 amount) external returns (int256 pnl);

    /// @notice Anyone, after dayStart(day) + houseReturnWindow: books unreturned deployment as a
    ///         junior-first loss.
    function writeOffHouse(uint32 day) external;

    /// @notice Anyone, once, when openPolicies[day] == 0 and deployedByDay[day] == 0. If dayPnl < 0
    ///         calls WIStaking.haircut(day, min(mulDiv(l, 1e4, juniorAssets + l), haircutCapBps)).
    function closeDay(uint32 day) external returns (uint16 haircutBps);

    // ---- views ----

    function seniorAssets() external view returns (uint256);

    function juniorAssets() external view returns (uint256);

    function capital() external view returns (uint256);

    function reserved() external view returns (uint256);

    function deployed() external view returns (uint256);

    function deployedByDay(uint32 day) external view returns (uint256);

    function openPolicies(uint32 day) external view returns (uint256);

    function dayPnl(uint32 day) external view returns (int256);

    function juniorSharesOf(address owner) external view returns (uint256);

    function totalJuniorShares() external view returns (uint256);

    function seniorShare() external view returns (address);

    function getWithdrawRequest(uint256 requestId) external view returns (WithdrawRequest memory);
}
