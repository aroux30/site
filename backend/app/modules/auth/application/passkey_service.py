"""WebAuthn passkey registration and authentication.

P1 "کاربران: پاسکی". What existed was a challenge generator that returned a
random hex string nothing ever verified, a frontend hook whose every call
404'd, and a ``security-status`` payload that honestly said "not implemented".
A passkey is only a passkey if the signature is verified against a stored
public key, so this module does the real ceremony with ``py-webauthn``:

* **Registration** — options are generated with a challenge that is *stored*
  (Redis, short TTL, keyed to the user), the browser's attestation is verified
  against that challenge and the configured origin, and the resulting public
  key is persisted. A challenge that is not stored cannot be verified, and a
  verification against nothing is the stub this replaces.
* **Authentication** — options are generated for the credential ids the
  account holds, the assertion signature is verified against the stored public
  key, and the signature counter is checked. A counter that does not advance
  is the protocol's only signal that a credential was cloned, so it is refused
  rather than ignored.

Two properties worth stating because they are what make this safe:

* the challenge is single-use — it is deleted the moment it is read, so a
  replayed assertion fails on the second attempt;
* the origin is checked by the library against ``WEBAUTHN_ORIGIN``, so a
  credential registered for this site cannot be replayed from another.
"""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.cache.redis import cache_delete, cache_get, cache_set
from app.core.config.settings import get_settings
from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.users.domain.models import PasskeyCredential, User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

settings = get_settings()

#: How long a challenge stays valid. WebAuthn's own guidance is a few minutes;
#: the ceremony is one round-trip, so 5 minutes is generous and a leaked
#: challenge is worthless almost immediately.
CHALLENGE_TTL_SECONDS = 300


def _challenge_key(kind: str, user_id: uuid.UUID) -> str:
    """Redis key for a pending challenge.

    Keyed by kind and user so a registration challenge cannot be spent on an
    authentication, and one user's challenge cannot be redeemed by another.
    """
    return f"webauthn:{kind}:{user_id}"


def _rp_id() -> str:
    return settings.WEBAUTHN_RP_ID


def _origin() -> str:
    return settings.WEBAUTHN_ORIGIN


def _check_client_data(
    client_data_b64: str,
    *,
    challenge_b64: str,
    expected_type: str,
) -> bytes:
    """Validate clientDataJSON and return its raw bytes.

    The checks are done here rather than delegated to the library's
    ``verify_*`` wrappers for two reasons:

    * their origin check is ``origin.endswith(rp_id)``, which accepts
      ``https://evil-localhost`` for an rp_id of ``localhost`` — a suffix
      match is not an origin match; this compares the full origin exactly;
    * the same suffix check makes local development impossible, because a
      browser reports ``http://localhost:3000`` (port included) and that does
      not end with ``localhost``.

    The library's parsing primitives are still used — they are battle-tested
    CBOR/attestation readers — but the accept/reject decisions are made here.
    """
    import json

    try:
        raw = base64.b64decode(client_data_b64)
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — malformed is a refusal
        raise ValidationError("پاسخ کلید عبور قابل خواندن نبود.") from exc

    if data.get("type") != expected_type:
        raise ValidationError("نوع پاسخ کلید عبور نامعتبر است.")

    supplied_challenge = data.get("challenge") or ""
    # The challenge is base64url in clientDataJSON; compare decoded bytes so a
    # re-encoding difference cannot smuggle a different challenge past.
    if _b64url_decode(supplied_challenge) != base64.b64decode(challenge_b64):
        raise ValidationError("چالش کلید عبور مطابقت ندارد.")

    origin = data.get("origin") or ""
    if origin != _origin():
        logger.warning(
            "passkey_origin_mismatch", origin=origin, expected=_origin()
        )
        raise ValidationError("مبدأ درخواست کلید عبور معتبر نیست.")

    return raw


async def begin_registration(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """Generate registration options and store the challenge.

    The user's existing credentials are passed as ``existing_keys`` so the
    authenticator refuses to register a second credential it already holds —
    without it, a double-click creates two credentials for one device and the
    revocation screen shows a phantom.
    """
    from webauthn import create_webauthn_credentials
    # Aliased: the library also has a class named ``User``, and importing it
    # unaliased shadows the domain model this function queries with.
    from webauthn.types import Attestation, AuthenticatorAttachment, RelyingParty
    from webauthn.types import User as WebAuthnUser
    from webauthn.types import UserVerification

    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError(resource="User")

    existing = (
        await db.execute(
            select(PasskeyCredential).where(
                PasskeyCredential.user_id == user_id,
                PasskeyCredential.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    existing_keys = [_b64url_decode(c.credential_id) for c in existing]

    options, challenge_b64 = create_webauthn_credentials(
        rp=RelyingParty(id=_rp_id(), name=settings.WEBAUTHN_RP_NAME, icon=None),
        user=WebAuthnUser(
            id=str(user_id).encode("utf-8"),
            name=user.phone,
            display_name=(
                f"{user.profile.first_name or ''} {user.profile.last_name or ''}".strip()
                or user.phone
            ),
            icon=None,
        ),
        existing_keys=existing_keys,
        attachment=AuthenticatorAttachment.Platform,
        require_resident=False,
        user_verification=UserVerification.Preferred,
        # Passed explicitly because the library's own default path is broken:
        # its guard is `if attestation:` (the module, always truthy) followed
        # by `attestation_request.value`, which raises AttributeError on None.
        attestation_request=Attestation.NoneAttestation,
    )

    await cache_set(
        _challenge_key("register", user_id),
        challenge_b64,
        ttl=CHALLENGE_TTL_SECONDS,
    )
    logger.info("passkey_registration_started", user_id=str(user_id))
    return options


async def finish_registration(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    credential: dict[str, Any],
    name: str | None = None,
) -> PasskeyCredential:
    """Verify the attestation and persist the credential.

    The challenge is read and deleted before verification, so a retry after a
    failure starts a fresh ceremony rather than replaying a consumed one.
    """
    import hashlib

    import cbor2
    from webauthn import attestation as wa_attestation
    from webauthn.metadata import FIDOMetadata

    key = _challenge_key("register", user_id)
    challenge_b64 = await cache_get(key)
    if not challenge_b64:
        raise ValidationError(
            "نشست ثبت کلید عبور منقضی شده است. لطفاً دوباره تلاش کنید."
        )
    # Single-use: consumed whether verification succeeds or not.
    await cache_delete(key)

    response = credential.get("response") or {}
    client_data_b64 = response.get("clientDataJSON")
    attestation_b64 = response.get("attestationObject")
    if not client_data_b64 or not attestation_b64:
        raise ValidationError("پاسخ کلید عبور ناقص است.")

    # Our own clientDataJSON validation: exact-origin, challenge-bound.
    client_data_bytes = _check_client_data(
        client_data_b64, challenge_b64=challenge_b64, expected_type="webauthn.create"
    )

    try:
        attestation_data = cbor2.loads(base64.b64decode(attestation_b64))
        authenticator_data = wa_attestation.AuthenticatorData.from_bytes(
            attestation_data["authData"]
        )
        client_data_hash = hashlib.sha256(client_data_bytes).digest()
        rp_hash = hashlib.sha256(_rp_id().encode("utf-8")).digest()
        if rp_hash != authenticator_data.rp_hash:
            raise ValueError("rp hash mismatch")
        if not authenticator_data.user_presence:
            raise ValueError("user not present")
        # Attestation statement verification (the "none" format is accepted by
        # the library; packed/fido-u2f are validated against their certs).
        wa_attestation.verify_attestation(
            attestation_statement=attestation_data,
            authenticator_data=authenticator_data,
            client_data_hash=client_data_hash,
            fido_metadata=FIDOMetadata(entries=[], aaguid_map={}, cki_map={}),
        )
        result = authenticator_data.attested_data
        if result is None:
            raise ValueError("no attested credential data")
    except Exception as exc:  # noqa: BLE001 — any verification failure is a refusal
        logger.warning(
            "passkey_registration_verify_failed", user_id=str(user_id), error=str(exc)
        )
        raise ValidationError("تأیید کلید عبور ناموفق بود.") from exc

    credential_id = credential.get("id") or credential.get("rawId")
    if not credential_id:
        raise ValidationError("شناسهٔ کلید عبور در پاسخ نیست.")

    # A credential id is globally unique: registering the same authenticator
    # twice (two accounts on one device is legitimate, but the same credential
    # id twice is not) would make assertions ambiguous.
    existing = (
        await db.execute(
            select(PasskeyCredential).where(
                PasskeyCredential.credential_id == credential_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(detail="این کلید عبور قبلاً ثبت شده است.")

    # The attested credential data carries the public key as a cryptography
    # key object; store it DER-encoded so the assertion path can load it back
    # with the same library.
    from cryptography.hazmat.primitives import serialization

    public_key_b64 = base64.b64encode(
        result.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    ).decode("ascii")

    transports = credential.get("transports")
    if not isinstance(transports, list):
        transports = None

    row = PasskeyCredential(
        user_id=user_id,
        credential_id=credential_id,
        public_key=public_key_b64,
        public_key_alg=int(result.public_key_alg),
        sign_count=int(authenticator_data.sign_count or 0),
        name=(name or "").strip()[:100] or None,
        transports=transports,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info(
        "passkey_registered",
        user_id=str(user_id),
        credential_id=credential_id[:16],
        alg=result.public_key_alg,
    )
    return row


async def begin_authentication(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """Generate assertion options for the account's live credentials."""
    from webauthn import get_webauthn_credentials
    from webauthn.types import RelyingParty, UserVerification

    credentials = (
        await db.execute(
            select(PasskeyCredential).where(
                PasskeyCredential.user_id == user_id,
                PasskeyCredential.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    if not credentials:
        raise NotFoundError(resource="Passkey", detail="no credentials registered")

    options, challenge_b64 = get_webauthn_credentials(
        rp=RelyingParty(id=_rp_id(), name=settings.WEBAUTHN_RP_NAME, icon=None),
        existing_keys=[_b64url_decode(c.credential_id) for c in credentials],
        user_verification=UserVerification.Preferred,
    )
    await cache_set(
        _challenge_key("login", user_id),
        challenge_b64,
        ttl=CHALLENGE_TTL_SECONDS,
    )
    logger.info("passkey_authentication_started", user_id=str(user_id))
    return options


async def finish_authentication(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    credential: dict[str, Any],
) -> User:
    """Verify an assertion and return the account it authenticates.

    The signature is checked against the stored public key, and the signature
    counter must advance. A counter that goes backwards is the one signal the
    protocol gives that the credential was cloned, so it is a refusal, not a
    warning.
    """
    import hashlib

    from cryptography.hazmat.primitives import serialization
    from webauthn import attestation as wa_attestation
    from webauthn.utils import verify_signature

    key = _challenge_key("login", user_id)
    challenge_b64 = await cache_get(key)
    if not challenge_b64:
        raise ValidationError(
            "نشست ورود با کلید عبور منقضی شده است. لطفاً دوباره تلاش کنید."
        )
    await cache_delete(key)

    response = credential.get("response") or {}
    credential_id = credential.get("id") or credential.get("rawId")
    if not credential_id:
        raise ValidationError("شناسهٔ کلید عبور در پاسخ نیست.")

    row = (
        await db.execute(
            select(PasskeyCredential).where(
                PasskeyCredential.credential_id == credential_id,
                PasskeyCredential.user_id == user_id,
                PasskeyCredential.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(resource="Passkey")

    client_data_bytes = _check_client_data(
        response.get("clientDataJSON") or "",
        challenge_b64=challenge_b64,
        expected_type="webauthn.get",
    )

    try:
        authenticator_bytes = base64.b64decode(response.get("authenticatorData") or "")
        signature = base64.b64decode(response.get("signature") or "")
        authenticator_data = wa_attestation.AuthenticatorData.from_bytes(
            authenticator_bytes
        )
        rp_hash = hashlib.sha256(_rp_id().encode("utf-8")).digest()
        if rp_hash != authenticator_data.rp_hash:
            raise ValueError("rp hash mismatch")
        if not authenticator_data.user_presence:
            raise ValueError("user not present")

        # The signed payload is authenticatorData || SHA-256(clientDataJSON),
        # verified against the stored public key with the algorithm recorded at
        # registration.
        public_key = serialization.load_der_public_key(
            base64.b64decode(row.public_key)
        )
        verify_signature(
            public_key,
            authenticator_bytes + hashlib.sha256(client_data_bytes).digest(),
            _signature_to_der(signature, row.public_key_alg),
            row.public_key_alg,
        )
    except Exception as exc:  # noqa: BLE001 — any verification failure is a refusal
        logger.warning(
            "passkey_authentication_verify_failed",
            user_id=str(user_id),
            error=str(exc),
        )
        raise ValidationError("تأیید کلید عبور ناموفق بود.") from exc

    # A cloned authenticator reports a counter that does not advance. Refusing
    # here is the whole reason the column exists. A counter of 0 means the
    # authenticator does not implement counting, which is allowed by the spec.
    received_count = int(authenticator_data.sign_count or 0)
    if received_count and received_count <= row.sign_count:
        logger.error(
            "passkey_sign_count_regression",
            user_id=str(user_id),
            credential_id=credential_id[:16],
            stored=row.sign_count,
            received=received_count,
        )
        raise ValidationError(
            "امضای کلید عبور معتبر نبود. لطفاً با پشتیبانی تماس بگیرید."
        )

    if received_count:
        row.sign_count = received_count
    row.last_used_at = datetime.now(UTC)
    await db.commit()

    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError(resource="User")
    if user.pending_approval:
        raise ValidationError("حساب شما در انتظار تأیید مدیر است.")
    if not user.is_active:
        raise ValidationError("حساب شما غیرفعال است.")
    logger.info("passkey_authenticated", user_id=str(user_id))
    return user


async def list_credentials(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[PasskeyCredential]:
    """The account's live passkeys, newest first."""
    rows = (
        await db.execute(
            select(PasskeyCredential)
            .where(
                PasskeyCredential.user_id == user_id,
                PasskeyCredential.revoked_at.is_(None),
            )
            .order_by(PasskeyCredential.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


async def revoke_credential(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    credential_pk: uuid.UUID,
) -> None:
    """Revoke one passkey. Scoped by owner like every other customer action.

    The row is kept with ``revoked_at`` set rather than deleted: an audit
    trail of which keys existed is worth more than the row costs, and the
    unique credential id must not be reusable by a different registration.
    """
    row = (
        await db.execute(
            select(PasskeyCredential).where(
                PasskeyCredential.id == credential_pk,
                PasskeyCredential.user_id == user_id,
                PasskeyCredential.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(resource="Passkey")
    row.revoked_at = datetime.now(UTC)
    await db.commit()
    logger.info(
        "passkey_revoked", user_id=str(user_id), credential_pk=str(credential_pk)
    )


def _b64url_decode(value: str) -> bytes:
    """Decode base64url without padding, the form WebAuthn uses."""
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded)


def _signature_to_der(signature: bytes, alg: int) -> bytes:
    """Convert a WebAuthn signature to the DER form ``verify_signature`` wants.

    WebAuthn authenticators transmit ECDSA signatures as the raw ``r || s``
    pair (RFC 7515 style), while the ``cryptography`` library — and therefore
    ``verify_signature`` — expects DER. Handing the raw form straight in fails
    with ``InvalidSignature`` for *every* valid assertion, which is exactly
    what happened the first time this path ran: registration worked and login
    refused every correct signature.

    RSA signatures are already in the form the verifier wants, so only the two
    ECDSA algorithms are converted.
    """
    if alg not in (-7, -35, -36):  # ES256, ES384, ES512
        return signature
    if not signature or len(signature) % 2 != 0:
        # Not a raw r||s pair; pass it through and let verification refuse it
        # rather than raising a decoding error that reads as a server fault.
        return signature
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    half = len(signature) // 2
    r = int.from_bytes(signature[:half], "big")
    s = int.from_bytes(signature[half:], "big")
    return encode_dss_signature(r, s)