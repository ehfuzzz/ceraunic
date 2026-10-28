// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @title SeniorShare
/// @notice Senior tranche share of PoolVault (docs/SPEC.md 8.1): ERC-20, 12 decimals, minted,
///         burned and escrowed only by the vault that deploys it.
contract SeniorShare is ERC20 {
    address public immutable vault;

    error OnlyVault();

    constructor() ERC20("weather-insurance senior share", "wiSR") {
        vault = msg.sender;
    }

    modifier onlyVault() {
        if (msg.sender != vault) revert OnlyVault();
        _;
    }

    function decimals() public pure override returns (uint8) {
        return 12;
    }

    function mint(address to, uint256 amount) external onlyVault {
        _mint(to, amount);
    }

    function burn(address from, uint256 amount) external onlyVault {
        _burn(from, amount);
    }

    /// @notice Escrow move for withdrawal requests (no allowance needed; vault only).
    function vaultTransfer(address from, address to, uint256 amount) external onlyVault {
        _transfer(from, to, amount);
    }
}
