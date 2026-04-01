// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {InvestorRegistry} from "./InvestorRegistry.sol";

/**
 * @title PermissionedFundToken
 * @notice ERC-20-compatible token representing fund interests (LP units) in a
 *         tokenized private fund.
 *
 * Key design choices
 * ──────────────────
 *  • Every transfer (including mint and burn) is gated by the InvestorRegistry.
 *  • Minting represents a *subscription* – cash has been received off-chain,
 *    the transfer agent validates the instruction, and tokens are issued.
 *  • Burning represents a *redemption* – the investor requests liquidity,
 *    the fund processes the NAV calculation, and tokens are retired.
 *  • Peer-to-peer transfers are restricted to approved wallets only.
 *  • The contract can be paused (e.g., during NAV strike or fund event).
 *
 * This is NOT a production-grade security-token standard (e.g., ERC-3643).
 * It is a deliberately minimal implementation that demonstrates the
 * operational control surface a transfer agent or fund admin requires.
 *
 * Events are designed to be consumed by off-chain reconciliation tooling.
 */
contract PermissionedFundToken {
    // ──────────────────────────────────────────────
    //  Token metadata
    // ──────────────────────────────────────────────

    string public name;
    string public symbol;
    uint8  public constant decimals = 6; // common for fund-interest tokens

    // ──────────────────────────────────────────────
    //  State
    // ──────────────────────────────────────────────

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    address public admin;               // fund administrator / TA operator
    InvestorRegistry public registry;   // eligibility + wallet whitelist
    bool public paused;                 // operational pause (NAV strike, etc.)

    // ──────────────────────────────────────────────
    //  Events
    // ──────────────────────────────────────────────

    // Standard ERC-20
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    // Fund-operations events (indexed for off-chain reconciliation)
    event Subscription(address indexed investor, uint256 amount, bytes32 indexed subscriptionId);
    event Redemption(address indexed investor, uint256 amount, bytes32 indexed redemptionId);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ──────────────────────────────────────────────
    //  Errors
    // ──────────────────────────────────────────────

    error OnlyAdmin();
    error ContractPaused();
    error RecipientNotApproved(address to);
    error SenderNotApproved(address from);
    error InsufficientBalance(address account, uint256 requested, uint256 available);
    error InsufficientAllowance(address spender, uint256 requested, uint256 available);

    // ──────────────────────────────────────────────
    //  Modifiers
    // ──────────────────────────────────────────────

    modifier onlyAdmin() {
        if (msg.sender != admin) revert OnlyAdmin();
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert ContractPaused();
        _;
    }

    // ──────────────────────────────────────────────
    //  Constructor
    // ──────────────────────────────────────────────

    constructor(
        string memory _name,
        string memory _symbol,
        address _admin,
        address _registry
    ) {
        name     = _name;
        symbol   = _symbol;
        admin    = _admin;
        registry = InvestorRegistry(_registry);
    }

    // ──────────────────────────────────────────────
    //  Subscription (mint)
    // ──────────────────────────────────────────────

    /**
     * @notice Mint tokens to an approved investor wallet after a validated
     *         subscription instruction.  Called by the fund admin / TA once
     *         cash settlement is confirmed off-chain.
     * @param to             Approved wallet of the subscribing investor.
     * @param amount         Number of fund-interest tokens (6 decimals).
     * @param subscriptionId Off-chain reference linking to the subscription
     *                       instruction in the books-and-records system.
     */
    function mint(
        address to,
        uint256 amount,
        bytes32 subscriptionId
    ) external onlyAdmin whenNotPaused {
        if (!registry.isApprovedWallet(to)) revert RecipientNotApproved(to);

        balanceOf[to] += amount;
        totalSupply   += amount;

        emit Transfer(address(0), to, amount);
        emit Subscription(to, amount, subscriptionId);
    }

    // ──────────────────────────────────────────────
    //  Redemption (burn)
    // ──────────────────────────────────────────────

    /**
     * @notice Burn tokens from an investor wallet as part of a validated
     *         redemption.  Called by the fund admin / TA after NAV is struck
     *         and the redemption amount is finalized.
     * @param from           Wallet of the redeeming investor.
     * @param amount         Tokens to burn.
     * @param redemptionId   Off-chain reference for the redemption request.
     */
    function burn(
        address from,
        uint256 amount,
        bytes32 redemptionId
    ) external onlyAdmin whenNotPaused {
        uint256 bal = balanceOf[from];
        if (bal < amount) revert InsufficientBalance(from, amount, bal);

        balanceOf[from] -= amount;
        totalSupply     -= amount;

        emit Transfer(from, address(0), amount);
        emit Redemption(from, amount, redemptionId);
    }

    // ──────────────────────────────────────────────
    //  Restricted transfers
    // ──────────────────────────────────────────────

    /**
     * @notice Transfer tokens between two approved wallets.
     * @dev    Both sender and recipient must be on the whitelist.
     *         In a real deployment, additional compliance checks (holding
     *         period, investor-count caps, jurisdiction rules) would be
     *         layered here or in a separate compliance module.
     */
    function transfer(address to, uint256 amount) external whenNotPaused returns (bool) {
        _requireApproved(msg.sender, to);
        _transfer(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external whenNotPaused returns (bool) {
        _requireApproved(from, to);

        uint256 currentAllowance = allowance[from][msg.sender];
        if (currentAllowance < amount) revert InsufficientAllowance(msg.sender, amount, currentAllowance);
        allowance[from][msg.sender] = currentAllowance - amount;

        _transfer(from, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    // ──────────────────────────────────────────────
    //  Admin controls
    // ──────────────────────────────────────────────

    function pause() external onlyAdmin {
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyAdmin {
        paused = false;
        emit Unpaused(msg.sender);
    }

    // ──────────────────────────────────────────────
    //  Internal helpers
    // ──────────────────────────────────────────────

    function _transfer(address from, address to, uint256 amount) internal {
        uint256 bal = balanceOf[from];
        if (bal < amount) revert InsufficientBalance(from, amount, bal);

        balanceOf[from] -= amount;
        balanceOf[to]   += amount;

        emit Transfer(from, to, amount);
    }

    function _requireApproved(address from, address to) internal view {
        if (!registry.isApprovedWallet(from)) revert SenderNotApproved(from);
        if (!registry.isApprovedWallet(to))   revert RecipientNotApproved(to);
    }
}
