// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * ATMOSCHAIN — CCTS SmartMarket
 * CarbonCreditToken.sol
 *
 * ERC-20 token representing 1 Carbon Credit = 1 tonne of CO2e avoided.
 * Minted by the ATMOSCHAIN platform when waste is converted/avoided.
 *
 * Token: CarbonCreditToken (CCT)
 *
 * Functions:
 *   mint(address, amount)    — mint new credits (owner only)
 *   retire(amount)           — permanently retire credits (burn)
 *   transfer(to, amount)     — standard ERC-20 transfer
 *   balanceOf(address)       — check credit balance
 *   totalSupply()            — total credits minted
 *
 * Author: ATMOSCHAIN Dev Team
 */

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract CarbonCreditToken is ERC20, Ownable {
    
    // Events for marketplace and audit trail
    event CreditsMinted(address indexed recipient, uint256 amount, string source, uint256 timestamp);
    event CreditsRetired(address indexed holder, uint256 amount, string reason, uint256 timestamp);

    // Credit record: maps token mint operation to metadata
    struct CreditRecord {
        string  source;         // e.g., "WasteVision Detection — plastic bottle"
        uint256 co2e_grams;     // CO2e in grams (integer, avoids decimals)
        uint256 timestamp;
        address minter;
    }

    mapping(uint256 => CreditRecord) public creditRecords;
    uint256 public recordCount;

    // Total credits permanently retired (burned)
    uint256 public totalRetired;

    constructor() ERC20("CarbonCreditToken", "CCT") Ownable(msg.sender) {}

    /**
     * @dev Mint new carbon credit tokens.
     * @param recipient   Address to receive the tokens
     * @param amount      Number of tokens (1 token = 1 tonne CO2e = 10^18 wei)
     * @param source      Description of the carbon reduction project
     * @param co2e_grams  Precise CO2e in grams (for sub-tonne precision)
     */
    function mint(
        address recipient,
        uint256 amount,
        string memory source,
        uint256 co2e_grams
    ) external onlyOwner {
        require(recipient != address(0), "CCT: recipient is zero address");
        require(amount > 0 || co2e_grams > 0, "CCT: cannot mint zero credits");

        _mint(recipient, amount);

        creditRecords[recordCount] = CreditRecord({
            source      : source,
            co2e_grams  : co2e_grams,
            timestamp   : block.timestamp,
            minter      : msg.sender
        });
        recordCount++;

        emit CreditsMinted(recipient, amount, source, block.timestamp);
    }

    /**
     * @dev Permanently retire (burn) carbon credits — removes them from supply.
     * Used when an industry buys credits to offset their emissions.
     * @param amount  Number of tokens to retire
     * @param reason  Reason for retirement (e.g., "IndiGo Q1 2026 offset")
     */
    function retire(uint256 amount, string memory reason) external {
        require(amount > 0, "CCT: cannot retire zero credits");
        require(balanceOf(msg.sender) >= amount, "CCT: insufficient credits to retire");

        _burn(msg.sender, amount);
        totalRetired += amount;

        emit CreditsRetired(msg.sender, amount, reason, block.timestamp);
    }

    /**
     * @dev Get credit record details by record index.
     */
    function getCreditRecord(uint256 index) external view returns (
        string memory source,
        uint256 co2e_grams,
        uint256 timestamp,
        address minter
    ) {
        CreditRecord memory r = creditRecords[index];
        return (r.source, r.co2e_grams, r.timestamp, r.minter);
    }

    /**
     * @dev Returns total circulating supply (minted minus retired).
     */
    function circulatingSupply() external view returns (uint256) {
        return totalSupply();
    }
}
