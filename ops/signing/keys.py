"""
Key management for ML-DSA-65 post-quantum signing.

Handles keypair generation, persistence, and loading.  Keys are stored as
hex-encoded files:

    data/keys/ops_authority.pub   (public key — committed to repo)
    data/keys/ops_authority.key   (secret key — excluded via .gitignore)

In production the secret key would live in an HSM or vault; here it is a
local file for demo purposes.
"""

import hashlib
from pathlib import Path

from pqcrypto.sign.ml_dsa_65 import generate_keypair


class KeyManager:
    """Generate, store, and load ML-DSA-65 keypairs."""

    def __init__(self, keys_dir: Path):
        self.keys_dir = keys_dir
        self.pub_path = keys_dir / "ops_authority.pub"
        self.key_path = keys_dir / "ops_authority.key"

    # ------------------------------------------------------------------
    #  Keypair lifecycle
    # ------------------------------------------------------------------

    def keypair_exists(self) -> bool:
        return self.pub_path.exists() and self.key_path.exists()

    def generate(self) -> tuple[bytes, bytes]:
        """Generate a fresh ML-DSA-65 keypair and persist to disk."""
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        pk, sk = generate_keypair()
        self.pub_path.write_text(pk.hex())
        self.key_path.write_text(sk.hex())
        return pk, sk

    def load_public_key(self) -> bytes:
        return bytes.fromhex(self.pub_path.read_text().strip())

    def load_secret_key(self) -> bytes:
        return bytes.fromhex(self.key_path.read_text().strip())

    def load_keypair(self) -> tuple[bytes, bytes]:
        return self.load_public_key(), self.load_secret_key()

    def ensure_keypair(self) -> tuple[bytes, bytes]:
        """Load existing keypair or generate a new one."""
        if self.keypair_exists():
            return self.load_keypair()
        return self.generate()

    # ------------------------------------------------------------------
    #  Utility
    # ------------------------------------------------------------------

    @staticmethod
    def public_key_hash(pk: bytes) -> str:
        """SHA-256 fingerprint of the public key (hex, first 16 chars)."""
        return hashlib.sha256(pk).hexdigest()[:16]
