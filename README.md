# Tokenized Fund Operations Demo

**A proof-of-concept that models the operational layer behind a tokenized private fund — not just the smart contracts, but the investor onboarding, transfer restrictions, books and records, daily reconciliation, and exception management that make tokenized funds work in a regulated institutional setting.**

---

## Why This Exists

Deploying a token is straightforward. Operating a tokenized fund is not.

In traditional fund administration, a transfer agent maintains investor eligibility records, validates subscription and redemption instructions against cash movements, enforces transfer restrictions, and reconciles share registers daily. When the share register moves on-chain, that operational surface area doesn't shrink — it expands. Now the books and records live in two places, and they must agree.

This repo demonstrates practical understanding of that operational reality. It simulates a small institutional fund with permissioned investors, wallet whitelisting, subscription-based minting, redemption-based burning, restricted peer-to-peer transfers, off-chain books and records, and a daily reconciliation that flags exceptions.

The central message: **creating a token and operating a tokenized fund are fundamentally different problems.**

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
          reconcile.py                 └─────────────────────────────────┘
                 │
      ┌──────────▼──────────┐
      │  Daily Ops Report   │
      │  ─ Break categories │
      │  ─ Recommended      │
      │    actions           │
      └─────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for detailed design decisions and [docs/workflow-diagram.md](docs/workflow-diagram.md) for the full Mermaid lifecycle diagram.

---

## Operational Workflow

1. **Investor onboarded** — KYC/AML documents submitted and cleared.
2. **Eligibility approved** — Admin registers the investor in `InvestorRegistry`.
3. **Wallet whitelisted** — Admin links one or more wallets to the approved investor.
4. **Cash received off-chain** — Wire or stablecoin settlement confirmed.
5. **Subscription validated** — Transfer agent checks eligibility, cash, and instruction details.
6. **Tokens minted on-chain** — `PermissionedFundToken.mint()` with a `subscriptionId` reference.
7. **Ledger updated off-chain** — Books and records reflect the new position.
8. **Daily reconciliation** — `reconcile.py` compares on-chain balances to off-chain expectations.
9. **Exceptions flagged** — Breaks are categorized and routed to the ops team.
10. **Redemption processed** — NAV struck, burn executed, cash disbursed.

---

## Sample Scenario

The repo includes a narrative cast of four investors:

| Investor | Status | Scenario |
|----------|--------|----------|
| **North River Family Office** | Active | Clean $500K subscription, minted. Has a pending $100K redemption (queued, not yet burned). |
| **Elm Street Capital** | Active | $1M subscription, minted. Clean $250K redemption, burned and settled. |
| **Harbor Peak LP** | Active | $750K subscription — cash received but **mint not yet executed** (deliberate recon break). |
| **Juniper Advisory** | Pending | KYC under review. Submitted $250K but **cannot be processed** until cleared. Attempted transfer to their wallet was **blocked on-chain**. |

Running the reconciliation produces four breaks:
- Pending subscription for Harbor Peak (mint instruction not executed)
- Blocked subscription for Juniper (KYC not cleared)
- Pending redemption for North River (burn queued but not executed)
- Blocked transfer attempt to Juniper's unapproved wallet

---

## Repo Structure

```
├── README.md
├── foundry.toml
├── src/
│   ├── InvestorRegistry.sol        # Investor eligibility + wallet whitelist
│   └── PermissionedFundToken.sol   # Permissioned ERC-20 fund token
├── script/
│   └── Deploy.s.sol                # Deploys and seeds sample data
├── test/
│   └── PermissionedFundToken.t.sol # 19 tests covering full lifecycle
├── ops/
│   └── reconcile.py                # Daily recon: on-chain vs off-chain
├── data/
│   ├── investors.csv               # Investor master file
│   ├── wallets.csv                 # Approved wallet registry
│   ├── subscriptions.csv           # Subscription instructions
│   ├── redemptions.csv             # Redemption requests
│   ├── expected_balances.csv       # Expected token positions
│   └── onchain_snapshot.json       # Simulated on-chain state
├── reports/
│   └── daily_ops_report.md         # Auto-generated exception report
└── docs/
    ├── one-page-explainer.md       # Briefing note for ops/product leaders
    ├── architecture.md             # Design decisions and system layers
    └── workflow-diagram.md         # Mermaid lifecycle diagram
```

---

## How to Run

### Prerequisites

- [Foundry](https://book.getfoundry.sh/getting-started/installation) (forge, anvil)
- Python 3.8+

### Compile and Test Contracts

```bash
forge build
forge test -v
```

Expected: 19 tests pass covering subscription minting, redemption burning, transfer restrictions, admin flows, pause behavior, and event emissions.

### Run the Reconciliation Script

```bash
python3 ops/reconcile.py
```

Expected: 4 breaks flagged, each categorized with a recommended action. The report is written to `reports/daily_ops_report.md`.

### Deploy to Local Node (Optional)

```bash
anvil &
forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast
```

---

## Sample Output

Running `python3 ops/reconcile.py` produces:

```
## Summary

- Breaks found: 4
- Clean balances: 2
- Pending investors: 1

## Exception Details

### Break #1 — PENDING_SUBSCRIPTION
- Investor Id: INV-003
- Category: Subscription not yet minted
- Action: Execute mint instruction

### Break #2 — PENDING_SUBSCRIPTION
- Investor Id: INV-004
- Category: Subscription blocked — investor not approved
- Action: Resolve KYC/AML before processing

### Break #3 — PENDING_REDEMPTION
- Investor Id: INV-001
- Category: Redemption queued — burn not yet executed
- Action: Execute burn and initiate cash disbursement

### Break #4 — BLOCKED_TRANSFER
- Category: Transfer rejected — recipient not on whitelist
- Action: Review: was this an authorized transfer attempt?
```

---

## What This Demonstrates

- **Investor onboarding and eligibility** — KYC-gated registry with admin approval flows
- **Wallet whitelisting** — On-chain enforcement of which addresses can hold and receive tokens
- **Subscription lifecycle** — Cash receipt → instruction validation → mint with off-chain reference
- **Redemption lifecycle** — Request → NAV calculation → burn → cash disbursement
- **Transfer restrictions** — Only approved-to-approved transfers; all others rejected and logged
- **Books and records** — Parallel off-chain ledger mirroring on-chain positions
- **Daily reconciliation** — Automated comparison with categorized break reports
- **Exception management** — Actionable output for an ops team, not just raw data
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

---

## Docs

- **[One-Page Explainer](docs/one-page-explainer.md)** — Briefing note: why tokenization requires more than a smart contract.
- **[Architecture](docs/architecture.md)** — System layers, contract relationships, and design rationale.
- **[Workflow Diagram](docs/workflow-diagram.md)** — Full Mermaid lifecycle from onboarding to exception resolution.

---

*Built to demonstrate operational literacy in tokenized fund infrastructure — the engine room behind tokenized assets, not just the token itself.*
