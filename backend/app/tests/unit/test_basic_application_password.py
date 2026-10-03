"""Tests for HTTP Basic authentication with an application password.

WordPress accepts an application password over HTTP Basic
(``Authorization: Basic base64(login:app_password)``) and this accepted only
Bearer, so a script written against a WordPress REST client got a 401 and had to
be rewritten to change the scheme.

The load-bearing property is that the username is ignored: the identity comes
from the password's own record. A config with the wrong login baked in must
still authenticate as the password's owner, or a leaked config would be
useless in a way that reads like a security feature and is not one.
"""

from __future__ import annotations

import base64

import pytest

import app.core.security.dependencies as deps


def _basic_header(username: str, password: str) -> dict[str, str]:
    raw = f"{username}:{password}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


class _Request:
    """The slice of Request the extractor touches."""

    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = headers or {}

    @property
    def url(self) -> str:
        return "http://testserver/api"


class _Basic:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password


# -------------------------------------------------- the detection heuristic


def test_a_jwt_is_not_treated_as_an_application_password():
    # A JWT has dots; testing that first keeps the common case off the database.
    assert deps._looks_like_application_password("a.b.c") is False


def test_a_dotless_token_is_a_candidate():
    assert deps._looks_like_application_password("x" * 30) is True


def test_a_short_token_is_not_a_candidate():
    # Too short to be token_urlsafe output at the length we mint.
    assert deps._looks_like_application_password("short") is False


def test_an_empty_token_is_not_a_candidate():
    assert deps._looks_like_application_password("") is False


# ------------------------------------------------------- header construction


def test_basic_header_encodes_login_and_password():
    # WordPress application passwords contain spaces, which is why they are
    # base64-encoded rather than pasted raw into a header.
    login, password = "shop@example.com", "abcd efgh ijkl mnop qrst uvwx"
    header = _basic_header(login, password)
    assert header["Authorization"].startswith("Basic ")
    decoded = base64.b64decode(header["Authorization"].split(" ", 1)[1]).decode()
    assert decoded == f"{login}:{password}"


# --------------------------------------------------------- token resolution


@pytest.mark.asyncio
async def test_bearer_header_still_wins_over_basic(monkeypatch):
    """A request carrying both is a Bearer request; Basic is the fallback.

    FastAPI's HTTPBearer and HTTPBasic both inspect the same header, so a
    request with ``Authorization: Bearer x`` yields credentials and a Basic with
    ``None``. This asserts the ordering explicitly so a refactor cannot quietly
    let Basic read a bearer token as a password.
    """
    calls: list[str] = []

    async def fake_verify(db, token):
        calls.append(token)
        return None

    monkeypatch.setattr(
        "app.modules.auth.application.application_password_service."
        "verify_application_password",
        fake_verify,
    )
    # The session factory is opened inside the branch; replacing it keeps this
    # test off the database entirely.
    import contextlib

    @contextlib.asynccontextmanager
    async def fake_session():
        yield object()

    monkeypatch.setattr(
        "app.core.database.session.async_session_factory", fake_session
    )

    from fastapi import HTTPException

    bearer = "a" * 30
    with pytest.raises(HTTPException):
        await deps._extract_token(
            _Request(),
            credentials=type("C", (), {"credentials": bearer})(),
            # Basic is present too. A client can legitimately send both, and
            # the ordering has to be decided by the code rather than by which
            # header the client happened to build first.
            basic=_Basic("login@example.com", "p" * 30),
            access_token=None,
        )
    assert calls == [bearer], (
        "the bearer token must be the credential even when a Basic header is "
        "also present; reading the Basic password instead would turn a valid "
        "bearer session into a 401"
    )


@pytest.mark.asyncio
async def test_basic_password_becomes_the_token(monkeypatch):
    import contextlib

    seen: list[str] = []

    async def fake_verify(db, token):
        seen.append(token)
        return None

    @contextlib.asynccontextmanager
    async def fake_session():
        yield object()

    monkeypatch.setattr(
        "app.modules.auth.application.application_password_service."
        "verify_application_password",
        fake_verify,
    )
    monkeypatch.setattr(
        "app.core.database.session.async_session_factory", fake_session
    )

    from fastapi import HTTPException

    password = "p" * 30
    with pytest.raises(HTTPException):
        await deps._extract_token(
            _Request(),
            credentials=None,
            basic=_Basic("ignored@example.com", password),
            access_token=None,
        )
    assert seen == [password], "the password field is the credential; the login is not"


@pytest.mark.asyncio
async def test_basic_with_an_empty_password_falls_through_to_the_cookie():
    # HTTPBasic decodes any ``Basic <base64>`` header, so a client that sends
    # "user:" would otherwise authenticate with an empty string.
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        await deps._extract_token(
            _Request(),
            credentials=None,
            basic=_Basic("someone@example.com", ""),
            access_token=None,
        )


@pytest.mark.asyncio
async def test_no_credential_at_all_is_unauthorized():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await deps._extract_token(
            _Request(), credentials=None, basic=None, access_token=None
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_the_401_advertises_both_schemes():
    """A client that only knows WordPress must be able to discover Basic."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await deps._extract_token(
            _Request(), credentials=None, basic=None, access_token=None
        )
    challenge = exc.value.headers.get("WWW-Authenticate", "")
    assert "Bearer" in challenge
    assert "Basic" in challenge
