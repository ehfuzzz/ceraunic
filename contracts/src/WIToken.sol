// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ERC20Burnable} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";

/// @title WIToken
/// @notice Fixed-supply governance token (codename "weather-insurance" / "WI"). docs/SPEC.md 8.7:
///         minted once to `to` at construction; there is no mint function. Burnable so WIStaking can
///         burn haircuts. WI never pays a claim; claim-paying money is USDC in PoolVault.
contract WIToken is ERC20, ERC20Burnable {
    constructor(address to, uint256 supply) ERC20("weather-insurance", "WI") {
        _mint(to, supply);
    }
}
