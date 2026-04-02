#!/usr/bin/env python3
"""
Generate PQ-Signed Approval Artifacts
======================================

Reads the off-chain books-and-records (CSV files) and produces ML-DSA-65
signed JSON artifacts for each operational approval:

  - Wallet approvals   → data/approvals/wallet_approval_INV-XXX.json
  - Subscription approvals → data/approvals/subscription_approval_SUB-XXX.json
  - Redemption approvals   → data/approvals/redemption_approval_RED-XXX.json

Detached signatures are written to signatures/.

Deliberate gaps:
  - INV-004 (Juniper Advisory): NO wallet approval (KYC pending)
  - SUB-004: NO subscription approval (investor not approved)
  These omissions produce expected breaks in the reconciliation engine.

Usage:
    python ops/generate_approvals.py
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Resolve paths relative to repo root
REPO_ROOT     = Path(__file__).resolve().parent.parent
DATA_DIR      = REPO_ROOT / "data"
APPROVALS_DIR = DATA_DIR / "approvals"
SIGNATURES_DIR = REPO_ROOT / "signatures"
KEYS_DIR      = DATA_DIR / "keys"

sys.path.insert(0, str(REPO_ROOT))
from ops.signing.keys import KeyManager
from ops.signing.pq_signer import PQSigner


def load_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def generate_wallet_approvals(
    wallets: list[dict],
    investors: list[dict],
    sk: bytes,
    pk: bytes,
    pk_hash: str,
) -> int:
    """Generate signed wallet approval artifacts for approved wallets only."""

    # Build lookup for investor status
    inv_status = {inv["investor_id"]: inv["status"] for inv in investors}
    count = 0

    for row in wallets:
        inv_id = row["investor_id"]

        # Skip unapproved investors (deliberate gap for Juniper)
        if row["approved"] != "yes" or inv_status.get(inv_id) != "active":
            continue

        artifact = {
            "artifact_type": "wallet_approval",
            "investor_id": inv_id,
            "wallet_address": row["wallet_address"],
            "wallet_label": row["label"],
            "approved_by": "ops_authority",
            "approved_date": row["approved_date"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pq_algorithm": "ML-DSA-65",
            "pq_public_key_hash": pk_hash,
        }

        sig_hex = PQSigner.sign_artifact(artifact, sk)

        # Write artifact
        artifact_path = APPROVALS_DIR / f"wallet_approval_{inv_id}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2))

        # Write detached signature
        sig_path = SIGNATURES_DIR / f"wallet_approval_{inv_id}.sig"
        PQSigner.save_signature(sig_hex, sig_path)

        count += 1

    return count


def generate_subscription_approvals(
    subs: list[dict],
    investors: list[dict],
    sk: bytes,
    pk: bytes,
    pk_hash: str,
) -> int:
    """Generate signed subscription approval artifacts.

    Only generates for investors with cleared KYC (active status).
    SUB-004 (Juniper) is deliberately skipped.
    """

    inv_status = {inv["investor_id"]: inv["status"] for inv in investors}
    count = 0

    for row in subs:
        inv_id = row["investor_id"]

        # Skip subscriptions for non-active investors
        if inv_status.get(inv_id) != "active":
            continue

        sub_id = row["subscription_id"]
        artifact = {
            "artifact_type": "subscription_approval",
            "subscription_id": sub_id,
            "investor_id": inv_id,
            "wallet_address": row["wallet_address"],
            "amount_usd": row["amount_usd"],
            "tokens_expected": row["tokens_expected"],
            "cash_received": row["cash_received"],
            "cash_date": row["cash_date"],
            "approved_by": "ops_authority",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pq_algorithm": "ML-DSA-65",
            "pq_public_key_hash": pk_hash,
        }

        sig_hex = PQSigner.sign_artifact(artifact, sk)

        artifact_path = APPROVALS_DIR / f"subscription_approval_{sub_id}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2))

        sig_path = SIGNATURES_DIR / f"subscription_approval_{sub_id}.sig"
        PQSigner.save_signature(sig_hex, sig_path)

        count += 1

    return count


def generate_redemption_approvals(
    reds: list[dict],
    investors: list[dict],
    sk: bytes,
    pk: bytes,
    pk_hash: str,
) -> int:
    """Generate signed redemption approval artifacts."""

    inv_status = {inv["investor_id"]: inv["status"] for inv in investors}
    count = 0

    for row in reds:
        inv_id = row["investor_id"]

        if inv_status.get(inv_id) != "active":
            continue

        red_id = row["redemption_id"]
        artifact = {
            "artifact_type": "redemption_approval",
            "redemption_id": red_id,
            "investor_id": inv_id,
            "wallet_address": row["wallet_address"],
            "tokens_to_burn": row["tokens_to_burn"],
            "redemption_usd": row["redemption_usd"],
            "request_date": row["request_date"],
            "approved_by": "ops_authority",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pq_algorithm": "ML-DSA-65",
            "pq_public_key_hash": pk_hash,
        }

        sig_hex = PQSigner.sign_artifact(artifact, sk)

        artifact_path = APPROVALS_DIR / f"redemption_approval_{red_id}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2))

        sig_path = SIGNATURES_DIR / f"redemption_approval_{red_id}.sig"
        PQSigner.save_signature(sig_hex, sig_path)

        count += 1

    return count


def main():
    print("Generating PQ-signed approval artifacts...\n")

    # Ensure directories
    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    SIGNATURES_DIR.mkdir(parents=True, exist_ok=True)

    # Load or generate keypair
    km = KeyManager(KEYS_DIR)
    pk, sk = km.ensure_keypair()
    pk_hash = km.public_key_hash(pk)

    if km.keypair_exists():
        print(f"  Loaded ML-DSA-65 keypair (public key hash: {pk_hash})")
    else:
        print(f"  Generated new ML-DSA-65 keypair (public key hash: {pk_hash})")

    # Load off-chain records
    investors = load_csv(DATA_DIR / "investors.csv")
    wallets   = load_csv(DATA_DIR / "wallets.csv")
    subs      = load_csv(DATA_DIR / "subscriptions.csv")
    reds      = load_csv(DATA_DIR / "redemptions.csv")

    # Generate artifacts
    n_wallets = generate_wallet_approvals(wallets, investors, sk, pk, pk_hash)
    n_subs    = generate_subscription_approvals(subs, investors, sk, pk, pk_hash)
    n_reds    = generate_redemption_approvals(reds, investors, sk, pk, pk_hash)

    total = n_wallets + n_subs + n_reds

    print(f"\n  Wallet approvals:       {n_wallets}")
    print(f"  Subscription approvals: {n_subs}")
    print(f"  Redemption approvals:   {n_reds}")
    print(f"  Total artifacts:        {total}")

    # Report deliberate gaps
    print("\n  Deliberate gaps (expected recon breaks):")
    print("    - INV-004 (Juniper Advisory): no wallet approval (KYC pending)")
    print("    - SUB-004: no subscription approval (investor not approved)")
    print("    - SUB-003: signed approval exists but mint NOT executed on-chain")
    print("    - RED-002: signed approval exists but burn NOT executed on-chain")

    print(f"\n  Artifacts written to {APPROVALS_DIR.relative_to(REPO_ROOT)}/")
    print(f"  Signatures written to {SIGNATURES_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
