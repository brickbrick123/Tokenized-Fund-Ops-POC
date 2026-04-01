#!/usr/bin/env python3
"""
Daily Reconciliation Script — Tokenized Fund Operations
========================================================

Compares on-chain token balances (from a JSON snapshot) against off-chain
books-and-records (CSV files) to produce a daily ops exception report.

In production this would:
  • Query an archive node or indexer for real-time balances and events.
  • Pull off-chain records from a transfer-agent database or fund-admin system.
  • Post the report to an ops dashboard or ticketing system.

For this proof-of-concept, both data sources are flat files so the repo
is self-contained and reviewers can run it without infrastructure.

Usage:
    python ops/reconcile.py

Output:
    • Console summary  (human-readable, designed for an ops team lead)
    • reports/daily_ops_report.md  (Markdown file, archivable)
"""

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
#  Paths (relative to repo root)
# ---------------------------------------------------------------------------

REPO_ROOT       = Path(__file__).resolve().parent.parent
DATA_DIR        = REPO_ROOT / "data"
REPORTS_DIR     = REPO_ROOT / "reports"
ONCHAIN_FILE    = DATA_DIR / "onchain_snapshot.json"
INVESTORS_FILE  = DATA_DIR / "investors.csv"
WALLETS_FILE    = DATA_DIR / "wallets.csv"
SUBS_FILE       = DATA_DIR / "subscriptions.csv"
REDS_FILE       = DATA_DIR / "redemptions.csv"
EXPECTED_FILE   = DATA_DIR / "expected_balances.csv"

REPORT_OUT      = REPORTS_DIR / "daily_ops_report.md"


# ---------------------------------------------------------------------------
#  Loaders
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def load_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
#  Reconciliation logic
# ---------------------------------------------------------------------------

def reconcile() -> dict:
    """Run all checks and return a structured report dict."""

    onchain   = load_json(ONCHAIN_FILE)
    investors = load_csv(INVESTORS_FILE)
    wallets   = load_csv(WALLETS_FILE)
    subs      = load_csv(SUBS_FILE)
    reds      = load_csv(REDS_FILE)
    expected  = load_csv(EXPECTED_FILE)

    on_balances = onchain["balances"]  # wallet → float
    snapshot_ts = onchain["snapshot_timestamp"]
    events      = onchain.get("recent_events", [])

    breaks: list[dict] = []
    info: list[dict]   = []

    # --- 1.  Balance comparison: expected vs on-chain ----------------------

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
                "type": "BALANCE_OK",
                "investor_id": inv_id,
                "wallet": wallet,
                "balance": on_tokens,
            })

    # --- 2.  Pending subscriptions (cash received, not yet minted) ---------

    for sub in subs:
        if sub["mint_status"] in ("pending", "blocked"):
            breaks.append({
                "type":        "PENDING_SUBSCRIPTION",
                "investor_id": sub["investor_id"],
                "sub_id":      sub["subscription_id"],
                "amount_usd":  sub["amount_usd"],
                "tokens":      sub["tokens_expected"],
                "mint_status": sub["mint_status"],
                "category":    "Subscription not yet minted" if sub["mint_status"] == "pending"
                               else "Subscription blocked — investor not approved",
                "action":      "Execute mint instruction" if sub["mint_status"] == "pending"
                               else "Resolve KYC/AML before processing",
            })

    # --- 3.  Pending redemptions (queued but not burned) -------------------

    for red in reds:
        if red["burn_status"] in ("queued", "pending"):
            breaks.append({
                "type":        "PENDING_REDEMPTION",
                "investor_id": red["investor_id"],
                "red_id":      red["redemption_id"],
                "tokens":      red["tokens_to_burn"],
                "burn_status": red["burn_status"],
                "category":    "Redemption queued — burn not yet executed",
                "action":      "Execute burn and initiate cash disbursement",
            })

    # --- 4.  Blocked transfer events (from on-chain log) -------------------

    for evt in events:
        if evt.get("event") == "TransferBlocked":
            breaks.append({
                "type":     "BLOCKED_TRANSFER",
                "from":     evt["from"],
                "to":       evt["to"],
                "amount":   evt["amount"],
                "reason":   evt.get("reason", "unknown"),
                "category": "Transfer rejected — recipient not on whitelist",
                "action":   "Review: was this an authorized transfer attempt? If yes, onboard recipient first.",
            })

    # --- 5.  Wallet / investor status warnings -----------------------------

    for inv in investors:
        if inv["status"] == "pending":
            info.append({
                "type":        "INVESTOR_PENDING",
                "investor_id": inv["investor_id"],
                "name":        inv["legal_name"],
                "note":        "KYC/AML under review — no on-chain activity permitted",
            })

    return {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "snapshot_timestamp": snapshot_ts,
        "total_supply_onchain": onchain["total_supply"],
        "breaks": breaks,
        "info": info,
    }


def _categorize_balance_break(inv_id, wallet, diff, subs, reds) -> dict:
    """Heuristic categorization of a balance mismatch."""

    # Check for pending subscriptions
    for sub in subs:
        if sub["investor_id"] == inv_id and sub["mint_status"] in ("pending", "blocked"):
            return {
                "label": f"Pending subscription {sub['subscription_id']} — off-chain expects tokens not yet minted",
                "action": "Track SUB instruction status; mint once cleared",
            }

    # Check for pending redemptions
    for red in reds:
        if red["investor_id"] == inv_id and red["burn_status"] in ("queued", "pending"):
            return {
                "label": f"Pending redemption {red['redemption_id']} — burn not yet executed",
                "action": "Execute burn; update off-chain ledger once settled",
            }

    # Fallback
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

    breaks = report["breaks"]
    info   = report["info"]

    # --- Summary -----------------------------------------------------------

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Breaks found:** {len(breaks)}")
    lines.append(f"- **Clean balances:** {sum(1 for i in info if i['type'] == 'BALANCE_OK')}")
    lines.append(f"- **Pending investors:** {sum(1 for i in info if i['type'] == 'INVESTOR_PENDING')}")
    lines.append("")

    if not breaks:
        lines.append("> All balances reconcile. No exceptions.")
        lines.append("")
    else:
        # --- Breaks table --------------------------------------------------

        lines.append("## Exception Details")
        lines.append("")

        for i, brk in enumerate(breaks, 1):
            lines.append(f"### Break #{i} — {brk['type']}")
            lines.append("")

            for k, v in brk.items():
                if k == "type":
                    continue
                label = k.replace("_", " ").title()
                lines.append(f"- **{label}:** {v}")
            lines.append("")

    # --- Clean balances ----------------------------------------------------

    ok_balances = [i for i in info if i["type"] == "BALANCE_OK"]
    if ok_balances:
        lines.append("## Reconciled Balances (No Exceptions)")
        lines.append("")
        lines.append("| Investor | Wallet | Balance |")
        lines.append("|----------|--------|---------|")
        for b in ok_balances:
            short_wallet = b["wallet"][:10] + "…"
            lines.append(f"| {b['investor_id']} | `{short_wallet}` | {b['balance']:,.6f} |")
        lines.append("")

    # --- Pending investors -------------------------------------------------

    pending = [i for i in info if i["type"] == "INVESTOR_PENDING"]
    if pending:
        lines.append("## Pending Investors (Not Yet Approved)")
        lines.append("")
        for p in pending:
            lines.append(f"- **{p['investor_id']}** — {p['name']}: {p['note']}")
        lines.append("")

    # --- Footer ------------------------------------------------------------

    lines.append("---")
    lines.append("")
    lines.append("*This report is auto-generated by `ops/reconcile.py`. "
                 "Breaks should be reviewed and resolved by the fund operations "
                 "team before end of business.*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main():
    print("Running daily reconciliation...\n")

    report  = reconcile()
    md_text = format_report(report)

    # Write report file
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(md_text)

    # Print to console
    print(md_text)
    print(f"\nReport written to {REPORT_OUT.relative_to(REPO_ROOT)}")

    # Exit with non-zero if breaks exist (useful for CI / alerting)
    if report["breaks"]:
        print(f"\n⚠  {len(report['breaks'])} exception(s) require attention.")
        sys.exit(1)
    else:
        print("\n✓  All balances reconcile. No exceptions.")
        sys.exit(0)


if __name__ == "__main__":
    main()
