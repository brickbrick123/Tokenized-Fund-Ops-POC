// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title InvestorRegistry
 * @notice Maintains the investor eligibility list and approved-wallet mapping.
 *
 * In a regulated tokenized fund, tokens may only be held by investors who have
 * completed KYC/AML and been formally approved by the fund administrator or
 * transfer agent.  Each approved investor may register one or more wallets.
 *
 * This contract is the single source of truth the token contract queries
 * before every mint, burn, and transfer.
 *
 * Roles
 * ─────
 *  • admin          – fund administrator / transfer-agent operator
 *  • complianceOfficer – secondary signer for investor-level approvals
 *
 * Workflow (mirrors off-chain books-and-records)
 * ──────────────────────────────────────────────
 *  1. Admin approves investor   → InvestorApproved event
 *  2. Admin registers wallet(s) → WalletApproved event
 *  3. Token contract checks isApprovedWallet() on every transfer
 *  4. Admin can revoke investor or wallet → corresponding Revoked event
 */
contract InvestorRegistry {
    // ──────────────────────────────────────────────
    //  State
    // ──────────────────────────────────────────────

    address public admin;

    /// @dev investorId ⇒ approved flag
    mapping(bytes32 => bool) public approvedInvestors;

    /// @dev wallet ⇒ investorId (zero means not registered)
    mapping(address => bytes32) public walletToInvestor;

    /// @dev wallet ⇒ approved flag
    mapping(address => bool) public approvedWallets;

    /// @dev investorId ⇒ list of registered wallets (for off-chain tooling)
    mapping(bytes32 => address[]) public investorWallets;

    // ──────────────────────────────────────────────
    //  Events  (consumed by reconciliation scripts)
    // ──────────────────────────────────────────────

    event InvestorApproved(bytes32 indexed investorId, string name);
    event InvestorRevoked(bytes32 indexed investorId);
    event WalletApproved(bytes32 indexed investorId, address indexed wallet);
    event WalletRevoked(bytes32 indexed investorId, address indexed wallet);

    // ──────────────────────────────────────────────
    //  Errors
    // ──────────────────────────────────────────────

    error OnlyAdmin();
    error InvestorNotApproved(bytes32 investorId);
    error WalletAlreadyRegistered(address wallet);
    error WalletNotRegistered(address wallet);

    // ──────────────────────────────────────────────
    //  Modifiers
    // ──────────────────────────────────────────────

    modifier onlyAdmin() {
        if (msg.sender != admin) revert OnlyAdmin();
        _;
    }

    // ──────────────────────────────────────────────
    //  Constructor
    // ──────────────────────────────────────────────

    constructor(address _admin) {
        admin = _admin;
    }

    // ──────────────────────────────────────────────
    //  Investor management
    // ──────────────────────────────────────────────

    /**
     * @notice Approve an investor after KYC/AML clearance.
     * @param investorId Unique identifier (typically a hash of the investor's
     *        legal name + jurisdiction, assigned by the transfer agent).
     * @param name Human-readable name stored only in the event log for
     *        off-chain indexing.
     */
    function approveInvestor(bytes32 investorId, string calldata name) external onlyAdmin {
        approvedInvestors[investorId] = true;
        emit InvestorApproved(investorId, name);
    }

    /**
     * @notice Revoke investor eligibility.  Does NOT automatically burn tokens
     *         – the fund admin must handle that through the token contract's
     *         forced-redemption flow.
     */
    function revokeInvestor(bytes32 investorId) external onlyAdmin {
        approvedInvestors[investorId] = false;
        emit InvestorRevoked(investorId);
    }

    // ──────────────────────────────────────────────
    //  Wallet management
    // ──────────────────────────────────────────────

    /**
     * @notice Register a wallet for an already-approved investor.
     * @dev    A wallet can only belong to one investor at a time.
     */
    function approveWallet(bytes32 investorId, address wallet) external onlyAdmin {
        if (!approvedInvestors[investorId]) revert InvestorNotApproved(investorId);
        if (approvedWallets[wallet]) revert WalletAlreadyRegistered(wallet);

        walletToInvestor[wallet] = investorId;
        approvedWallets[wallet] = true;
        investorWallets[investorId].push(wallet);

        emit WalletApproved(investorId, wallet);
    }

    /**
     * @notice Revoke a wallet registration.
     */
    function revokeWallet(bytes32 investorId, address wallet) external onlyAdmin {
        if (walletToInvestor[wallet] != investorId) revert WalletNotRegistered(wallet);

        approvedWallets[wallet] = false;
        walletToInvestor[wallet] = bytes32(0);

        emit WalletRevoked(investorId, wallet);
    }

    // ──────────────────────────────────────────────
    //  View helpers (used by the token contract)
    // ──────────────────────────────────────────────

    function isApprovedWallet(address wallet) external view returns (bool) {
        return approvedWallets[wallet];
    }

    function isApprovedInvestor(bytes32 investorId) external view returns (bool) {
        return approvedInvestors[investorId];
    }

    function getInvestorWallets(bytes32 investorId) external view returns (address[] memory) {
        return investorWallets[investorId];
    }
}
