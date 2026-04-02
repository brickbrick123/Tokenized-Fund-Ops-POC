# Operating a Tokenized Fund: Beyond the Smart Contract

## The Problem

Most blockchain demonstrations stop at the token. They show how to deploy an ERC-20, maybe add a whitelist, and call it "tokenized securities." But issuing a token is not the same as operating a tokenized fund.

In traditional fund administration, a transfer agent maintains investor records, validates subscription and redemption instructions, enforces eligibility rules, reconciles cash movements against share registers, and produces exception reports when things don't match. None of that disappears when the share register moves on-chain. The operational surface area actually increases, because now the books and records exist in two places — on-chain and off-chain — and they must agree.

And there is a second problem on the horizon. The cryptographic signatures that secure blockchain transactions today (ECDSA) will not survive a sufficiently large quantum computer. The question is not whether, but when — and what the operational layer should do about it now.

## What This Repo Demonstrates

**Permissioned issuance.** Tokens can only be minted to wallets belonging to investors who have been explicitly approved after KYC/AML clearance. There is no open minting. The fund admin controls the cap table.

**Transfer restrictions.** Tokens can only move between whitelisted wallets. A transfer to an unapproved address is rejected at the contract level, and the attempt is logged for operational review.

**Subscription and redemption lifecycle.** Minting corresponds to a subscription instruction that has been validated off-chain — cash received, eligibility confirmed, NAV reference established. Burning corresponds to a redemption that has been approved and finalized. Both carry off-chain reference IDs so the on-chain action can be traced back to the originating instruction.

**Post-quantum operational approvals.** Every off-chain authorization — wallet registration, subscription approval, redemption approval — is cryptographically signed using ML-DSA-65, a NIST-standardized post-quantum signature scheme. This creates a quantum-resistant audit trail for the operational layer, independent of on-chain cryptography.

**Daily reconciliation with PQ verification.** A reconciliation engine compares on-chain balances against off-chain expectations, verifies every PQ-signed approval artifact, cross-references signed authorizations against actual on-chain execution, and flags discrepancies by severity. The reconciliation report itself is PQ-signed as a daily attestation.

## Why This Matters

Tokenization at institutional scale is not a smart-contract problem. It is an operations problem with a smart-contract component. The teams building this infrastructure need people who understand:

- That a mint is the end of a subscription workflow, not the beginning.
- That investor records exist in two places and must be reconciled daily.
- That transfer restrictions are a compliance requirement, not a feature toggle.
- That exception management is where most of the operational work happens.
- That the blockchain is an audit trail and enforcement layer, not a replacement for fund administration.
- That quantum threats to on-chain cryptography demand proactive measures at the operational layer, where migration is possible today.

The hybrid post-quantum model demonstrates that you don't need to wait for protocol-level upgrades to start building quantum-resistant infrastructure. The operational layer — approvals, reconciliation, attestation — is entirely within our control.

## What Is Intentionally Simplified

This is a proof-of-concept, not a production system. Specifically:

- The token does not implement ERC-3643 or any formal security-token standard.
- There is no compliance module for jurisdiction rules, holding periods, or investor-count caps.
- NAV calculation, cash settlement, and custody are represented as off-chain data, not automated.
- Admin operations use a single EOA instead of multisig governance.
- The reconciliation reads a JSON snapshot instead of querying a live node.
- PQ keys are stored as local files rather than in an HSM.

These simplifications are deliberate. The goal is to demonstrate operational awareness, workflow design, and forward-looking security architecture — not to ship production infrastructure.
