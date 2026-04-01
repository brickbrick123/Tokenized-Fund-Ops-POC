// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import {InvestorRegistry} from "../src/InvestorRegistry.sol";
import {PermissionedFundToken} from "../src/PermissionedFundToken.sol";

/**
 * @title Deploy
 * @notice Deploys the InvestorRegistry and PermissionedFundToken, wires them
 *         together, and seeds the registry with sample investors and wallets.
 *
 * Usage (local anvil):
 *   anvil &
 *   forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast
 */
contract Deploy is Script {
    function run() external {
        uint256 deployerKey = vm.envOr("DEPLOYER_PRIVATE_KEY", uint256(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80));
        address deployer    = vm.addr(deployerKey);

        vm.startBroadcast(deployerKey);

        // 1. Deploy registry
        InvestorRegistry registry = new InvestorRegistry(deployer);

        // 2. Deploy fund token, linked to registry
        PermissionedFundToken token = new PermissionedFundToken(
            "Meridian Institutional Fund I",
            "MIF1",
            deployer,
            address(registry)
        );

        // 3. Seed sample investors (mirrors /data/investors.csv)
        bytes32 nrId = keccak256("NORTH_RIVER_FAMILY_OFFICE");
        bytes32 esId = keccak256("ELM_STREET_CAPITAL");
        bytes32 hpId = keccak256("HARBOR_PEAK_LP");

        registry.approveInvestor(nrId, "North River Family Office");
        registry.approveInvestor(esId, "Elm Street Capital");
        registry.approveInvestor(hpId, "Harbor Peak LP");

        // 4. Register wallets (mirrors /data/wallets.csv)
        //    Using deterministic addresses for reproducibility
        address nrWallet = address(0x1001);
        address esWallet = address(0x2001);
        address hpWallet = address(0x3001);

        registry.approveWallet(nrId, nrWallet);
        registry.approveWallet(esId, esWallet);
        registry.approveWallet(hpId, hpWallet);

        vm.stopBroadcast();

        // Log deployment summary
        console.log("=== Deployment Summary ===");
        console.log("Registry:", address(registry));
        console.log("Token:   ", address(token));
        console.log("Admin:   ", deployer);
    }
}
