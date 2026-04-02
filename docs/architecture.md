# Architecture Overview

## System Layers

This project models a tokenized fund as three coordinated layers, on-chain, off-chain, and a post-quantum signing layer, with a reconciliation bridge that verifies all three.

```
┌──────────────────────────────────────────────────────────┐
│                  PQ Signing Layer                         │
│                                                          │
│  ML-DSA-65 Keypair     Approval Artifacts (JSON)         │
│  Key Manager           Detached Signatures (.sig)        │
│  Artifact Signer       Daily Attestation                 │
│                                                          │
│  ← Every operational approval is PQ-signed →             │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                     Off-Chain Layer                       │
│                                                          │
│  Investor Master File    Subscription Records            │
│  Wallet Registry         Redemption Records              │
│  Expected Balances       Settlement Status                │
│                                                          │
│  ← Maintained by fund admin / transfer agent →           │
└──────────────────────────┬───────────────────────────────┘
                           │
                    Reconciliation
                     (reconcile.py)
                           │
┌──────────────────────────▼───────────────────────────────┐
│                     On-Chain Layer                        │
│                                                          │
│  InvestorRegistry.sol    PermissionedFundToken.sol        │
│  ─ Investor approval     ─ ERC-20 with transfer gates    │
│  ─ Wallet whitelist      ─ Mint on subscription          │
│  ─ Eligibility queries   ─ Burn on redemption            │
│                          ─ Admin pause                   │
│                                                          │
│  ← Immutable audit trail; enforces permissioning →       │
└──────────────────────────────────────────────────────────┘
```

## Contract Relationships

```mermaid
classDiagram
    class InvestorRegistry {
        +address admin
        +approveInvestor(bytes32 id, string name)
        +revokeInvestor(bytes32 id)
        +approveWallet(bytes32 id, address wallet)
        +revokeWallet(bytes32 id, address wallet)
        +isApprovedWallet(address) bool
        +isApprovedInvestor(bytes32) bool
    }

    class PermissionedFundToken {
        +string name
        +string symbol
        +uint8 decimals
        +address admin
        +bool paused
        +mint(address to, uint256 amount, bytes32 subId)
        +burn(address from, uint256 amount, bytes32 redId)
        +transfer(address to, uint256 amount) bool
        +pause()
        +unpause()
    }

    PermissionedFundToken --> InvestorRegistry : queries isApprovedWallet()
```

## PQ Signing Architecture

```mermaid
classDiagram
    class KeyManager {
        +Path keys_dir
        +generate() tuple
        +load_public_key() bytes
        +load_secret_key() bytes
        +ensure_keypair() tuple
        +public_key_hash(pk) str
    }

    class PQSigner {
        +canonicalize(artifact) bytes
        +artifact_hash(artifact) str
        +sign_artifact(artifact, sk) str
        +verify_artifact(artifact, sig, pk) bool
        +save_signature(sig, path)
        +load_signature(path) str
    }

    PQSigner ..> KeyManager : uses keys from
```

## Approval Artifact Flow

```
Wallet Approval:
  Investor KYC cleared → ops authority signs artifact → wallet whitelisted on-chain

Subscription Approval:
  Cash received → ops authority signs artifact → tokens minted on-chain

Redemption Approval:
  NAV struck → ops authority signs artifact → tokens burned on-chain

Daily Reconciliation:
  For each on-chain action → load artifact → verify PQ signature → cross-reference
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Separate registry from token | Mirrors real-world separation between investor records (transfer agent) and asset issuance. Registry can serve multiple fund tokens. |
| 6-decimal precision | Common for fund-interest tokens; avoids floating-point issues that 18 decimals would introduce in off-chain reconciliation. |
| Admin-only mint/burn | Subscriptions and redemptions are not self-service. The fund admin validates off-chain before executing on-chain. |
| `bytes32 subscriptionId` in mint | Links on-chain action to off-chain instruction, making reconciliation possible. |
| Hybrid PQ model | On-chain stays classical (ECDSA); off-chain approvals secured with ML-DSA-65. No protocol changes required. |
| Detached signatures | Approval artifacts remain human-readable JSON; signatures stored separately for clean separation. |
| Canonical JSON for signing | Deterministic serialization ensures signatures verify regardless of formatting differences. |
| Severity-based breaks | Critical/high/medium classification routes exceptions to the right urgency level. |
| Simulated on-chain snapshot | Keeps the repo self-contained. In production, this would be a live RPC call or indexer query. |
| CSV off-chain records | Simple and reviewable. In production, this would be a database or fund-admin platform export. |

## What Would Change in Production

- **Registry** would integrate with a KYC provider API and support multi-sig admin operations.
- **Token** would implement ERC-3643 or a comparable security-token standard with compliance modules for jurisdiction rules, holding periods, and investor-count caps.
- **PQ key management** would use an HSM (CloudHSM, Azure Key Vault) with role-based access and key rotation policies.
- **Reconciliation** would run against a live indexer (e.g., The Graph, Goldsky) and feed results into an ops dashboard with alerting.
- **Off-chain records** would live in a transfer-agent platform (e.g., a regulated books-and-records system) rather than CSV files.
- **Deployment** would use a multisig (e.g., Safe) for admin operations rather than a single EOA.
- **Attestation** would feed into a compliance reporting pipeline with retention policies.
