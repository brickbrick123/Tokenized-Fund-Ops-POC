# Tokenized Fund Operations — Lifecycle Workflow

The diagram below traces the end-to-end lifecycle of a single investor from onboarding through daily reconciliation.

```mermaid
flowchart TD
    A[Investor Submits Application] --> B{KYC / AML Review}
    B -- Cleared --> C[Investor Approved in Registry]
    B -- Failed / Pending --> B1[Application Held — Compliance Follow-Up]

    C --> D[Wallet Address Submitted]
    D --> E[Admin Whitelists Wallet On-Chain]
    E --> F[Wallet Approved Event Emitted]

    F --> G[Cash Received Off-Chain]
    G --> H{Subscription Instruction Validated?}
    H -- Yes --> I[Admin Mints Tokens On-Chain]
    H -- No --> H1[Subscription Queued — Exception Flagged]

    I --> J[Subscription Event Emitted]
    J --> K[Off-Chain Ledger Updated]
    K --> L[Daily Reconciliation Runs]

    L --> M{On-Chain == Off-Chain?}
    M -- Match --> N[Balance Confirmed ✓]
    M -- Mismatch --> O[Break Identified — Exception Report Generated]
    O --> P[Ops Team Reviews and Resolves]

    P --> Q{Resolution}
    Q -- Stale Ledger --> K
    Q -- Pending Mint --> I
    Q -- Pending Burn --> R

    subgraph Redemption Flow
        S[Investor Requests Redemption] --> T[NAV Calculated / Amount Finalized]
        T --> U{Burn Instruction Validated?}
        U -- Yes --> R[Admin Burns Tokens On-Chain]
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

**Where human intervention is required:**

- KYC/AML clearance decision (compliance officer)
- Subscription instruction validation (transfer agent)
- NAV strike and redemption amount finalization (fund administrator)
- Exception resolution after reconciliation breaks (ops team)

**Where automation helps but does not replace judgment:**

- Wallet whitelisting (admin executes, compliance approves)
- Mint and burn execution (admin executes after off-chain validation)
- Reconciliation (script identifies breaks, humans resolve them)

This workflow mirrors the operational model of a real transfer agent or fund administrator managing tokenized securities. The on-chain layer handles custody and transfer restriction. Everything else — eligibility, cash settlement, NAV calculation, exception management — remains off-chain and requires operational controls.
