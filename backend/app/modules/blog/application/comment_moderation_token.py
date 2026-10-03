"""One-click moderation links in the moderator mail (WordPress: `comment.php?action=…`).

WordPress ends the moderation mail with three links — Approve, Trash, Spam —
so a moderator triaging from their inbox never opens the panel. Each link is
`admin_url("comment.php?action=approve&c={$comment_id}")`, which is why WP pairs
it with a nonce check in the handler: the URL is a bearer capability, and
anyone who has read one mail holds the ability to moderate that comment.

That arrangement is the thing to copy and the thing not to. Here the link
carries an HMAC-signed token instead of a bare id, and a token stops working
the moment it has been spent: the second click finds the comment already in the
status the link asked for, and the handler refuses rather than re-reporting
success. So a forwarded mail, a shared thread, or a browser prefetch cannot act
twice, and a re-click cannot manufacture an audit entry for an action nobody
took. Two further properties fall out of the signing rather than being bolted
on:

* the token is bound to *this* comment and *this* action — a token minted for
  approving cannot be edited to trash, and cannot be pointed at another comment.
* it expires. A moderation token is not a session; a week is long enough to
  approve a comment somebody is waiting on and short enough that a link sitting
  in an inbox archive does not stay a live capability.

No login is required and none is offered: the endpoint is public by
construction, which is exactly why the token has to carry the authorisation.
Everything here is HMAC-SHA256 over a canonical string, compared with
`hmac.compare_digest` — the same primitives the inbound-webhook verifier already
uses, so there is one signing convention in this codebase rather than two.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import uuid

logger = logging.getLogger(__name__)

#: How long a minted link stays clickable. Long enough to cover a moderator
#: reading their mail on a phone the next morning; short enough that the link
#: is dead once the comment is old news.
TOKEN_TTL_SECONDS = 7 * 24 * 3600

#: Actions a link may perform. Kept as a set so an action arriving from a
#: forged token is rejected by lookup rather than by a comparison chain that
#: has to be extended every time someone adds one.
ACTIONS = frozenset({"approve", "spam", "trash"})

#: The action each one means, as a comment status. `trash` is reversible;
#: `delete` deliberately has no link here, because a mail is the least
#: appropriate place to make a permanent choice.
#: Values, not member names. `CommentStatus("approved")` resolves; passing the
#: name raises ValueError, because this is a str-backed enum whose members are
#: lower-case. Storing the name here is the same confusion the enum columns in
#: this schema have already had twice.
_ACTION_TO_STATUS = {
    "approve": "approved",
    "spam": "spam",
    "trash": "trash",
}


def _key() -> bytes:
    """The app secret this token family is signed with.

    Raises rather than falling back to a default. An empty or placeholder key
    would still sign and verify symmetrically, so every token would validate
    and the link would be forgeable by anyone who noticed — the failure would
    look exactly like success. Refusing to mint is the safe direction: no mail
    goes out with a dead link, and the cause is named.
    """
    from app.core.config.settings import get_settings

    key = getattr(get_settings(), "JWT_SECRET_KEY", "") or ""
    if not key:
        raise RuntimeError(
            "cannot sign a moderation token: no JWT secret is configured"
        )
    return key.encode("utf-8")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(payload: bytes) -> bytes:
    return hmac.new(_key(), payload, hashlib.sha256).digest()


def mint_token(comment_id: uuid.UUID | str, action: str, *, now: float | None = None) -> str:
    """Build a signed, expiring, single-purpose moderation link token.

    Layout is ``<payload>.<signature>``, both base64url. The payload carries the
    comment id, the action and the expiry, so a verifier never has to trust a
    field it did not check.
    """
    if action not in ACTIONS:
        raise ValueError(f"unknown moderation action: {action!r}")
    issued = int(now if now is not None else time.time())
    body = f"{comment_id}:{action}:{issued + TOKEN_TTL_SECONDS}"
    encoded = _b64(body.encode("utf-8"))
    return f"{encoded}.{_b64(_sign(body.encode('utf-8')))}"


def verify_token(
    token: str,
    comment_id: uuid.UUID | str,
    action: str,
    *,
    now: float | None = None,
    already_done: bool = False,
) -> bool:
    """Is this token the right, unexpired, untampered capability for the call?

    ``already_done`` is the single-use half: the caller passes whether the
    comment is *already* in the status this action sets. A link that has been
    spent then fails here, so the refusal is decided in one place and reads the
    same whether it came from a second click or from a token replayed by a
    script.

    Returns False rather than raising for every rejection. The caller is a
    public GET, and the only correct behaviour for a bad link is to render a
    page saying so — an exception would let a caller distinguish "expired" from
    "wrong comment" from "bad signature" by status code, which is more than a
    one-click link needs to disclose.
    """
    if action not in ACTIONS:
        return False
    if already_done:
        return False
    if not token or "." not in token:
        return False
    encoded, _, signature = token.partition(".")
    try:
        raw = _unb64(encoded)
        given = _unb64(signature)
    except Exception:  # noqa: BLE001 — any malformed input is simply invalid
        return False

    # Signature first: an unsigned body must never reach the parse below.
    if not hmac.compare_digest(_sign(raw), given):
        return False

    try:
        token_id, token_action, expiry = raw.decode("utf-8").split(":")
    except (UnicodeDecodeError, ValueError):
        return False

    if not hmac.compare_digest(token_action, action):
        return False
    if not hmac.compare_digest(str(token_id), str(comment_id)):
        return False

    current = int(now if now is not None else time.time())
    try:
        if int(expiry) <= current:
            return False
    except ValueError:
        return False
    return True


def build_action_url(comment_id: uuid.UUID | str, action: str, site_url: str) -> str:
    """The full link as it appears in the mail.

    Kept next to the token code so the shape of the URL cannot drift away from
    what the endpoint accepts — a template that builds a slightly different
    query string is the most likely way for this feature to break quietly.
    """
    token = mint_token(comment_id, action)
    base = (site_url or "").rstrip("/")
    # The router is mounted at /api/v1/blog (see the include table in main.py),
    # so the link has to carry that prefix. Kept as a constant next to the URL
    # builder because a mail that has already gone out with the wrong prefix is
    # not fixable by deploying a route.
    return f"{base}/api/v1/blog/comment-action/{action}/{comment_id}?token={token}"


def status_for(action: str) -> str | None:
    """The comment status an action sets, or None if the action is unknown."""
    return _ACTION_TO_STATUS.get(action)