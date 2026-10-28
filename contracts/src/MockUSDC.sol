// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @title MockUSDC
/// @notice 6-decimal stand-in for USDC on anvil / HyperEVM testnet. NOT for mainnet:
///         `mint` is open to anyone so demo wallets can self-fund.
contract MockUSDC is ERC20 {
    constructor() ERC20("Mock USD Coin", "USDC") {}

    function decimals() public pure override returns (uint8) {
        return 6;
    }

    /// @notice Public faucet. Testnet / anvil only.
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}
