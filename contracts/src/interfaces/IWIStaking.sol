// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @title IWIStaking
/// @notice Staked WI carries governance weight and is cut pro rata (burned, never sold) when the
///         pool's junior ledger loses money on a closed day. docs/SPEC.md section 8.7 (plan 07-01).
///         Signatures and NatSpec only.
/// @dev WI is fixed supply (minted once to the deployer, no mint function). Shares use the same
///      virtual offset as the pool: stake mints mulDiv(amount, totalShares + 1e6, totalStaked + 1);
///      claim pays mulDiv(shares, totalStaked + 1, totalShares + 1e6). A haircut burns
///      mulDiv(totalStaked, bps, 1e4) WI held here, so every position (cooldown included) is cut
///      pro rata in O(1). Stakers earn nothing in v0. WI never pays a claim.
interface IWIStaking {
    struct UnstakeRequest {
        address owner;
        bool claimed;
        uint64 claimableAt; // request time + unstakeCooldown
        uint256 shares; // still counted in totalShares, so still cuttable
    }

    event Staked(address indexed owner, uint256 amount, uint256 shares);
    event UnstakeRequested(uint256 indexed requestId, address indexed owner, uint256 shares, uint64 claimableAt);
    event UnstakeClaimed(uint256 indexed requestId, address indexed owner, uint256 amount);
    event Haircut(uint32 indexed day, uint16 bps, uint256 burned);

    function stake(uint256 amount) external returns (uint256 shares);

    function requestUnstake(uint256 shares) external returns (uint256 requestId);

    function claimUnstake(uint256 requestId) external returns (uint256 amount);

    /// @notice PoolVault only, from closeDay. bps <= haircutCapBps; one call per day.
    function haircut(uint32 day, uint16 bps) external returns (uint256 burned);

    function totalStaked() external view returns (uint256);

    function totalShares() external view returns (uint256);

    function sharesOf(address owner) external view returns (uint256);

    /// @notice Staked amount not in cooldown.
    function votingPower(address owner) external view returns (uint256);

    function unstakeCooldown() external view returns (uint64);

    function haircutCapBps() external view returns (uint16);

    function wi() external view returns (address);
}
