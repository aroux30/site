"""Cryptographic utilities for digital goods inventory (Karta Phase 1/2).

Provides:
- AES-256-GCM symmetric encryption / decryption for PINs, credentials and
  serials (Karta ``card_encrypt`` / ``card_decrypt``)
- SHA-256 deterministic hashing for duplicate detection (Karta ``card_hash``)
- Key management sourced from application settings with an explicit
  rotation path: the active key encrypts everything new; decryption
  transparently accepts keys listed in ``DIGITAL_CARDS_PREVIOUS_KEYS`` so
  operators can rotate without downtime, then run the re-encrypt sweep
  (``reencrypt_all_cards``) to move every payload onto the active key.

Plaintext never reaches the database, the logs, or error messages.
"""

from __future__ import annotations

import base64
import hashlib
import os

import structlog
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config.settings import get_settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_NONCE_LEN = 12


def _decode_key(key_str: str) -> bytes | None:
    """Decode a base64 (or raw) key string into 32 key bytes, or None."""
    candidate = key_str.strip()
    if not candidate or candidate.startswith("CHANGE-ME"):
        return None
    try:
        decoded = base64.b64decode(candidate)
        if len(decoded) == 32:
            return decoded
        return hashlib.sha256(decoded).digest()
    except Exception:
        return hashlib.sha256(candidate.encode()).digest()


def _active_key_bytes() -> bytes:
    """Retrieve the active 32-byte AES key from settings.

    In production a missing/placeholder key is a hard configuration error —
    silently encrypting inventory with a publicly-known dev key would be
    worse than failing to boot.
    """
    settings = get_settings()
    key_str = settings.DIGITAL_CARDS_ENCRYPTION_KEY.strip()

    key = _decode_key(key_str)
    if key is not None:
        return key

    if settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "DIGITAL_CARDS_ENCRYPTION_KEY must be set to a strong base64 key in production"
        )

    # Deterministic fallback for test/dev environments only.
    return hashlib.sha256(b"ecom-digital-cards-default-dev-key").digest()


def _previous_key_bytes() -> list[bytes]:
    """Decode the rotation history: keys that may still decrypt old payloads."""
    settings = get_settings()
    keys: list[bytes] = []
    for part in (settings.DIGITAL_CARDS_PREVIOUS_KEYS or "").split(","):
        decoded = _decode_key(part)
        if decoded is not None:
            keys.append(decoded)
    return keys


def compute_card_hash(pin: str, serial: str | None = None) -> str:
    """Compute deterministic SHA-256 hash for deduplication (Karta ``card_hash``).

    Normalises whitespace and case to ensure reliable duplicate detection.
    """
    clean_pin = pin.strip()
    clean_serial = (serial or "").strip()
    composite = f"{clean_pin}|{clean_serial}".encode()
    return hashlib.sha256(composite).hexdigest()


def encrypt_pin(pin: str) -> str:
    """Encrypt plaintext PIN / credential / serial using AES-256-GCM.

    Returns base64-encoded payload containing: 12-byte nonce + ciphertext + 16-byte tag.
    """
    key = _active_key_bytes()
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_LEN)  # Standard 96-bit nonce for GCM
    data = pin.strip().encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_pin(ciphertext_payload: str) -> str:
    """Decrypt an AES-256-GCM payload and return the plaintext.

    Tries the active key first, then the configured rotation history
    (``DIGITAL_CARDS_PREVIOUS_KEYS``). Raises ValueError if ciphertext is
    corrupted, tampered with, or no configured key matches.
    """
    try:
        raw = base64.b64decode(ciphertext_payload.strip())
        nonce = raw[:_NONCE_LEN]
        ciphertext = raw[_NONCE_LEN:]
    except Exception as exc:
        raise ValueError("Decryption failed: corrupted ciphertext") from exc

    for key in [_active_key_bytes(), *_previous_key_bytes()]:
        try:
            decrypted = AESGCM(key).decrypt(nonce, ciphertext, None)
            return decrypted.decode("utf-8")
        except Exception:
            logger.debug("decrypt_key_rotation_miss", action="decrypt_pin")
            continue

    raise ValueError("Decryption failed: corrupted ciphertext or invalid key")


# Serials use the same AES-256-GCM scheme; explicit aliases document intent.
encrypt_serial = encrypt_pin
decrypt_serial = decrypt_pin
