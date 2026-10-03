"""SSO/OIDC login (Google first): state→callback flow that lands on the
existing ``_create_token_pair`` so sessions, permissions and audit logging
behave exactly like password/OTP logins.

Design notes:
- The OAuth ``state`` parameter is stored server-side in Redis (5 min TTL)
  bound to the provider, so callbacks cannot be replayed or cross-injected.
- The provider's ``id_token`` is verified against Google's JWKS via httpx —
  signature, issuer, audience and expiry are all checked before trusting the
  embedded email.
- Users are matched by verified email; a new user is provisioned (phone is a
  placeholder until the user completes their profile) only when the provider
  asserts ``email_verified``.
"""

from __future__ import annotations

import base64
import json
import secrets
import time
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import UnauthorizedError, ValidationError
from app.modules.users.domain.models import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

STATE_TTL_SECONDS = 300
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"


def _cfg() -> tuple[str, str, str]:
    s = get_settings()
    client_id = getattr(s, "GOOGLE_OAUTH_CLIENT_ID", "") or ""
    client_secret = getattr(s, "GOOGLE_OAUTH_CLIENT_SECRET", "") or ""
    redirect_uri = getattr(s, "GOOGLE_OAUTH_REDIRECT_URI", "") or ""
    return client_id, client_secret, redirect_uri


def google_sso_configured() -> bool:
    # Token exchange also needs the secret — a partial config shows the login
    # button then fails after Google redirects back.
    client_id, client_secret, redirect_uri = _cfg()
    return bool(client_id and client_secret and redirect_uri)


def _sso_phone_placeholder() -> str:
    """A unique, always-valid placeholder for an SSO-provisioned account.

    ``phone`` is ``varchar(15)`` and is this platform's unique login
    identifier, so an SSO account needs one. The width is read from the column
    rather than hardcoded, so a future migration widening or narrowing it does
    not silently reintroduce the overflow that made every new Google sign-in
    fail on the flush.
    """
    from app.modules.users.domain.models import User

    prefix = "sso-"
    try:
        width = User.__table__.c.phone.type.length or 15
    except Exception:  # pragma: no cover - only if the column is unmapped
        width = 15
    room = max(1, int(width) - len(prefix))
    return f"{prefix}{uuid.uuid4().hex[:room]}"


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _safe_return_url(raw: str | None) -> str:
    """Only same-origin paths are allowed (no protocol-relative or absolute URLs)."""
    if raw and raw.startswith("/") and not raw.startswith("//"):
        return raw[:500]
    return "/account"


async def start_google_login(return_url: str | None = None) -> str:
    """Build the Google consent URL with a server-side stored state nonce."""
    client_id, _, redirect_uri = _cfg()
    if not client_id or not redirect_uri:
        raise ValidationError(
            detail="ورود با گوگل برای این فروشگاه پیکربندی نشده است",
            error_code="SSO_NOT_CONFIGURED",
        )
    state = secrets.token_urlsafe(24)
    from app.core.cache.redis import cache_set

    # The value doubles as the post-login return URL ("google|<return>").
    await cache_set(f"sso:state:{state}", f"google|{_safe_return_url(return_url)}", ttl=STATE_TTL_SECONDS)
    from urllib.parse import urlencode

    params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return f"{GOOGLE_AUTH_URL}?{params}"


async def _exchange_code(code: str) -> dict[str, Any]:
    import httpx

    client_id, client_secret, redirect_uri = _cfg()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise UnauthorizedError(detail="Google token exchange failed")
    return resp.json()


async def _verify_google_id_token(id_token: str) -> dict[str, Any]:
    """Verify signature (RS256 via Google JWKS), iss, aud and exp."""
    import httpx
    from jose import jwk, jwt
    from jose.exceptions import JWTError

    try:
        header_segment, _, _ = id_token.partition(".")
        header = json.loads(_b64url_decode(header_segment))
        kid = header.get("kid")
    except Exception as exc:
        raise UnauthorizedError(detail="Malformed id_token") from exc

    async with httpx.AsyncClient(timeout=10) as client:
        jwks = (await client.get(GOOGLE_JWKS_URL)).json()
    key_data = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key_data is None:
        raise UnauthorizedError(detail="Unknown Google signing key")

    client_id, _, _ = _cfg()
    try:
        claims = jwt.decode(
            id_token,
            jwk.construct(key_data),
            algorithms=["RS256"],
            audience=client_id,
            issuer=["https://accounts.google.com", "accounts.google.com"],
        )
    except JWTError as exc:
        raise UnauthorizedError(detail="Invalid Google id_token") from exc

    if claims.get("exp", 0) < time.time():
        raise UnauthorizedError(detail="Google id_token expired")
    return claims


async def complete_google_login(
    db: AsyncSession,
    *,
    code: str,
    state: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[dict[str, str], str]:
    """Validate state + code, match/provision the user, issue session tokens.

    Returns (tokens, return_url) so the route can send the browser back to the
    page the user came from (or /account) instead of a bare JSON body.
    """
    from app.core.cache.redis import cache_delete, cache_get

    stored = await cache_get(f"sso:state:{state}")
    if not stored or not stored.startswith("google|"):
        raise UnauthorizedError(detail="SSO state is invalid or expired")
    await cache_delete(f"sso:state:{state}")
    return_url = _safe_return_url(stored.partition("|")[2])

    token_payload = await _exchange_code(code)
    id_token = token_payload.get("id_token", "")
    claims = await _verify_google_id_token(id_token)

    email = (claims.get("email") or "").strip().lower()
    if not email or claims.get("email_verified") is not True:
        raise UnauthorizedError(detail="Google account email is not verified")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        # Provision: phone is the unique login identifier in this platform, so
        # SSO users get a placeholder they must replace in profile completion.
        #
        # The column is ``varchar(15)``. Writing a fixed 12 hex characters after
        # the ``sso-`` prefix produced 16 and every *new* Google sign-in died on
        # the flush with "value too long for type character varying(15)" —
        # returning users were unaffected, which is why it stayed hidden. The
        # length is now derived from the column so it cannot drift again, and
        # shortened to fit rather than truncating a fixed literal.
        phone = _sso_phone_placeholder()
        # The author slug, from the email's local part: without it an SSO
        # account's author archive 404s, which is the same gap the OTP path
        # had — every creation path must write the column the archive reads.
        from app.modules.users.application.author_slug import unique_author_slug

        user = User(
            phone=phone,
            email=email,
            password_hash=None,
            is_active=True,
            is_verified=True,
            author_slug=await unique_author_slug(
                db, email.split("@")[0] or email, fallback=email
            ),
        )
        db.add(user)
        await db.flush()
        await logger.ainfo("sso_user_provisioned", email=email)

    if not user.is_active:
        raise UnauthorizedError(detail="Account is deactivated")
    if user.deleted_at is not None:
        raise UnauthorizedError(detail="Account is deactivated")

    user.last_login = __import__("datetime").datetime.now(__import__("datetime").UTC)
    await db.flush()

    from app.modules.auth.application.auth_service import _create_token_pair

    tokens = await _create_token_pair(db, user, ip_address=ip_address, user_agent=user_agent)

    from app.modules.audit.application.audit_service import log_action

    await log_action(
        db,
        actor_id=user.id,
        action="user.login_sso",
        resource="user",
        resource_id=user.id,
        after={"provider": "google", "email": email},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await logger.ainfo("user_logged_in_sso", user_id=str(user.id), provider="google")
    return tokens, return_url
