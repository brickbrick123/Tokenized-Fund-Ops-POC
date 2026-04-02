#!/usr/bin/env python3
"""
End-to-End Demo — Hybrid Post-Quantum Fund Operations
=======================================================

Orchestrates the full lifecycle so a reviewer can see every layer in action:

  1. Generate (or load) ML-DSA-65 keypair
  2. Generate PQ-signed approval artifacts for wallets, subscriptions, redemptions
  3. Run the daily reconciliation with PQ verification
  4. Print a narrative walkthrough explaining each step
  5. Verify the daily attestation signature

Usage:
    python ops/demo.py
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ops.signing.keys import KeyManager
from ops.signing.pq_signer import PQSigner
from ops.generate_approvals import main as generate_main
from ops.reconcile import reconcile, format_report, generate_attestation
from ops.reconcile import REPORTS_DIR, REPORT_OUT, ATTESTATION_OUT

KEYS_DIR = REPO_ROOT / "data" / "keys"


def banner(text: str) -> None:
    width = max(len(text) + 4, 60)
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width + "\n")


def section(text: str) -> None:
    print(f"\n--- {text} ---\n")


def main():
    banner("Hybrid Post-Quantum Fund Operations — End-to-End Demo")

    # ------------------------------------------------------------------
    #  Step 1: Keypair
    # ------------------------------------------------------------------
    section("Step 1: ML-DSA-65 Keypair")

    km = KeyManager(KEYS_DIR)
    pk, sk = km.ensure_keypair()
    pk_hash = km.public_key_hash(pk)

    print(f"  Algorithm:       ML-DSA-65 (NIST FIPS 204)")
    print(f"  Public key size: {len(pk)} bytes")
    print(f"  Secret key size: {len(sk)} bytes")
    print(f"  Public key hash: {pk_hash}")

    if km.keypair_exists():
        print("  Status:          Loaded existing keypair from data/keys/")
    else:
        print("  Status:          Generated new keypair")

    # ------------------------------------------------------------------
    #  Step 2: Generate approval artifacts
    # ------------------------------------------------------------------
    section("Step 2: Generate PQ-Signed Approval Artifacts")
    generate_main()

    # ------------------------------------------------------------------
    #  Step 3: Verify a sample artifact (walkthrough)
    # ------------------------------------------------------------------
    section("Step 3: Signature Verification Walkthrough")

    sample_path = REPO_ROOT / "data" / "approvals" / "subscription_approval_SUB-001.json"
    sample_sig_path = REPO_ROOT / "signatures" / "subscription_approval_SUB-001.sig"

    if sample_path.exists() and sample_sig_path.exists():
        artifact = json.loads(sample_path.read_text())
        sig_hex = PQSigner.load_signature(sample_sig_path)

        print("  Artifact: subscription_approval_SUB-001.json")
        print(f"  Type:     {artifact.get('artifact_type')}")
        print(f"  Investor: {artifact.get('investor_id')}")
        print(f"  Amount:   ${artifact.get('amount_usd')}")
        print(f"  SHA-256:  {PQSigner.artifact_hash(artifact)[:32]}...")
        print(f"  Sig size: {len(sig_hex) // 2} bytes ({len(sig_hex)} hex chars)")

        valid = PQSigner.verify_artifact(artifact, sig_hex, pk)
        print(f"  Verified: {'PASS' if valid else 'FAIL'}")

        # Demonstrate tamper detection
        tampered = dict(artifact)
        tampered["amount_usd"] = "999999.00"
        tampered_valid = PQSigner.verify_artifact(tampered, sig_hex, pk)
        print(f"\n  Tamper test (modified amount_usd to $999,999):")
        print(f"  Verified: {'FAIL — tampering detected' if not tampered_valid else 'PASS (unexpected)'}")
    else:
        print("  (sample artifact not found — run generate_approvals.py first)")

    # ------------------------------------------------------------------
    #  Step 4: Daily reconciliation
    # ------------------------------------------------------------------
    section("Step 4: Daily Reconciliation with PQ Verification")

    report = reconcile()
    md_text = format_report(report)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(md_text)

    # Print summary (not the full report — it's long)
    pq = report["pq_checks"]
    print(f"  PQ artifacts verified: {pq['verified']}")
    print(f"  Missing approvals:     {pq['missing']}")
    print(f"  Invalid signatures:    {pq['invalid']}")
    print(f"  Total breaks:          {len(report['breaks'])}")

    for brk in report["breaks"]:
        sev = brk.get("severity", "medium").upper()
        print(f"    [{sev}] {brk['type']}: {brk.get('category', '')}")

    # ------------------------------------------------------------------
    #  Step 5: PQ-signed daily attestation
    # ------------------------------------------------------------------
    section("Step 5: PQ-Signed Daily Attestation")

    attestation = generate_attestation(report)
    ATTESTATION_OUT.write_text(json.dumps(attestation, indent=2))

    att = attestation["attestation"]
    print(f"  Attestation type: {att['attestation_type']}")
    print(f"  Breaks reported:  {att['breaks_count']}")
    print(f"  Attested by:      {att['attested_by']}")
    print(f"  Algorithm:        {att['pq_algorithm']}")
    print(f"  Signature size:   {len(attestation['signature']) // 2} bytes")

    # Verify the attestation we just created
    valid = PQSigner.verify_artifact(att, attestation["signature"], pk)
    print(f"  Signature valid:  {'PASS' if valid else 'FAIL'}")

    # ------------------------------------------------------------------
    #  Summary
    # ------------------------------------------------------------------
    banner("Demo Complete")

    print("  Files generated:")
    print(f"    - data/approvals/   (8 signed approval artifacts)")
    print(f"    - signatures/       (8 detached ML-DSA-65 signatures)")
    print(f"    - {REPORT_OUT.relative_to(REPO_ROOT)}")
    print(f"    - {ATTESTATION_OUT.relative_to(REPO_ROOT)}")
    print()
    print("  The hybrid model ensures that every off-chain operational")
    print("  approval is cryptographically bound to a post-quantum")
    print("  signature, while on-chain transactions continue to use")
    print("  classical ECDSA. The daily reconciliation verifies both")
    print("  layers and flags any discrepancies.")
    print()


if __name__ == "__main__":
    main()
