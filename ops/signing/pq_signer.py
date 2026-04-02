"""
PQ artifact signing and verification using ML-DSA-65.

Each operational approval (wallet, subscription, redemption) is represented
as a JSON artifact.  This module:

  1. Canonicalizes the artifact (deterministic JSON serialization).
  2. Signs the canonical bytes with ML-DSA-65.
  3. Verifies signatures against the ops-authority public key.

Signatures are stored as detached hex files in signatures/.
"""

import hashlib
import json
from pathlib import Path

from pqcrypto.sign.ml_dsa_65 import sign, verify


class PQSigner:
    """Sign and verify JSON approval artifacts with ML-DSA-65."""

    # ------------------------------------------------------------------
    #  Canonical form
    # ------------------------------------------------------------------

    @staticmethod
    def canonicalize(artifact: dict) -> bytes:
        """Deterministic JSON serialization (sorted keys, compact separators)."""
        return json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def artifact_hash(artifact: dict) -> str:
        """SHA-256 hex digest of the canonical artifact."""
        return hashlib.sha256(PQSigner.canonicalize(artifact)).hexdigest()

    # ------------------------------------------------------------------
    #  Sign / verify
    # ------------------------------------------------------------------

    @staticmethod
    def sign_artifact(artifact: dict, secret_key: bytes) -> str:
        """Sign a JSON artifact; return the signature as a hex string."""
        msg = PQSigner.canonicalize(artifact)
        sig = sign(secret_key, msg)
        return sig.hex()

    @staticmethod
    def verify_artifact(artifact: dict, signature_hex: str, public_key: bytes) -> bool:
        """Verify a detached signature against a JSON artifact.

        Returns True on success, False on failure.
        """
        msg = PQSigner.canonicalize(artifact)
        sig = bytes.fromhex(signature_hex)
        try:
            return verify(public_key, msg, sig)
        except Exception:
            return False

    # ------------------------------------------------------------------
    #  File I/O helpers
    # ------------------------------------------------------------------

    @staticmethod
    def save_signature(sig_hex: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sig_hex)

    @staticmethod
    def load_signature(path: Path) -> str:
        return path.read_text().strip()
