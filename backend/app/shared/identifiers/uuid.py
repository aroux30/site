"""UUID generation utilities.

Centralises UUID creation so that the project consistently uses UUIDv4 and
callers can easily switch to UUIDv7 (time-ordered) in the future.
"""

from __future__ import annotations

import uuid


def generate_uuid() -> uuid.UUID:
    """Generate a new random UUID (version 4)."""
    return uuid.uuid4()


def generate_prefixed_id(prefix: str) -> str:
    """Return a human-friendly prefixed identifier.

    Examples::

        >>> generate_prefixed_id("ord")
        'ord_a1b2c3d4e5f6...'
        >>> generate_prefixed_id("usr")
        'usr_...'

    Useful for external-facing IDs where the prefix hints at the entity type.
    """
    return f"{prefix}_{uuid.uuid4().hex}"


def is_valid_uuid(value: str) -> bool:
    """Check whether *value* is a valid UUID string."""
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return True


def uuid_from_str(value: str) -> uuid.UUID:
    """Parse a UUID from its string representation.

    Raises ``ValueError`` if *value* is not a valid UUID.
    """
    return uuid.UUID(value)
