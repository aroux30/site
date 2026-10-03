"""Application passwords: mint, verify, revoke (WordPress parity).

A client authenticates with ``Authorization: Bearer <token>`` where the token
is an application password rather than a JWT. Verification is deliberately
constant-ish: the row is found by the token's SHA-256, so a wrong token costs
one indexed lookup and reveals nothing about whether a prefix exists.

Security properties this module is responsible for:

* the plaintext secret exists only in the creation response;
* a revoked or expired credential stops working immediately, without waiting
  for any TTL, because the check is against the row on every request;
* last-use is recorded, so a user can see a credential they forgot about;
* OTP-only accounts (no ``password_hash``) may still hold an application
  password — the credential *is* their login for API use.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.users.domain.models import ApplicationPassword

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Secrets are 24 random characters: ~140 bits, so guessing is not a concern
#: even with no lockout.
TOKEN_BYTES = 24
TOKEN_PREFIX_LEN = 8
DEFAULT_VALIDITY_DAYS = 365
#: WordPress treats an application password with no expiry as valid forever.
#: A year is the friendlier default here: a forgotten credential that never
#: expires is a permanent hole the user cannot see.


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _mint() -> tuple[str, str, str]:
    """Return ``(plaintext, prefix, hash)``.

    The prefix is a separate random run rather than a slice of the secret, so
    the visible characters are not a prefix of the actual credential — a
    stored prefix must not narrow a brute force.
    """
    plaintext = secrets.token_urlsafe(TOKEN_BYTES)
    prefix = secrets.token_urlsafe(TOKEN_PREFIX_LEN)[:12]
    return plaintext, prefix, _hash_token(plaintext)


async def create_application_password(
    db: "AsyncSession",
    *,
    user_id: uuid.UUID,
    name: str,
    scopes: list[str] | None = None,
    expires_in_days: int | None = DEFAULT_VALIDITY_DAYS,
) -> tuple[ApplicationPassword, str]:
    """Create a credential. Returns the row and the one-time plaintext.

    The plaintext is not recoverable afterwards — only its hash is stored — so
    the caller must show it exactly once.
    """
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValidationError(detail="برای رمز برنامه یک نام لازم است")
    if expires_in_days is not None and not (1 <= expires_in_days <= 3650):
        raise ValidationError(detail="مدت اعتبار باید بین ۱ تا ۳۶۵۰ روز باشد")

    plaintext, prefix, token_hash = _mint()
    row = ApplicationPassword(
        user_id=user_id,
        name=clean_name[:100],
        token_prefix=prefix,
        token_hash=token_hash,
        scopes=scopes or [],
        expires_at=(
            datetime.now(UTC) + timedelta(days=expires_in_days)
            if expires_in_days
            else None
        ),
    )
    db.add(row)
    await db.flush()
    await logger.ainfo(
        "application_password_created", user_id=str(user_id), name=clean_name
    )
    return row, plaintext


async def verify_application_password(
    db: "AsyncSession",
    token: str,
    *,
    ip_address: str | None = None,
) -> dict[str, Any] | None:
    """Resolve a presented application password to a token payload.

    Returns the same shape ``get_current_user`` produces, so downstream
    handlers are unchanged whether the caller authenticated with a JWT or an
    application password. ``None`` means "not a valid application password",
    which is not itself an error — the caller may still want to try a JWT.
    """
    if not token:
        return None

    stmt = select(ApplicationPassword).where(
        ApplicationPassword.token_hash == _hash_token(token)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None

    now = datetime.now(UTC)
    if not row.is_active or row.revoked_at is not None:
        logger.info("application_password_rejected", reason="revoked", user_id=str(row.user_id))
        return None
    if row.expires_at is not None and row.expires_at <= now:
        logger.info("application_password_rejected", reason="expired", user_id=str(row.user_id))
        return None

    row.last_used_at = now
    row.last_used_ip = (ip_address or "")[:45] or None
    # No commit here: the request that authenticated is not the transaction's
    # owner, and a failure to record usage must never fail the request. The
    # update rides along on the caller's own commit when there is one.
    await db.flush()

    return {
        "sub": str(row.user_id),
        # Marks the payload so a handler can tell the two auth paths apart.
        "auth_method": "application_password",
        "app_password_id": str(row.id),
        "scopes": list(row.scopes or []),
        "type": "application",
    }


def has_scope(payload: dict[str, Any], required: str) -> bool:
    """Whether a token payload permits ``required``.

    An application password with an empty scope list has full access (the
    WordPress default). A non-empty list is a strict allow-list: anything not
    named is refused, so adding a scope later cannot silently widen access.
    JWTs carry no scopes and are not restricted by this function.
    """
    if payload.get("auth_method") != "application_password":
        return True
    scopes = payload.get("scopes") or []
    if not scopes:
        return True
    return required in scopes or "*" in scopes


async def list_application_passwords(
    db: "AsyncSession", *, user_id: uuid.UUID
) -> list[ApplicationPassword]:
    """The user's credentials, newest first, revocations included.

    A revoked row stays visible: hiding it would make the list look like the
    credential was never created, and a user comparing against a note they
    wrote months ago would be more confused, not less.
    """
    stmt = (
        select(ApplicationPassword)
        .where(ApplicationPassword.user_id == user_id)
        .order_by(ApplicationPassword.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def revoke_application_password(
    db: "AsyncSession", *, user_id: uuid.UUID, app_password_id: uuid.UUID
) -> ApplicationPassword:
    """Deactivate a credential. Scoped to the owner so one user cannot revoke another's."""
    row = (
        await db.execute(
            select(ApplicationPassword).where(
                ApplicationPassword.id == app_password_id,
                ApplicationPassword.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(
            "ApplicationPassword", f"Application password '{app_password_id}' not found"
        )
    row.is_active = False
    row.revoked_at = datetime.now(UTC)
    await db.flush()
    await logger.ainfo(
        "application_password_revoked",
        user_id=str(user_id),
        app_password_id=str(app_password_id),
    )
    return row


# ── Admin side (another user's credentials) ─────────────────────────────────


async def list_application_passwords_admin(
    db: "AsyncSession", *, target_user_id: uuid.UUID
) -> list[ApplicationPassword]:
    """A target account's credentials, for an operator's review.

    P2 "REST: مدیریت Application Password کاربر دیگر". A support case about a
    leaked token used to end with "ask the user to revoke it themselves" —
    an operator could neither see which credentials existed nor cut one off.

    The target is named explicitly, never taken from the session: every
    owner-scoped function above derives the user from the token, and this one
    must not, or the "admin" path would be indistinguishable from self-service
    and an operator could not actually help anybody.
    """
    stmt = (
        select(ApplicationPassword)
        .where(ApplicationPassword.user_id == target_user_id)
        .order_by(ApplicationPassword.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def revoke_application_password_admin(
    db: "AsyncSession",
    *,
    target_user_id: uuid.UUID,
    app_password_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> ApplicationPassword:
    """Revoke one of a target account's credentials, at an operator's request.

    The row is scoped by ``target_user_id`` as well as the credential id, so
    an operator cannot revoke a credential belonging to a different account by
    guessing its id — the same owner predicate the self-service revoke uses,
    with the owner supplied by the route instead of the session.

    ``actor_id`` is recorded so a forced revocation is attributable: a token
    that stops working with no record of who ended it is not a support action,
    it is a mystery. The admin never receives the secret — only a hash is
    stored, and this returns the row, whose response model has no token field.
    """
    row = (
        await db.execute(
            select(ApplicationPassword).where(
                ApplicationPassword.id == app_password_id,
                ApplicationPassword.user_id == target_user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(
            "ApplicationPassword", f"Application password '{app_password_id}' not found"
        )
    row.is_active = False
    row.revoked_at = datetime.now(UTC)
    await db.flush()
    await logger.ainfo(
        "application_password_revoked_by_admin",
        target_user_id=str(target_user_id),
        app_password_id=str(app_password_id),
        actor_id=str(actor_id),
    )
    return row


async def revoke_all_application_passwords(
    db: "AsyncSession", *, user_id: uuid.UUID
) -> int:
    """Revoke every credential for a user. Returns how many were live."""
    rows = await list_application_passwords(db, user_id=user_id)
    now = datetime.now(UTC)
    count = 0
    for row in rows:
        if row.is_active and row.revoked_at is None:
            row.is_active = False
            row.revoked_at = now
            count += 1
    await db.flush()
    await logger.ainfo(
        "application_passwords_revoked_all", user_id=str(user_id), count=count
    )
    return count
