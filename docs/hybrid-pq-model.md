# Hybrid Post-Quantum Operational Model

## Overview

This system implements a **hybrid classical + post-quantum** architecture for tokenized fund operations. On-chain transactions continue to use classical ECDSA (the Ethereum standard), while all off-chain operational approvals are secured with **ML-DSA-65** (NIST FIPS 204, formerly CRYSTALS-Dilithium), a lattice-based post-quantum digital signature scheme.

The rationale: quantum computers threaten the ECDSA signatures that secure blockchain transactions, but the timeline for that threat is uncertain. Rather than waiting for full protocol-level PQ migration, this model introduces PQ-signed approval artifacts at the operational layer, the part of fund administration where humans authorize actions before they reach the chain.

---

## Why Hybrid

A fully post-quantum blockchain does not exist at institutional scale today. Migrating Ethereum's signature scheme is a multi-year protocol effort. But the operational approval layer, where a fund administrator authorizes a mint, burn, or wallet registration, is entirely off-chain and under our control.

By signing every off-chain approval with ML-DSA-65:

- **Approval artifacts are quantum-resistant today.** Even if a future adversary breaks ECDSA, the off-chain authorization trail remains cryptographically intact.
- **On-chain execution stays compatible.** No changes to smart contracts, no dependency on protocol upgrades.
- **The reconciliation engine verifies both layers.** Any mismatch between PQ-signed approvals and on-chain state is flagged as an exception.

---

## ML-DSA-65 (NIST FIPS 204)

ML-DSA-65 is one of three parameter sets in the Module-Lattice-Based Digital Signature Standard, finalized by NIST in August 2024 as FIPS 204. It replaced CRYSTALS-Dilithium as the official name.

| Parameter | Value |
|-----------|-------|
| Security level | NIST Level 3 (128-bit post-quantum) |
| Public key size | 1,952 bytes |
| Secret key size | 4,032 bytes |
| Signature size | 3,309 bytes |
| Underlying problem | Module Learning With Errors (M-LWE) |

This demo uses the `pqcrypto` Python library (v0.4.0), which provides bindings to the reference implementation.

---

## Approval Artifact Lifecycle

```
1. Investor onboarded, KYC cleared
        │
        ▼
2. Ops authority generates JSON approval artifact
   (wallet, subscription, or redemption)
        │
        ▼
3. Artifact canonicalized (deterministic JSON)
        │
        ▼
4. ML-DSA-65 signature computed over canonical bytes
        │
        ▼
5. Artifact saved to data/approvals/
   Detached signature saved to signatures/
        │
        ▼
6. On-chain action executed (mint, burn, whitelist)
        │
        ▼
7. Daily reconciliation:
   - Loads each artifact
   - Verifies PQ signature
   - Cross-references on-chain state
   - Flags breaks by severity
```

### Artifact Types

**Wallet Approval** — Authorizes a wallet address to hold and receive fund tokens for a specific investor.

**Subscription Approval** — Authorizes minting tokens to an investor's wallet after cash settlement is confirmed.

**Redemption Approval** — Authorizes burning tokens from an investor's wallet and initiating cash disbursement.

### Canonical JSON

To ensure deterministic signature verification, all artifacts are serialized using:
```python
json.dumps(artifact, sort_keys=True, separators=(",", ":"))
```

This produces compact, key-sorted JSON with no whitespace variation.

---

## Threat Model

### What PQ Signing Protects Against

1. **Harvest-now, decrypt-later attacks.** An adversary recording approval artifacts today cannot forge new ones even with a future quantum computer.
2. **Unauthorized operational actions.** Any on-chain transaction without a corresponding PQ-signed approval is flagged as a critical break.
3. **Artifact tampering.** Modifying any field in a signed artifact (amount, investor ID, wallet address) invalidates the ML-DSA-65 signature.
4. **Key compromise detection.** Invalid signatures on existing artifacts indicate possible key compromise and trigger immediate escalation.

### What It Does Not Protect Against

- **On-chain ECDSA vulnerability.** If ECDSA is broken, on-chain transactions could be forged. This requires protocol-level migration (outside scope).
- **Compromised ops authority key.** If the ML-DSA-65 secret key is exfiltrated, an attacker can forge approval artifacts. Production systems would use an HSM.
- **Collusion.** If the ops authority and on-chain admin are the same compromised entity, both layers are compromised simultaneously.

---

## Key Management

In this proof-of-concept, keys are stored as hex-encoded files:

```
data/keys/
  ops_authority.pub   (public key — committed to repo)
  ops_authority.key   (secret key — excluded via .gitignore)
```

In production:

| Concern | POC Approach | Production Equivalent |
|---------|-------------|----------------------|
| Key storage | Local files | HSM (CloudHSM, Azure Key Vault) |
| Key rotation | Manual regeneration | Scheduled rotation with overlap period |
| Access control | Single operator | Role-based with audit trail |
| Backup | None | Encrypted backup in separate facility |

---

## Migration Path to Full PQ

This hybrid model is designed as a stepping stone:

1. **Current state (this demo):** PQ-signed off-chain approvals + classical on-chain execution.
2. **Near-term:** PQ-signed approval artifacts become a compliance requirement for fund administrators.
3. **Medium-term:** On-chain contracts begin accepting PQ signature proofs (EIP-level changes required).
4. **Long-term:** Full PQ migration at the protocol level (Ethereum PQ roadmap).

The off-chain PQ layer does not need to wait for any of the on-chain milestones. It can be deployed today and provides incremental security improvement immediately.
