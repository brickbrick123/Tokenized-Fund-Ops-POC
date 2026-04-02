#!/usr/bin/env python3
"""
Daily Reconciliation Script — Tokenized Fund Operations
========================================================

Compares on-chain token balances (from a JSON snapshot) against off-chain
books-and-records (CSV files) and verifies post-quantum signed approval
artifacts to produce a daily ops exception report.

Reconciliation layers:
  1. Balance comparison — expected vs on-chain token positions.
  2. PQ approval verification — every wallet, subscription, and redemption
     must have a valid ML-DSA-65 signed approval artifact.
  3. Cross-reference — signed approvals vs actual on-chain execution.
  4. Blocked transfer detection — on-chain event log review.
  5. Investor status warnings — pending KYC/AML flags.

Break severity levels:
  - CRITICAL: Missing or invalid PQ signature on an executed transaction.
  - HIGH: Signed approval exists but on-chain action not yet taken, or
          on-chain whitelist without signed approval.
  - MEDIUM: Pending subscription/redemption, blocked transfers.

In production this would:
  - Query an archive node or indexer for real-time balances and events.
  - Pull off-chain records from a transfer-agent database or fund-admin system.
  - Post the report to an ops dashboard or ticketing system.

For this proof-of-concept, both data sources are flat files so the repo
is self-contained and reviewers can run it without infrastructure.

Usage:
    python ops/reconcile.py

Output:
    - Console summary (human-readable, designed for an ops team lead)
    - reports/daily_ops_report.md (Markdown, archivable)
    - reports/daily_attestation.json (PQ-signed reconciliation attestation)
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
#  Paths (relative to repo root)
# ---------------------------------------------------------------------------

REPO_ROOT       = Path(__file__).resolve().parent.parent
DATA_DIR        = REPO_ROOT / "data"
REPORTS_DIR     = REPO_ROOT / "reports"
APPROVALS_DIR   = DATA_DIR / "approvals"
SIGNATURES_DIR  = REPO_ROOT / "signatures"
KEYS_DIR        = DATA_DIR / "keys"
ONCHAIN_FILE    = DATA_DIR / "onchain_snapshot.json"
INVESTORS_FILE  = DATA_DIR / "investors.csv"
WALLETS_FILE    = DATA_DIR / "wallets.csv"
SUBS_FILE       = DATA_DIR / "subscriptions.csv"
REDS_FILE       = DATA_DIR / "redemptions.csv"
EXPECTED_FILE   = DATA_DIR / "expected_balances.csv"

REPORT_OUT      = REPORTS_DIR / "daily_ops_report.md"
ATTESTATION_OUT = REPORTS_DIR / "daily_attestation.json"

sys.path.insert(0, str(REPO_ROOT))
from ops.signing.keys import KeyManager
from ops.signing.pq_signer import PQSigner


# ---------------------------------------------------------------------------
#  Loaders
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def load_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_approval(name: str) -> dict | None:
    """Load a JSON approval artifact by name, or None if missing."""
    path = APPROVALS_DIR / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def load_sig(name: str) -> str | None:
    """Load a detached signature by name, or None if missing."""
    path = SIGNATURES_DIR / f"{name}.sig"
    if path.exists():
        return PQSigner.load_signature(path)
    return None


# ---------------------------------------------------------------------------
#  PQ verification helpers
# ---------------------------------------------------------------------------

def verify_approval(artifact_name: str, pk: bytes) -> dict:
    """Verify a single approval artifact + signature.

    Returns a status dict with keys: exists, valid, artifact, error.
    """
    artifact = load_approval(artifact_name)
    sig_hex  = load_sig(artifact_name)

    if artifact is None:
        return {"exists": False, "valid": False, "artifact": None,
                "error": "Approval artifact not found"}

    if sig_hex is None:
        return {"exists": True, "valid": False, "artifact": artifact,
                "error": "Detached signature file not found"}

    valid = PQSigner.verify_artifact(artifact, sig_hex, pk)
    if not valid:
        return {"exists": True, "valid": False, "artifact": artifact,
                "error": "ML-DSA-65 signature verification failed"}

    return {"exists": True, "valid": True, "artifact": artifact, "error": None}


# ---------------------------------------------------------------------------
#  Reconciliation logic
# ---------------------------------------------------------------------------

def reconcile() -> dict:
    """Run all reconciliation checks and return a structured report dict."""

    onchain   = load_json(ONCHAIN_FILE)
    investors = load_csv(INVESTORS_FILE)
    wallets   = load_csv(WALLETS_FILE)
    subs      = load_csv(SUBS_FILE)
    reds      = load_csv(REDS_FILE)
    expected  = load_csv(EXPECTED_FILE)

    on_balances = onchain["balances"]
    snapshot_ts = onchain["snapshot_timestamp"]
    events      = onchain.get("recent_events", [])

    # Load PQ public key
    km = KeyManager(KEYS_DIR)
    pk = km.load_public_key()
    pk_hash = km.public_key_hash(pk)

    breaks: list[dict] = []
    info:   list[dict] = []

    pq_checks = {"verified": 0, "missing": 0, "invalid": 0}

    # --- 1. Balance comparison: expected vs on-chain ----------------------

    for row in expected:
        wallet     = row["wallet_address"]
        exp_tokens = float(row["expected_tokens"])
        on_tokens  = on_balances.get(wallet, 0.0)
        inv_id     = row["investor_id"]
        diff       = round(on_tokens - exp_tokens, 6)

        if abs(diff) > 0.000001:
            category = _categorize_balance_break(inv_id, wallet, diff, subs, reds)
            breaks.append({
                "type":        "BALANCE_MISMATCH",
                "severity":    "medium",
                "investor_id": inv_id,
                "wallet":      wallet,
                "expected":    exp_tokens,
                "on_chain":    on_tokens,
                "diff":        diff,
                "category":    category["label"],
                "action":      category["action"],
            })
        else:
            info.append({
                "type":        "BALANCE_OK",
                "investor_id": inv_id,
                "wallet":      wallet,
                "balance":     on_tokens,
            })

    # --- 2. PQ approval verification: wallets -----------------------------

    inv_status = {inv["investor_id"]: inv["status"] for inv in investors}

    for row in wallets:
        inv_id = row["investor_id"]
        if inv_status.get(inv_id) != "active":
            continue  # pending investors handled separately

        if row["approved"] != "yes":
            continue

        result = verify_approval(f"wallet_approval_{inv_id}", pk)

        if result["valid"]:
            pq_checks["verified"] += 1
        elif not result["exists"]:
            pq_checks["missing"] += 1
            breaks.append({
                "type":        "WHITELISTED_WALLET_WITHOUT_SIGNED_APPROVAL",
                "severity":    "high",
                "investor_id": inv_id,
                "wallet":      row["wallet_address"],
                "category":    "Wallet whitelisted on-chain but no PQ-signed approval artifact",
                "action":      "Generate and sign wallet approval before next attestation window",
            })
        else:
            pq_checks["invalid"] += 1
            breaks.append({
                "type":        "INVALID_PQ_SIGNATURE",
                "severity":    "critical",
                "investor_id": inv_id,
                "wallet":      row["wallet_address"],
                "category":    f"Wallet approval signature invalid — {result['error']}",
                "action":      "Escalate immediately: possible key compromise or artifact tampering",
            })

    # --- 3. PQ approval verification: subscriptions -----------------------

    for sub in subs:
        inv_id = sub["investor_id"]
        sub_id = sub["subscription_id"]

        if inv_status.get(inv_id) != "active":
            if sub["mint_status"] == "blocked":
                breaks.append({
                    "type":        "MISSING_PQ_APPROVAL",
                    "severity":    "medium",
                    "investor_id": inv_id,
                    "sub_id":      sub_id,
                    "amount_usd":  sub["amount_usd"],
                    "category":    "Subscription blocked — investor not approved, no PQ approval possible",
                    "action":      "Resolve KYC/AML before processing; PQ approval will follow clearance",
                })
            continue

        result = verify_approval(f"subscription_approval_{sub_id}", pk)

        if result["valid"]:
            pq_checks["verified"] += 1

            if sub["mint_status"] == "pending":
                breaks.append({
                    "type":        "APPROVED_INSTRUCTION_WITHOUT_ONCHAIN_EXECUTION",
                    "severity":    "high",
                    "investor_id": inv_id,
                    "sub_id":      sub_id,
                    "tokens":      sub["tokens_expected"],
                    "category":    "PQ-signed subscription approval exists but mint not executed on-chain",
                    "action":      "Execute mint instruction — approval is valid and verified",
                })
        elif not result["exists"]:
            pq_checks["missing"] += 1
            if sub["mint_status"] == "minted":
                breaks.append({
                    "type":        "MISSING_PQ_APPROVAL",
                    "severity":    "critical",
                    "investor_id": inv_id,
                    "sub_id":      sub_id,
                    "category":    "Tokens minted on-chain without PQ-signed approval artifact",
                    "action":      "Escalate: on-chain action executed without required off-chain authorization",
                })
            else:
                breaks.append({
                    "type":        "MISSING_PQ_APPROVAL",
                    "severity":    "high",
                    "investor_id": inv_id,
                    "sub_id":      sub_id,
                    "category":    "Subscription instruction lacks PQ-signed approval",
                    "action":      "Generate and sign approval artifact before executing mint",
                })
        else:
            pq_checks["invalid"] += 1
            breaks.append({
                "type":        "INVALID_PQ_SIGNATURE",
                "severity":    "critical",
                "investor_id": inv_id,
                "sub_id":      sub_id,
                "category":    f"Subscription approval signature invalid — {result['error']}",
                "action":      "Escalate immediately: possible key compromise or artifact tampering",
            })

    # --- 4. PQ approval verification: redemptions -------------------------

    for red in reds:
        inv_id = red["investor_id"]
        red_id = red["redemption_id"]

        if inv_status.get(inv_id) != "active":
            continue

        result = verify_approval(f"redemption_approval_{red_id}", pk)

        if result["valid"]:
            pq_checks["verified"] += 1

            if red["burn_status"] in ("queued", "pending"):
                breaks.append({
                    "type":        "APPROVED_INSTRUCTION_WITHOUT_ONCHAIN_EXECUTION",
                    "severity":    "high",
                    "investor_id": inv_id,
                    "red_id":      red_id,
                    "tokens":      red["tokens_to_burn"],
                    "category":    "PQ-signed redemption approval exists but burn not executed on-chain",
                    "action":      "Execute burn and initiate cash disbursement — approval is valid",
                })
        elif not result["exists"]:
            pq_checks["missing"] += 1
            severity = "critical" if red["burn_status"] == "burned" else "high"
            breaks.append({
                "type":        "MISSING_PQ_APPROVAL",
                "severity":    severity,
                "investor_id": inv_id,
                "red_id":      red_id,
                "category":    "Redemption lacks PQ-signed approval artifact",
                "action":      "Escalate: redemption processed without required authorization"
                               if red["burn_status"] == "burned"
                               else "Generate and sign approval before executing burn",
            })
        else:
            pq_checks["invalid"] += 1
            breaks.append({
                "type":        "INVALID_PQ_SIGNATURE",
                "severity":    "critical",
                "investor_id": inv_id,
                "red_id":      red_id,
                "category":    f"Redemption approval signature invalid — {result['error']}",
                "action":      "Escalate immediately: possible key compromise or artifact tampering",
            })

    # --- 5. Blocked transfer events (from on-chain log) -------------------

    for evt in events:
        if evt.get("event") == "TransferBlocked":
            breaks.append({
                "type":     "BLOCKED_TRANSFER",
                "severity": "medium",
                "from":     evt["from"],
                "to":       evt["to"],
                "amount":   evt["amount"],
                "reason":   evt.get("reason", "unknown"),
                "category": "Transfer rejected — recipient not on whitelist",
                "action":   "Review: was this an authorized transfer attempt? If yes, onboard recipient first.",
            })

    # --- 6. Investor status warnings --------------------------------------

    for inv in investors:
        if inv["status"] == "pending":
            info.append({
                "type":        "INVESTOR_PENDING",
                "investor_id": inv["investor_id"],
                "name":        inv["legal_name"],
                "note":        "KYC/AML under review — no on-chain activity permitted",
            })

    # --- Sort breaks by severity ------------------------------------------

    severity_order = {"critical": 0, "high": 1, "medium": 2}
    breaks.sort(key=lambda b: severity_order.get(b.get("severity", "medium"), 9))

    return {
        "run_timestamp":        datetime.now(timezone.utc).isoformat(),
        "snapshot_timestamp":   snapshot_ts,
        "total_supply_onchain": onchain["total_supply"],
        "pq_algorithm":         "ML-DSA-65 (NIST FIPS 204)",
        "pq_public_key_hash":   pk_hash,
        "pq_checks":            pq_checks,
        "breaks":               breaks,
        "info":                  info,
    }


def _categorize_balance_break(inv_id, wallet, diff, subs, reds) -> dict:
    """Heuristic categorization of a balance mismatch."""

    for sub in subs:
        if sub["investor_id"] == inv_id and sub["mint_status"] in ("pending", "blocked"):
            return {
                "label": f"Pending subscription {sub['subscription_id']} — off-chain expects tokens not yet minted",
                "action": "Track SUB instruction status; mint once cleared",
            }

    for red in reds:
        if red["investor_id"] == inv_id and red["burn_status"] in ("queued", "pending"):
            return {
                "label": f"Pending redemption {red['redemption_id']} — burn not yet executed",
                "action": "Execute burn; update off-chain ledger once settled",
            }

    return {
        "label": "Unexplained mismatch — requires manual investigation",
        "action": "Escalate to transfer-agent team for root-cause analysis",
    }


# ---------------------------------------------------------------------------
#  Report formatting
# ---------------------------------------------------------------------------

def format_report(report: dict) -> str:
    """Render the reconciliation report as Markdown."""

    lines = []
    lines.append("# Daily Ops Reconciliation Report")
    lines.append("")
    lines.append(f"**Run timestamp:** {report['run_timestamp']}")
    lines.append(f"**On-chain snapshot:** {report['snapshot_timestamp']}")
    lines.append(f"**Total supply (on-chain):** {report['total_supply_onchain']:,.6f} tokens")
    lines.append("")

    # PQ verification summary
    pq = report["pq_checks"]
    lines.append("## PQ Signature Verification Summary")
    lines.append("")
    lines.append(f"- **Algorithm:** {report['pq_algorithm']}")
    lines.append(f"- **Public key hash:** `{report['pq_public_key_hash']}`")
    lines.append(f"- **Artifacts verified:** {pq['verified']}")
    lines.append(f"- **Missing approvals:** {pq['missing']}")
    lines.append(f"- **Invalid signatures:** {pq['invalid']}")
    lines.append("")

    breaks = report["breaks"]
    info   = report["info"]

    # Summary
    lines.append("## Summary")
    lines.append("")

    critical = sum(1 for b in breaks if b.get("severity") == "critical")
    high     = sum(1 for b in breaks if b.get("severity") == "high")
    medium   = sum(1 for b in breaks if b.get("severity") == "medium")

    lines.append(f"- **Total breaks:** {len(breaks)}")
    lines.append(f"  - Critical: {critical}")
    lines.append(f"  - High: {high}")
    lines.append(f"  - Medium: {medium}")
    lines.append(f"- **Clean balances:** {sum(1 for i in info if i['type'] == 'BALANCE_OK')}")
    lines.append(f"- **Pending investors:** {sum(1 for i in info if i['type'] == 'INVESTOR_PENDING')}")
    lines.append("")

    if not breaks:
        lines.append("> All balances reconcile. All PQ approvals verified. No exceptions.")
        lines.append("")
    else:
        lines.append("## Exception Details")
        lines.append("")

        for i, brk in enumerate(breaks, 1):
            severity_tag = brk.get("severity", "medium").upper()
            lines.append(f"### Break #{i} — {brk['type']} [{severity_tag}]")
            lines.append("")

            for k, v in brk.items():
                if k in ("type", "severity"):
                    continue
                label = k.replace("_", " ").title()
                lines.append(f"- **{label}:** {v}")
            lines.append("")

    # Clean balances
    ok_balances = [i for i in info if i["type"] == "BALANCE_OK"]
    if ok_balances:
        lines.append("## Reconciled Balances (No Exceptions)")
        lines.append("")
        lines.append("| Investor | Wallet | Balance |")
        lines.append("|----------|--------|---------|")
        for b in ok_balances:
            short_wallet = b["wallet"][:10] + "..."
            lines.append(f"| {b['investor_id']} | `{short_wallet}` | {b['balance']:,.6f} |")
        lines.append("")

    # Pending investors
    pending = [i for i in info if i["type"] == "INVESTOR_PENDING"]
    if pending:
        lines.append("## Pending Investors (Not Yet Approved)")
        lines.append("")
        for p in pending:
            lines.append(f"- **{p['investor_id']}** — {p['name']}: {p['note']}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*This report is auto-generated by `ops/reconcile.py`. "
                 "Breaks should be reviewed and resolved by the fund operations "
                 "team before end of business. The report itself is PQ-signed "
                 "as a daily attestation.*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  Daily attestation
# ---------------------------------------------------------------------------

def generate_attestation(report: dict) -> dict:
    """Create and PQ-sign a daily reconciliation attestation."""

    km = KeyManager(KEYS_DIR)
    pk, sk = km.load_keypair()
    pk_hash = km.public_key_hash(pk)

    attestation = {
        "attestation_type": "daily_reconciliation",
        "run_timestamp": report["run_timestamp"],
        "snapshot_timestamp": report["snapshot_timestamp"],
        "total_supply_onchain": report["total_supply_onchain"],
        "breaks_count": len(report["breaks"]),
        "critical_breaks": sum(1 for b in report["breaks"] if b.get("severity") == "critical"),
        "high_breaks": sum(1 for b in report["breaks"] if b.get("severity") == "high"),
        "medium_breaks": sum(1 for b in report["breaks"] if b.get("severity") == "medium"),
        "pq_checks": report["pq_checks"],
        "attested_by": "ops_authority",
        "pq_algorithm": "ML-DSA-65",
        "pq_public_key_hash": pk_hash,
    }

    sig_hex = PQSigner.sign_artifact(attestation, sk)

    return {
        "attestation": attestation,
        "signature": sig_hex,
    }


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main():
    print("Running daily reconciliation with PQ verification...\n")

    report  = reconcile()
    md_text = format_report(report)

    # Write Markdown report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(md_text)

    # Generate and write PQ-signed attestation
    attestation = generate_attestation(report)
    ATTESTATION_OUT.write_text(json.dumps(attestation, indent=2))

    # Print to console
    print(md_text)
    print(f"Report written to {REPORT_OUT.relative_to(REPO_ROOT)}")
    print(f"Attestation written to {ATTESTATION_OUT.relative_to(REPO_ROOT)}")

    # Exit with non-zero if breaks exist
    if report["breaks"]:
        critical = sum(1 for b in report["breaks"] if b.get("severity") == "critical")
        high     = sum(1 for b in report["breaks"] if b.get("severity") == "high")
        medium   = sum(1 for b in report["breaks"] if b.get("severity") == "medium")
        print(f"\n⚠  {len(report['breaks'])} exception(s) require attention "
              f"({critical} critical, {high} high, {medium} medium).")
        sys.exit(1)
    else:
        print("\n✓  All balances reconcile. All PQ approvals verified. No exceptions.")
        sys.exit(0)


if __name__ == "__main__":
    main()
