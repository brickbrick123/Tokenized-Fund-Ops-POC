// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {InvestorRegistry} from "../src/InvestorRegistry.sol";
import {PermissionedFundToken} from "../src/PermissionedFundToken.sol";

/**
 * @title PermissionedFundTokenTest
 * @notice End-to-end test suite that exercises the core operational lifecycle
 *         of a permissioned tokenized fund:
 *
 *   1. Investor onboarding & wallet whitelisting
 *   2. Subscription → mint
 *   3. Redemption → burn
 *   4. Restricted peer-to-peer transfer
 *   5. Blocked transfer to unapproved wallet
 *   6. Admin pause / unpause
 *   7. Event emission verification
 *
 * Sample investors mirror the off-chain data files:
 *   - North River Family Office
 *   - Elm Street Capital
 *   - Harbor Peak LP
 *   - Juniper Advisory (unapproved — used for negative tests)
 */
contract PermissionedFundTokenTest is Test {
    InvestorRegistry     registry;
    PermissionedFundToken token;

    address admin       = address(0xA001);
    address northRiver  = address(0x1001);
    address elmStreet   = address(0x2001);
    address harborPeak  = address(0x3001);
    address juniper     = address(0x4001); // will NOT be approved

    bytes32 nrId  = keccak256("NORTH_RIVER_FAMILY_OFFICE");
    bytes32 esId  = keccak256("ELM_STREET_CAPITAL");
    bytes32 hpId  = keccak256("HARBOR_PEAK_LP");

    bytes32 sub001 = keccak256("SUB-001");
    bytes32 sub002 = keccak256("SUB-002");
    bytes32 sub003 = keccak256("SUB-003");
    bytes32 red001 = keccak256("RED-001");

    function setUp() public {
        vm.startPrank(admin);

        registry = new InvestorRegistry(admin);
        token    = new PermissionedFundToken(
            "Meridian Institutional Fund I",
            "MIF1",
            admin,
            address(registry)
        );

        // Onboard three investors
        registry.approveInvestor(nrId, "North River Family Office");
        registry.approveInvestor(esId, "Elm Street Capital");
        registry.approveInvestor(hpId, "Harbor Peak LP");

        // Register wallets
        registry.approveWallet(nrId, northRiver);
        registry.approveWallet(esId, elmStreet);
        registry.approveWallet(hpId, harborPeak);

        vm.stopPrank();
    }

    // ─────────────────────────────────────────
    //  Subscription (mint) tests
    // ─────────────────────────────────────────

    function test_subscription_mint() public {
        vm.prank(admin);
        token.mint(northRiver, 500_000000, sub001); // 500 tokens (6 dec)

        assertEq(token.balanceOf(northRiver), 500_000000);
        assertEq(token.totalSupply(), 500_000000);
    }

    function test_mint_emits_subscription_event() public {
        vm.prank(admin);

        vm.expectEmit(true, true, true, true);
        emit PermissionedFundToken.Subscription(northRiver, 500_000000, sub001);

        token.mint(northRiver, 500_000000, sub001);
    }

    function test_mint_emits_transfer_event() public {
        vm.prank(admin);

        vm.expectEmit(true, true, false, true);
        emit PermissionedFundToken.Transfer(address(0), northRiver, 500_000000);

        token.mint(northRiver, 500_000000, sub001);
    }

    function test_mint_to_unapproved_wallet_reverts() public {
        vm.prank(admin);
        vm.expectRevert(
            abi.encodeWithSelector(
                PermissionedFundToken.RecipientNotApproved.selector,
                juniper
            )
        );
        token.mint(juniper, 100_000000, sub003);
    }

    function test_mint_by_non_admin_reverts() public {
        vm.prank(northRiver);
        vm.expectRevert(PermissionedFundToken.OnlyAdmin.selector);
        token.mint(northRiver, 100_000000, sub001);
    }

    // ─────────────────────────────────────────
    //  Redemption (burn) tests
    // ─────────────────────────────────────────

    function test_redemption_burn() public {
        vm.startPrank(admin);
        token.mint(elmStreet, 1000_000000, sub002);
        token.burn(elmStreet, 250_000000, red001);
        vm.stopPrank();

        assertEq(token.balanceOf(elmStreet), 750_000000);
        assertEq(token.totalSupply(), 750_000000);
    }

    function test_burn_emits_redemption_event() public {
        vm.startPrank(admin);
        token.mint(elmStreet, 1000_000000, sub002);

        vm.expectEmit(true, true, true, true);
        emit PermissionedFundToken.Redemption(elmStreet, 250_000000, red001);

        token.burn(elmStreet, 250_000000, red001);
        vm.stopPrank();
    }

    function test_burn_exceeding_balance_reverts() public {
        vm.startPrank(admin);
        token.mint(elmStreet, 100_000000, sub002);

        vm.expectRevert(
            abi.encodeWithSelector(
                PermissionedFundToken.InsufficientBalance.selector,
                elmStreet,
                200_000000,
                100_000000
            )
        );
        token.burn(elmStreet, 200_000000, red001);
        vm.stopPrank();
    }

    // ─────────────────────────────────────────
    //  Transfer restriction tests
    // ─────────────────────────────────────────

    function test_transfer_between_approved_wallets() public {
        vm.prank(admin);
        token.mint(northRiver, 500_000000, sub001);

        vm.prank(northRiver);
        token.transfer(harborPeak, 200_000000);

        assertEq(token.balanceOf(northRiver), 300_000000);
        assertEq(token.balanceOf(harborPeak), 200_000000);
    }

    function test_transfer_to_unapproved_wallet_reverts() public {
        vm.prank(admin);
        token.mint(northRiver, 500_000000, sub001);

        vm.prank(northRiver);
        vm.expectRevert(
            abi.encodeWithSelector(
                PermissionedFundToken.RecipientNotApproved.selector,
                juniper
            )
        );
        token.transfer(juniper, 100_000000);
    }

    function test_transfer_from_unapproved_sender_reverts() public {
        // Juniper somehow has tokens (shouldn't happen, but testing defense)
        vm.prank(juniper);
        vm.expectRevert(
            abi.encodeWithSelector(
                PermissionedFundToken.SenderNotApproved.selector,
                juniper
            )
        );
        token.transfer(northRiver, 1);
    }

    // ─────────────────────────────────────────
    //  Admin approval flow tests
    // ─────────────────────────────────────────

    function test_investor_approval_emits_event() public {
        bytes32 newId = keccak256("NEW_INVESTOR");

        vm.prank(admin);
        vm.expectEmit(true, false, false, true);
        emit InvestorRegistry.InvestorApproved(newId, "New Investor LLC");

        registry.approveInvestor(newId, "New Investor LLC");
    }

    function test_wallet_approval_emits_event() public {
        bytes32 newId = keccak256("NEW_INVESTOR_2");
        address newWallet = address(0x9999);

        vm.startPrank(admin);
        registry.approveInvestor(newId, "New Investor 2");

        vm.expectEmit(true, true, false, true);
        emit InvestorRegistry.WalletApproved(newId, newWallet);

        registry.approveWallet(newId, newWallet);
        vm.stopPrank();
    }

    function test_wallet_for_unapproved_investor_reverts() public {
        bytes32 fakeId = keccak256("NOT_APPROVED");

        vm.prank(admin);
        vm.expectRevert(
            abi.encodeWithSelector(
                InvestorRegistry.InvestorNotApproved.selector,
                fakeId
            )
        );
        registry.approveWallet(fakeId, address(0x8888));
    }

    function test_revoked_wallet_cannot_receive() public {
        vm.startPrank(admin);
        token.mint(northRiver, 500_000000, sub001);

        // Revoke Harbor Peak's wallet
        registry.revokeWallet(hpId, harborPeak);
        vm.stopPrank();

        vm.prank(northRiver);
        vm.expectRevert(
            abi.encodeWithSelector(
                PermissionedFundToken.RecipientNotApproved.selector,
                harborPeak
            )
        );
        token.transfer(harborPeak, 100_000000);
    }

    // ─────────────────────────────────────────
    //  Pause tests
    // ─────────────────────────────────────────

    function test_pause_blocks_mint() public {
        vm.startPrank(admin);
        token.pause();

        vm.expectRevert(PermissionedFundToken.ContractPaused.selector);
        token.mint(northRiver, 100_000000, sub001);
        vm.stopPrank();
    }

    function test_pause_blocks_transfer() public {
        vm.prank(admin);
        token.mint(northRiver, 500_000000, sub001);

        vm.prank(admin);
        token.pause();

        vm.prank(northRiver);
        vm.expectRevert(PermissionedFundToken.ContractPaused.selector);
        token.transfer(elmStreet, 100_000000);
    }

    function test_unpause_restores_operations() public {
        vm.startPrank(admin);
        token.pause();
        token.unpause();
        token.mint(northRiver, 100_000000, sub001);
        vm.stopPrank();

        assertEq(token.balanceOf(northRiver), 100_000000);
    }

    function test_pause_emits_event() public {
        vm.prank(admin);

        vm.expectEmit(true, false, false, true);
        emit PermissionedFundToken.Paused(admin);

        token.pause();
    }
}
