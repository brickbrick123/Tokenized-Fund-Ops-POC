# Tokenized Fund Operations Demo

**A proof-of-concept that models the operational layer behind a tokenized private fund, not just the smart contracts, but the investor onboarding, transfer restrictions, books and records, daily reconciliation, exception management, and a hybrid post-quantum signing layer that secures every off-chain operational approval with ML-DSA-65 (NIST FIPS 204).**

---

## Why This Exists

Deploying a token is straightforward. Operating a tokenized fund is not.

In traditional fund administration, a transfer agent maintains investor eligibility records, validates subscription and redemption instructions against cash movements, enforces transfer restrictions, and reconciles share registers daily. When the share register moves on-chain, that operational surface area doesn't shrink, it expands. Now the books and records live in two places, and they must agree.

There is a second problem. The ECDSA signatures securing blockchain transactions today are vulnerable to quantum computers. While full protocol-level migration is years away, the operational layer, where humans authorize mints, burns, and wallet registrations, is entirely off-chain and under our control. We can secure it with post-quantum cryptography today.

This repo demonstrates both: **the operational engine room behind tokenized assets, and a forward-looking hybrid model that makes every off-chain approval quantum-resistant.**

---

## Architecture

```
Off-Chain (Fund Admin / Transfer Agent)          On-Chain (Blockchain)
┌─────────────────────────────────┐    ┌─────────────────────────────────┐
│  Investor master file           │    │  InvestorRegistry.sol           │
│  Wallet registry                │    │  ─ Eligibility approvals        │
│  Subscription instructions      │    │  ─ Wallet whitelist             │
│  Redemption requests            │    │                                 │
│  Expected token balances        │    │  PermissionedFundToken.sol      │
│  Settlement status              │    │  ─ Mint on subscription         │
│  Exception flags                │    │  ─ Burn on redemption           │
└────────────────┬────────────────┘    │  ─ Transfer restrictions        │
                 │                     │  ─ Admin pause                  │
          PQ Signing Layer             └─────────────────────────────────┘
     ┌───────────┴───────────┐
     │  ML-DSA-65 keypair    │
     │  Approval artifacts   │
     │  Detached signatures  │
     │  Daily attestation    │
     └───────────┬───────────┘
                 │
          reconcile.py
                 │
      ┌──────────▼──────────┐
      │  Daily Ops Report   │
      │  ─ Break severity   │
      │  ─ PQ verification  │
      │  ─ Recommended      │
      │    actions           │
      │  ─ Signed            │
      │    attestation       │
      └─────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for detailed design decisions, [docs/hybrid-pq-model.md](docs/hybrid-pq-model.md) for the post-quantum model, and [docs/workflow-diagram.md](docs/workflow-diagram.md) for the full Mermaid lifecycle diagram.

---

## Hybrid Post-Quantum Model

On-chain transactions stay classical (ECDSA). Off-chain operational approvals are signed with **ML-DSA-65** (NIST FIPS 204, formerly CRYSTALS-Dilithium), a lattice-based post-quantum signature scheme standardized in August 2024.

Every wallet approval, subscription authorization, and redemption authorization produces a JSON artifact that is canonicalized, signed with the ops authority's ML-DSA-65 key, and stored alongside a detached signature file. The daily reconciliation engine verifies every signature, cross-references signed approvals against on-chain state, and classifies discrepancies by severity:

| Break Type | Severity | Trigger |
|-----------|----------|---------|
| `INVALID_PQ_SIGNATURE` | Critical | Approval artifact with failed signature verification |
| `MISSING_PQ_APPROVAL` | Critical/Medium | On-chain action without signed approval |
| `APPROVED_INSTRUCTION_WITHOUT_ONCHAIN_EXECUTION` | High | Signed approval exists, on-chain action pending |
| `WHITELISTED_WALLET_WITHOUT_SIGNED_APPROVAL` | High | Wallet on-chain but no approval artifact |
| `BLOCKED_TRANSFER` | Medium | Transfer rejected at contract level |

The reconciliation report itself is PQ-signed as a daily attestation.

See [docs/hybrid-pq-model.md](docs/hybrid-pq-model.md) for the threat model, migration path, and key management details.

---

## Operational Workflow

1. **Investor onboarded** — KYC/AML documents submitted and cleared.
2. **Eligibility approved** — Admin registers the investor in `InvestorRegistry`.
3. **Wallet approval signed** — Ops authority PQ-signs a wallet approval artifact (ML-DSA-65).
4. **Wallet whitelisted** — Admin links the wallet to the approved investor on-chain.
5. **Cash received off-chain** — Wire or stablecoin settlement confirmed.
6. **Subscription approval signed** — Ops authority PQ-signs a subscription approval artifact.
7. **Tokens minted on-chain** — `PermissionedFundToken.mint()` with a `subscriptionId` reference.
8. **Ledger updated off-chain** — Books and records reflect the new position.
9. **Daily reconciliation** — `reconcile.py` verifies PQ signatures, compares on-chain vs off-chain, classifies breaks by severity.
10. **Daily attestation** — The reconciliation report is PQ-signed as a verifiable attestation.
11. **Exceptions flagged** — Breaks are categorized and routed to the ops team.
12. **Redemption processed** — Approval signed, NAV struck, burn executed, cash disbursed.

---

## Sample Scenario

The repo includes a narrative cast of four investors:

| Investor | Status | Scenario |
|----------|--------|----------|
| **North River Family Office** | Active | Clean $500K subscription, minted and PQ-approved. Has a pending $100K redemption (PQ-signed but burn not yet executed). |
| **Elm Street Capital** | Active | $1M subscription, minted and PQ-approved. Clean $250K redemption, burned and settled with valid PQ approval. |
| **Harbor Peak LP** | Active | $750K subscription — cash received and PQ-signed but **mint not yet executed** (deliberate break). |
| **Juniper Advisory** | Pending | KYC under review. Submitted $250K but **cannot be processed** — no PQ approval possible. Transfer to their wallet was **blocked on-chain**. |

Running the reconciliation produces 4 breaks:

- **[HIGH]** Harbor Peak subscription: PQ-signed approval exists but mint not executed on-chain
- **[HIGH]** North River redemption: PQ-signed approval exists but burn not executed on-chain
- **[MEDIUM]** Juniper subscription: blocked — investor not approved, no PQ approval possible
- **[MEDIUM]** Blocked transfer attempt to Juniper's unapproved wallet

---

## Repo Structure

```
├── README.md
├── foundry.toml
├── src/
│   ├── InvestorRegistry.sol          # Investor eligibility + wallet whitelist
│   └── PermissionedFundToken.sol     # Permissioned ERC-20 fund token
├── script/
│   └── Deploy.s.sol                  # Deploys and seeds sample data
├── test/
│   └── PermissionedFundToken.t.sol   # 19 tests covering full lifecycle
├── ops/
│   ├── signing/
│   │   ├── __init__.py               # PQ signing module exports
│   │   ├── keys.py                   # ML-DSA-65 key management
│   │   └── pq_signer.py             # Artifact signing and verification
│   ├── generate_approvals.py         # Generates PQ-signed approval artifacts
│   ├── reconcile.py                  # Daily recon with PQ verification
│   └── demo.py                       # End-to-end demo orchestration
├── data/
│   ├── investors.csv                 # Investor master file
│   ├── wallets.csv                   # Approved wallet registry
│   ├── subscriptions.csv             # Subscription instructions
│   ├── redemptions.csv               # Redemption requests
│   ├── expected_balances.csv         # Expected token positions
│   ├── onchain_snapshot.json         # Simulated on-chain state
│   ├── approvals/                    # PQ-signed JSON approval artifacts
│   └── keys/
│       └── ops_authority.pub         # ML-DSA-65 public key (secret key excluded)
├── signatures/                       # Detached ML-DSA-65 signature files
├── reports/
│   ├── daily_ops_report.md           # Auto-generated exception report
│   └── daily_attestation.json        # PQ-signed daily attestation
└── docs/
    ├── hybrid-pq-model.md            # Post-quantum architecture and threat model
    ├── architecture.md               # System layers and design decisions
    ├── one-page-explainer.md          # Briefing note for ops/product leaders
    └── workflow-diagram.md            # Mermaid lifecycle diagram with PQ steps
```

---

## How to Run

### Prerequisites

- [Foundry](https://book.getfoundry.sh/getting-started/installation) (forge, anvil)
- Python 3.10+
- `pqcrypto` library: `pip install pqcrypto`

### Compile and Test Contracts

```bash
forge build
forge test -v
```

Expected: 19 tests pass covering subscription minting, redemption burning, transfer restrictions, admin flows, pause behavior, and event emissions.

### Run the Full Demo

```bash
python3 ops/demo.py
```

This runs the complete lifecycle: generates the ML-DSA-65 keypair (if needed), creates PQ-signed approval artifacts, runs reconciliation with signature verification, and outputs a narrative walkthrough.

### Run Individual Steps

```bash
# Generate PQ-signed approval artifacts
python3 ops/generate_approvals.py

# Run daily reconciliation with PQ verification
python3 ops/reconcile.py
```

### Deploy to Local Node (Optional)

```bash
anvil &
forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast
```

---

## Sample Output

Running `python3 ops/reconcile.py` produces:

```
## PQ Signature Verification Summary

- Algorithm: ML-DSA-65 (NIST FIPS 204)
- Artifacts verified: 8
- Missing approvals: 0
- Invalid signatures: 0

## Summary

- Total breaks: 4
  - Critical: 0
  - High: 2
  - Medium: 2

## Exception Details

### Break #1 — APPROVED_INSTRUCTION_WITHOUT_ONCHAIN_EXECUTION [HIGH]
- Investor Id: INV-003
- Category: PQ-signed subscription approval exists but mint not executed on-chain
- Action: Execute mint instruction — approval is valid and verified

### Break #2 — APPROVED_INSTRUCTION_WITHOUT_ONCHAIN_EXECUTION [HIGH]
- Investor Id: INV-001
- Category: PQ-signed redemption approval exists but burn not executed on-chain
- Action: Execute burn and initiate cash disbursement — approval is valid

### Break #3 — MISSING_PQ_APPROVAL [MEDIUM]
- Investor Id: INV-004
- Category: Subscription blocked — investor not approved, no PQ approval possible
- Action: Resolve KYC/AML before processing

### Break #4 — BLOCKED_TRANSFER [MEDIUM]
- Category: Transfer rejected — recipient not on whitelist
- Action: Review: was this an authorized transfer attempt?
```

---

## What This Demonstrates

- **Investor onboarding and eligibility** — KYC-gated registry with admin approval flows
- **Wallet whitelisting** — On-chain enforcement of which addresses can hold and receive tokens
- **Subscription lifecycle** — Cash receipt → instruction validation → PQ-signed approval → mint with off-chain reference
- **Redemption lifecycle** — Request → NAV calculation → PQ-signed approval → burn → cash disbursement
- **Transfer restrictions** — Only approved-to-approved transfers; all others rejected and logged
- **Post-quantum operational approvals** — Every off-chain authorization is ML-DSA-65 signed
- **Hybrid classical + PQ model** — On-chain stays ECDSA; off-chain approvals are quantum-resistant
- **Books and records** — Parallel off-chain ledger mirroring on-chain positions
- **Daily reconciliation with PQ verification** — Automated comparison with signature validation and severity classification
- **Exception management** — Actionable output with critical/high/medium severity routing
- **Daily attestation** — PQ-signed reconciliation report as a verifiable audit artifact
- **Operational controls** — Pause capability, admin-only mutations, event audit trail

---

## What Is Intentionally Simplified

| Area | Simplification | Production Equivalent |
|------|----------------|----------------------|
| Token standard | Minimal ERC-20 with custom gates | ERC-3643 with pluggable compliance modules |
| Compliance rules | Single-tier whitelist | Jurisdiction rules, holding periods, investor-count caps |
| Admin model | Single EOA | Multisig (Safe) with role-based access |
| NAV calculation | Assumed off-chain | Oracle-fed or admin-attested NAV per period |
| Cash settlement | Represented in CSV | Bank API or stablecoin settlement integration |
| On-chain data | JSON snapshot file | Live RPC or indexer (The Graph, Goldsky) |
| Off-chain records | CSV files | Transfer-agent database or fund-admin platform |
| PQ key storage | Local file | HSM (CloudHSM, Azure Key Vault) |
| Key rotation | Manual | Scheduled rotation with overlap period |

---

## Docs

- **[Hybrid PQ Model](docs/hybrid-pq-model.md)** — Post-quantum architecture, threat model, ML-DSA-65 details, and migration path.
- **[Architecture](docs/architecture.md)** — System layers, contract relationships, PQ signing flow, and design rationale.
- **[One-Page Explainer](docs/one-page-explainer.md)** — Briefing note: why tokenization requires more than a smart contract.
- **[Workflow Diagram](docs/workflow-diagram.md)** — Full Mermaid lifecycle from onboarding to exception resolution with PQ signing steps.

---

*Built to demonstrate operational literacy in tokenized fund infrastructure — the engine room behind tokenized assets, secured with forward-looking post-quantum cryptography.*
