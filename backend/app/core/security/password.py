"""Password hashing using Argon2id.

Argon2id is the recommended password hashing algorithm per OWASP.  We use
``passlib`` with the ``argon2-cffi`` backend.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__rounds=4,  # time cost
    argon2__memory_cost=65536,  # 64 MiB
    argon2__parallelism=2,
)


def hash_password(plain: str) -> str:
    """Return an Argon2id hash of *plain*."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify *plain* against *hashed*.  Returns ``True`` on match."""
    return _pwd_context.verify(plain, hashed)


def needs_rehash(hashed: str) -> bool:
    """Check if the hash was created with outdated parameters."""
    return _pwd_context.needs_update(hashed)


# Precomputed constant Argon2id hash used to prevent side-channel timing attacks (User Enumeration)
DUMMY_ARGON2_HASH: str = "$argon2id$v=19$m=65536,t=4,p=2$DaG0FiIkZIyRcq61NkYIAQ$I0I+pUDPMvwKf0NN/02w2rmsabIO4N6UP6OhpCpM8U4"  # noqa: E501


def verify_dummy_password(plain: str) -> bool:
    """Perform constant-time Argon2id computation to neutralize timing-based user enumeration."""
    return verify_password(plain, DUMMY_ARGON2_HASH)


# ── OWASP Breached & Common Password Protection ──────────────────────────────

_COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "12345678",
        "123456789",
        "1234567890",
        "password",
        "password123",
        "pass1234",
        "admin123",
        "admin1234",
        "qwertyuiop",
        "asdfghjkl",
        "iran1234",
        "iran12345",
        "tehran123",
        "guest1234",
        "welcome123",
        "iloveyou123",
        "superman123",
        "dragon123",
        "football123",
        "monkey123",
        "master123",
        "trustnoone",
    }
)


def is_weak_password(password: str) -> bool:
    """Return True if password matches common dictionary attacks or predictable patterns."""
    clean = password.strip().lower()
    if clean in _COMMON_PASSWORDS:
        return True
    # Detect repeated characters such as "aaaaaaaa" or "11111111"
    return bool(len(clean) >= 8 and len(set(clean)) <= 2)
