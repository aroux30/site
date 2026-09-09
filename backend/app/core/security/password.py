"""Password hashing using Argon2id.

Argon2id is the recommended password hashing algorithm per OWASP.  We use
``passlib`` with the ``argon2-cffi`` backend.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__rounds=4,          # time cost
    argon2__memory_cost=65536, # 64 MiB
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
