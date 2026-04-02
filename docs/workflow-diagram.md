# Tokenized Fund Operations — Lifecycle Workflow

The diagram below traces the end-to-end lifecycle of a single investor from onboarding through daily reconciliation, including the post-quantum signing layer.

```mermaid
flowchart TD
    A[Investor Submits Application] --> B{KYC / AML Review}
    B -- Cleared --> C[Investor Approved in Registry]
    B -- Failed / Pending --> B1[Application Held — Compliance Follow-Up]

    C --> D[Wallet Address Submitted]
    D --> PQ1[Ops Authority Signs Wallet Approval — ML-DSA-65]
    PQ1 --> E[Admin Whitelists Wallet On-Chain]
    E --> F[Wallet Approved Event Emitted]

    F --> G[Cash Received Off-Chain]
    G --> H{Subscription Instruction Validated?}
    H -- Yes --> PQ2[Ops Authority Signs Subscription Approval — ML-DSA-65]
    H -- No --> H1[Subscription Queued — Exception Flagged]
    PQ2 --> I[Admin Mints Tokens On-Chain]

    I --> J[Subscription Event Emitted]
    J --> K[Off-Chain Ledger Updated]
    K --> L[Daily Reconciliation Runs]

    L --> L1[Verify PQ Signatures on All Approval Artifacts]
    L1 --> L2[Cross-Reference Approvals vs On-Chain State]
    L2 --> M{All Layers Agree?}
    M -- Match --> N[Balance Confirmed + PQ Verified ✓]
    M -- Mismatch --> O[Break Identified — Severity Assigned]
    O --> P[Ops Team Reviews and Resolves]

    P --> Q{Resolution}
    Q -- Stale Ledger --> K
    Q -- Pending Mint --> I
    Q -- Pending Burn --> R
    Q -- Missing PQ Approval --> PQ3[Generate and Sign Approval Artifact]
    PQ3 --> K

    L2 --> ATT[PQ-Sign Daily Attestation — ML-DSA-65]
    ATT --> ATT1[Attestation Archived]

    subgraph Redemption Flow
        S[Investor Requests Redemption] --> T[NAV Calculated / Amount Finalized]
        T --> U{Burn Instruction Validated?}
        U -- Yes --> PQ4[Ops Authority Signs Redemption Approval — ML-DSA-65]
        PQ4 --> R[Admin Burns Tokens On-Chain]
        U -- No --> U1[Redemption Queued — Exception Flagged]
        R --> V[Redemption Event Emitted]
        V --> W[Cash Disbursed Off-Chain]
        W --> K
    end

    subgraph Transfer Restriction
        X[Peer-to-Peer Transfer Attempted] --> Y{Both Wallets Approved?}
        Y -- Yes --> Z[Transfer Executes]
        Y -- No --> Z1[Transfer Blocked — Event Logged]
        Z1 --> O
    end
```

## Key Observations

**Where post-quantum signing applies:**

- Wallet approval (before on-chain whitelisting)
- Subscription approval (before on-chain minting)
- Redemption approval (before on-chain burning)
- Daily reconciliation attestation (after all checks complete)

**Where human intervention is required:**

- KYC/AML clearance decision (compliance officer)
- Subscription instruction validation (transfer agent)
- NAV strike and redemption amount finalization (fund administrator)
- Exception resolution after reconciliation breaks (ops team)

**Where automation helps but does not replace judgment:**

- Wallet whitelisting (admin executes, compliance approves)
- Mint and burn execution (admin executes after off-chain validation)
- PQ signature verification (automated; failures escalate to humans)
- Reconciliation (script identifies and classifies breaks, humans resolve them)

## Break Severity Classification

| Severity | Examples | Response Time |
|----------|----------|---------------|
| **Critical** | Invalid PQ signature; on-chain action without signed approval | Immediate escalation |
| **High** | Signed approval without on-chain execution; wallet without signed approval | Same-day resolution |
| **Medium** | Pending subscription/redemption; blocked transfer | Next business day |

This workflow mirrors the operational model of a real transfer agent or fund administrator managing tokenized securities. The on-chain layer handles custody and transfer restriction. The PQ signing layer secures operational authorizations. Everything else — eligibility, cash settlement, NAV calculation, exception management — remains off-chain and requires operational controls.
