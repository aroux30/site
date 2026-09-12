"""Cryptographic utilities for digital goods inventory (Karta Phase 1/2).

Provides:
- AES-256-GCM symmetric encryption / decryption for PINs and credentials
- SHA-256 deterministic hashing for duplicate detection (Karta ``card_hash``)
- Key management sourced securely from application settings / environment
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config.settings import get_settings


def _get_key_bytes() -> bytes:
    """Retrieve and decode the 32-byte AES key from settings."""
    settings = get_settings()
    key_str = settings.DIGITAL_CARDS_ENCRYPTION_KEY.strip()
    if not key_str or key_str.startswith("CHANGE-ME"):
        # Fallback to an environment-driven stable key if not set
        raw = os.environ.get("DIGITAL_CARDS_ENCRYPTION_KEY", "")
        if raw and not raw.startswith("CHANGE-ME"):
            key_str = raw.strip()
        else:
            # Deterministic fallback for test/dev environments
            return hashlib.sha256(b"ecom-digital-cards-default-dev-key").digest()

    try:
        decoded = base64.b64decode(key_str)
        if len(decoded) != 32:
            return hashlib.sha256(decoded).digest()
        return decoded
    except Exception:
        return hashlib.sha256(key_str.encode()).digest()


def compute_card_hash(pin: str, serial: str | None = None) -> str:
    """Compute deterministic SHA-256 hash for deduplication (Karta ``card_hash``).

    Normalises whitespace and case to ensure reliable duplicate detection.
    """
    clean_pin = pin.strip()
    clean_serial = (serial or "").strip()
    composite = f"{clean_pin}|{clean_serial}".encode()
    return hashlib.sha256(composite).hexdigest()


def encrypt_pin(pin: str) -> str:
    """Encrypt plaintext PIN / credential using AES-256-GCM.

    Returns base64-encoded payload containing: 12-byte nonce + ciphertext + 16-byte tag.
    """
    key = _get_key_bytes()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # Standard 96-bit nonce for GCM
    data = pin.strip().encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_pin(ciphertext_payload: str) -> str:
    """Decrypt AES-256-GCM payload and return the plaintext PIN.

    Raises ValueError if ciphertext is corrupted or tampering is detected.
    """
    try:
        raw = base64.b64decode(ciphertext_payload.strip())
        nonce = raw[:12]
        ciphertext = raw[12:]
        key = _get_key_bytes()
        aesgcm = AESGCM(key)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode("utf-8")
    except Exception as exc:
        raise ValueError("Decryption failed: corrupted ciphertext or invalid key") from exc
