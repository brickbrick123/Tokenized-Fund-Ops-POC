"""
Post-quantum signing infrastructure for off-chain operational approvals.

Uses ML-DSA-65 (NIST FIPS 204, formerly CRYSTALS-Dilithium) via the pqcrypto
library.  All on-chain transactions remain classical ECDSA — this module
secures the off-chain approval artifacts that authorize those transactions.
"""

from ops.signing.keys import KeyManager
from ops.signing.pq_signer import PQSigner

__all__ = ["KeyManager", "PQSigner"]
