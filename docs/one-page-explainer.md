# Operating a Tokenized Fund: Beyond the Smart Contract

## The Problem

Most blockchain demonstrations stop at the token. They show how to deploy an ERC-20, maybe add a whitelist, and call it "tokenized securities." But issuing a token is not the same as operating a tokenized fund.

In traditional fund administration, a transfer agent maintains investor records, validates subscription and redemption instructions, enforces eligibility rules, reconciles cash movements against share registers, and produces exception reports when things don't match. None of that disappears when the share register moves on-chain. The operational surface area actually increases, because now the books and records exist in two places — on-chain and off-chain — and they must agree.

## What This Repo Demonstrates

This project models a miniature version of that operational reality:

**Permissioned issuance.** Tokens can only be minted to wallets belonging to investors who have been explicitly approved after KYC/AML clearance. There is no open minting. The fund admin controls the cap table.

**Transfer restrictions.** Tokens can only move between whitelisted wallets. A transfer to an unapproved address is rejected at the contract level, and the attempt is logged for operational review.

**Subscription and redemption lifecycle.** Minting corresponds to a subscription instruction that has been validated off-chain — cash received, eligibility confirmed, NAV reference established. Burning corresponds to a redemption that has been approved and finalized. Both carry off-chain reference IDs so the on-chain action can be traced back to the originating instruction.

**Off-chain books and records.** The project includes sample investor master files, wallet registries, subscription logs, redemption logs, and expected balances — the kind of data a transfer agent or fund administrator maintains in parallel with the blockchain.

**Daily reconciliation.** A script compares on-chain balances against off-chain expected balances and produces an exception report. Breaks are categorized: pending subscription not yet minted, redemption queued but not burned, stale off-chain ledger, blocked transfer attempt. Each break includes a recommended next action.

## Why This Matters

Tokenization at institutional scale is not a smart-contract problem. It is an operations problem with a smart-contract component. The teams building this infrastructure need people who understand:

- That a mint is the end of a subscription workflow, not the beginning.
- That investor records exist in two places and must be reconciled daily.
- That transfer restrictions are a compliance requirement, not a feature toggle.
- That exception management is where most of the operational work happens.
- That the blockchain is an audit trail and enforcement layer, not a replacement for fund administration.

The difference between a token project and a tokenized fund is the operating model around it. This repo is a small demonstration of that operating model.

## What Is Intentionally Simplified

This is a proof-of-concept, not a production system. Specifically:

- The token does not implement ERC-3643 or any formal security-token standard.
- There is no compliance module for jurisdiction rules, holding periods, or investor-count caps.
- NAV calculation, cash settlement, and custody are represented as off-chain data, not automated.
- Admin operations use a single EOA instead of multisig governance.
- The reconciliation reads a JSON snapshot instead of querying a live node.

These simplifications are deliberate. The goal is to demonstrate operational awareness and workflow design, not to ship production infrastructure.
