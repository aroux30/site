"""Live-chat widget: n8n reply parsing, config privacy, Telegram ingest.

Pins the pure logic that the routes depend on — no DB, no network:

* the n8n reply parser accepts every shape the WordPress plugin accepted;
* the public config never leaks the n8n URL / Telegram credentials;
* the Telegram reply ingester recovers the session key from a quoted hand-off;
* the hand-off window math mutes the AI while a human owns the thread.

The privacy test is the important one: a regression that put ``webhook_url``
back into ``ChatPublicConfig`` would ship the n8n endpoint to every browser.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


# ── n8n reply parsing ─────────────────────────────────────────────────────


def test_extract_reply_accepts_every_plugin_shape():
    """Each response shape the plugin's post_to_n8n handled must parse."""
    from app.modules.chat.application.n8n_client import _extract_reply

    assert _extract_reply('{"output": "پاسخ"}') == "پاسخ"
    assert _extract_reply('{"text": "hi"}') == "hi"
    assert _extract_reply('{"message": "m"}') == "m"
    assert _extract_reply('{"content": "c"}') == "c"
    assert _extract_reply('[{"output": "first"}]') == "first"
    assert _extract_reply('[{"text": "arr"}]') == "arr"
    assert _extract_reply('["bare"]') == "bare"
    assert _extract_reply('"quoted"') == "quoted"
    assert _extract_reply("plain text") == "plain text"
    assert _extract_reply("") == ""


def test_extract_reply_prefers_known_key_over_generic():
    """A dict with both a known key and noise returns the known key."""
    from app.modules.chat.application.n8n_client import _extract_reply

    assert _extract_reply('{"noise": "x", "output": "wanted"}') == "wanted"


# ── Public config privacy ─────────────────────────────────────────────────


def test_public_config_strips_secrets():
    """The browser config must never carry the n8n URL or Telegram credentials.

    Negative test: the assertion is exact-key presence, so re-adding any of
    these to ``ChatPublicConfig`` fails here rather than in production.
    """
    from app.modules.chat.application.chat_config import public_config

    cfg = {
        "webhook_url": "https://n8n.internal/webhook/secret",
        "telegram_bot_token": "123:ABC",
        "telegram_chat_id": "-100999",
        "telegram_webhook_secret": "shh",
        "color_primary": "#123456",
    }
    pub = public_config(cfg).model_dump()
    for leaked in ("webhook_url", "telegram_bot_token", "telegram_chat_id", "telegram_webhook_secret"):
        assert leaked not in pub, f"{leaked} leaked into the public config"
    assert pub["color_primary"] == "#123456"
    assert pub["config_hash"]


def test_config_hash_changes_with_public_config():
    """The cache-bust hash must move when a visible field changes."""
    from app.modules.chat.application.chat_config import config_hash

    a = config_hash({"color_primary": "#111111"})
    b = config_hash({"color_primary": "#222222"})
    assert a != b


def test_config_hash_ignores_secret_change():
    """A secret rotation must NOT bust every visitor's cached widget."""
    from app.modules.chat.application.chat_config import config_hash

    a = config_hash({"telegram_bot_token": "old", "color_primary": "#111111"})
    b = config_hash({"telegram_bot_token": "new", "color_primary": "#111111"})
    assert a == b


# ── Telegram session-key extraction ───────────────────────────────────────


def test_extract_session_key_from_code_block():
    from app.modules.chat.application.telegram_ingest import _extract_session_key

    text = "شناسه گفتگو:\n<code>sess_abc123xyz</code>\n\nتاریخچه..."
    assert _extract_session_key(text) == "sess_abc123xyz"


def test_extract_session_key_from_uuid():
    from app.modules.chat.application.telegram_ingest import _extract_session_key

    key = "5ae8aeaa-715e-459b-995a-0a91fdb1deff"
    assert _extract_session_key(f"reply to <code>{key}</code>") == key


def test_extract_session_key_returns_none_when_absent():
    from app.modules.chat.application.telegram_ingest import _extract_session_key

    assert _extract_session_key("just some operator chatter") is None


# ── Hand-off window math ──────────────────────────────────────────────────


def test_handoff_active_while_future():
    """A session with a future deadline has the AI muted."""
    from app.modules.chat.application.chat_service import ChatService
    from app.modules.chat.domain.models import ChatSession

    session = ChatSession(session_key="k", user_name="u")
    session.handoff_until = datetime.now(UTC) + timedelta(minutes=5)
    assert ChatService.handoff_active(session) is True


def test_handoff_inactive_when_past_or_unset():
    from app.modules.chat.application.chat_service import ChatService
    from app.modules.chat.domain.models import ChatSession

    past = ChatSession(session_key="k", user_name="u")
    past.handoff_until = datetime.now(UTC) - timedelta(minutes=1)
    assert ChatService.handoff_active(past) is False

    unset = ChatSession(session_key="k", user_name="u")
    assert ChatService.handoff_active(unset) is False


# ── Telegram client gating ────────────────────────────────────────────────


def test_telegram_config_requires_both_token_and_chat():
    from app.modules.chat.application.telegram_client import TelegramConfig

    assert TelegramConfig(bot_token="", chat_id="-1").is_configured is False
    assert TelegramConfig(bot_token="t", chat_id="").is_configured is False
    assert TelegramConfig(bot_token="t", chat_id="-1").is_configured is True


# ── G1: user message forwarded to Telegram during handoff ─────────────────


def test_forward_user_message_sends_to_topic_when_handoff():
    """During a handoff the visitor's message must reach the operator (G1).

    Asserts the Telegram send was ATTEMPTED with the topic id — "never fetched"
    style: a mock transport records the call, so a regression that drops the
    forward fails here rather than passing on "no exception".
    """
    import asyncio

    from app.modules.chat.application import telegram_notify as tn

    calls: list[tuple[str, dict]] = []

    class FakeClient:
        async def send_message(self, text, *, thread_id=None, reply_markup=None):
            calls.append((text, {"thread_id": thread_id}))

    class FakeSession:
        tg_topic_id = 777

    class FakeDB:
        async def get(self, *a, **k):  # not used
            return None

    async def fake_resolve(db):
        return FakeClient()

    async def fake_get_session(db, key):
        return FakeSession()

    async def fake_flush():
        return None

    orig_resolve = tn._resolve_client
    orig_service = __import__(
        "app.modules.chat.application.chat_service", fromlist=["ChatService"]
    ).ChatService
    orig_get = orig_service.get_session_by_key
    try:
        tn._resolve_client = fake_resolve
        orig_service.get_session_by_key = staticmethod(fake_get_session)
        asyncio.run(tn.forward_user_message(FakeDB(), session_key="sess_x", message="سلام"))
    finally:
        tn._resolve_client = orig_resolve
        orig_service.get_session_by_key = orig_get

    assert len(calls) == 1, "user message was NOT forwarded to Telegram"
    assert calls[0][1]["thread_id"] == 777
    assert "پیام کاربر" in calls[0][0]


# ── F11: flow-complete idempotency key must digest CONTENT ────────────────


def test_sync_session_identity_is_a_service_method_not_module_function():
    """G8/F12: the heartbeat calls `ChatService.sync_session_identity`.

    A first cut imported it as a module-level function, but it is a staticmethod
    on the class — every authenticated heartbeat 500'd with ImportError. This
    pins the correct call shape: the class attribute exists AND the route calls
    it through the class (not a bare-name import).
    """
    import inspect

    from app.modules.chat.application.chat_service import ChatService
    from app.modules.chat.api import routes

    assert hasattr(ChatService, "sync_session_identity")
    assert inspect.iscoroutinefunction(ChatService.sync_session_identity)
    src = inspect.getsource(routes.heartbeat)
    assert "ChatService.sync_session_identity(" in src, "heartbeat does not call the service method"
    assert "import sync_session_identity" not in src, "stale module-level import reintroduced"


def test_flow_idempotency_key_is_content_stable_and_distinct():
    """The lock key must be stable across processes AND differ for different
    flows of the same length.

    Two regressions this pins (both proved by a reviewer):
    * Python ``hash()`` is salted per process, so a lock keyed on it stops
      locking under multiple workers;
    * a length-only key collides for two DIFFERENT same-length flows, so the
      second flow's messages are never stored.
    """
    import hashlib
    import json

    from app.modules.chat.schemas.chat import ChatFlowEntry

    def key(final: str, ctx: list[ChatFlowEntry]) -> str:
        # Mirrors the route's digest construction exactly.
        return hashlib.sha256(
            json.dumps(
                [final, [e.model_dump() for e in ctx]],
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

    flow_a = [ChatFlowEntry(role="user", message="قیمت"), ChatFlowEntry(role="ai", message="۱۰۰")]
    flow_b = [ChatFlowEntry(role="user", message="ارسال"), ChatFlowEntry(role="ai", message="۲۰۰")]
    # Same length, same final text, DIFFERENT content -> different keys.
    assert key("", flow_a) != key("", flow_b)
    # Identical flow -> identical key (so the double-submit lock holds).
    assert key("", flow_a) == key("", list(flow_a))
    # The key must NOT be a bare Python hash() (salted) — it is a hex digest.
    assert len(key("", flow_a)) == 64 and all(c in "0123456789abcdef" for c in key("", flow_a))


# ── Webhook security contract (regression guard) ──────────────────────────


def test_telegram_webhook_is_not_open_by_default_in_production():
    """The webhook must refuse an unauthenticated POST in production.

    A security review found the first cut gated only on `if expected:` — with
    the default blank secret, NO check ran, so an unauthenticated caller could
    delete a session or forge an admin reply. This pins the fix: in production
    the route 403s unless the secret is configured AND matches.

    Static assertion on the source (the route needs a DB + settings to call).
    Anchors are the EXACT expressions, not bare names: a bare "compare_digest"
    substring is satisfied by the explanatory comment on the same line, so the
    test passed even with the call reverted to `==` (a peer review proved this
    by textual simulation — the "a name in the file is not a connection" trap).
    """
    import inspect

    from app.modules.chat.api import routes

    src = inspect.getsource(routes.telegram_webhook)
    assert 'ENVIRONMENT == "production"' in src, "production guard removed"
    assert (
        "secrets.compare_digest(presented, expected)" in src
    ), "timing-safe compare call removed or reverted to =="
    assert '@limiter.limit("120/minute")' in src, "rate limit removed"
    # A malformed body must not 500 — the ingest contract is "never raises".
    assert "except (ValueError, UnicodeDecodeError)" in src, "malformed-JSON guard removed"


# ── Round-2 (N3): conversation-list last-seen formatting ───────────────────


def test_format_last_seen_matches_plugin_windows():
    """N3: `_format_last_seen` mirrors the plugin's `format_last_seen` (php:1780).

    The conversation list showed a blank "آخرین بازدید" because the field was
    hardcoded "". This pins the relative-time thresholds AND the shamsi/miladi
    day formatting so a regression to an empty/naive string flips it red.
    """
    from datetime import UTC, datetime, timedelta

    from app.modules.chat.application.chat_service import _format_last_seen

    now = datetime.now(UTC)
    assert _format_last_seen(now - timedelta(seconds=5)) == "🟢 آنلاین"
    assert _format_last_seen(now - timedelta(seconds=45)) == "45 ثانیه پیش"
    assert _format_last_seen(now - timedelta(minutes=5)) == "5 دقیقه پیش"
    assert _format_last_seen(now - timedelta(hours=3)) == "3 ساعت پیش"
    assert _format_last_seen(None) == ""
    # Older than a day: shamsi month name vs the miladi English label.
    old = now - timedelta(days=3)
    shamsi = _format_last_seen(old, "shamsi")
    miladi = _format_last_seen(old, "miladi")
    assert any(m in shamsi for m in ("فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد",
                                     "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"))
    assert miladi.startswith(("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))


def test_conversation_list_populates_last_seen_and_current_page():
    """N3: `list_conversations` must not hardcode the two fields to "".

    Source-level pin: a revert to `"last_seen_text": ""` / `"current_page": ""`
    is exactly the bug the plugin-parity fix removed. The plugin reads the
    online table for EVERY listed session (php:1355/1363), so an offline session
    with a stale presence row still shows a relative time + page; a session with
    NO presence row shows both as empty (php:1363 leaves them '' — no fallback to
    last_activity_at). Both branches are live-verified; this pins the source.
    """
    import inspect

    from app.modules.chat.application import chat_service

    src = inspect.getsource(chat_service.ChatService.list_conversations)
    assert "_format_last_seen(pres.last_seen, date_format)" in src
    assert 'pres.page_title or ""' in src
    # The empty branch is intentional (plugin php:1363): no presence row → both
    # stay "". Anchored as the `if pres else ""` fallback, not the old hardcode.
    assert 'if pres else ""' in src
    assert '"last_seen_text": ""' not in src
    assert '"current_page": ""' not in src


# ── Round-2 (bridge): jQuery array-key parsing ─────────────────────────────


def test_bridge_form_parses_bracketed_array_keys():
    """The WP plugin sends arrays as `session_ids[]` (jQuery serialization).

    `dict(form)` would keep the literal key `"session_ids[]"`, so the unread /
    validate actions read None and returned empty — the widget then wiped its
    session list every 6s (a live bug). This pins the normalization: strip the
    `[]` suffix and collect ALL values (repeated plain keys → list too).
    """
    import asyncio

    from starlette.datastructures import FormData, Headers, QueryParams

    from app.modules.chat.api import bridge

    class _Req:
        def __init__(self, form: FormData):
            self._form = form
            self.headers = Headers({"content-type": "application/x-www-form-urlencoded"})

        async def form(self) -> FormData:
            return self._form

    # One bracketed value.
    form = FormData([("action", "n8n_chat_unread_counts"), ("session_ids[]", "sess_a")])
    out = asyncio.run(bridge._form(_Req(form)))
    assert out["session_ids"] == ["sess_a"]
    assert "session_ids[]" not in out

    # Two bracketed values → both kept.
    form = FormData([("session_ids[]", "sess_a"), ("session_ids[]", "sess_b")])
    out = asyncio.run(bridge._form(_Req(form)))
    assert out["session_ids"] == ["sess_a", "sess_b"]

    # Repeated plain key → list (not last-wins).
    form = FormData([("session_ids", "sess_a"), ("session_ids", "sess_b")])
    out = asyncio.run(bridge._form(_Req(form)))
    assert out["session_ids"] == ["sess_a", "sess_b"]

    # A scalar field stays scalar.
    form = FormData([("session_id", "sess_x")])
    out = asyncio.run(bridge._form(_Req(form)))
    assert out["session_id"] == "sess_x"


# ── Round-2 (bridge): B1 upload / B2 handoff role / B4 webm mime ───────────


def test_bridge_upload_detects_starlette_uploadfile():
    """B1: `request.form()` yields a STARLETTE UploadFile, not FastAPI's.

    The bridge checked `isinstance(up, fastapi.UploadFile)` — False for the
    Starlette instance the form returns — so `file` stayed None and every
    widget file/voice upload failed silently with `{"success": false,
    "data": "no file"}`. Pins the corrected class (starlette is the base).
    """
    from starlette.datastructures import UploadFile as StarletteUploadFile

    import app.modules.chat.api.bridge as bridge

    src = bridge.__doc__ and open(bridge.__file__, encoding="utf-8").read()
    assert "from starlette.datastructures import UploadFile" in src
    assert "from fastapi import APIRouter, Depends, Request\n" in src  # no UploadFile
    # The runtime contract: a Starlette UploadFile IS the type we now check.
    assert StarletteUploadFile.__name__ == "UploadFile"


def test_handoff_system_message_is_admin_role():
    """B2: the handoff notice must be role=admin (plugin php:1513), so the
    visitor's unread count rises (badge/beep). A SYSTEM role is never
    read-marked by `mark_read` and never counts as unread."""
    import inspect

    from app.modules.chat.api import bridge, routes

    for mod in (bridge._handoff, routes.request_handoff):
        src = inspect.getsource(mod)
        assert "role=ChatRole.ADMIN" in src, f"{mod.__name__} must use ADMIN role"
        assert "role=ChatRole.SYSTEM" not in src


def test_handoff_blank_system_message_falls_back_to_default():
    """B1: plugin parity (php:1510) — when the operator clears
    `handoff_system_message`, the plugin substitutes a default notice so the
    visitor ALWAYS sees "support requested". The port used to skip the notice
    entirely (`if sys_msg:`), leaving the visitor with no handoff indication."""
    import inspect

    from app.modules.chat.api import bridge, routes
    from app.modules.chat.application import chat_config

    # The helper applies the blank-fallback.
    assert chat_config.handoff_system_message({"handoff_system_message": ""}) == (
        chat_config.DEFAULT_HANDOFF_SYSTEM_MESSAGE
    )
    assert chat_config.handoff_system_message({"handoff_system_message": "  "}) == (
        chat_config.DEFAULT_HANDOFF_SYSTEM_MESSAGE
    )
    # A real custom message is preserved verbatim (stripped).
    assert (
        chat_config.handoff_system_message({"handoff_system_message": " متن دلخواه "})
        == "متن دلخواه"
    )

    # BOTH handoff paths must call the helper (not a bare `if sys_msg:` guard).
    for mod in (bridge._handoff, routes.request_handoff):
        src = inspect.getsource(mod)
        assert "chat_config.handoff_system_message(" in src, (
            f"{mod.__name__} must use the blank-fallback helper"
        )



def test_webm_upload_keeps_webm_mime():
    """B4: a MediaRecorder voice note is WebM (EBML magic 1a45dfa3). The sniffer
    hardcoded `video/mp4` for that signature → a `.webm` voice note was stored
    as `.mp4` / video/mp4. It must detect WebM now."""
    from app.modules.media.application.media_service import _sniff_mime

    ebml = b"\x1a\x45\xdf\xa3" + b"\x00" * 20
    assert _sniff_mime(ebml, "audio/webm") == "audio/webm"
    assert _sniff_mime(ebml, "video/webm") == "video/webm"
    # Undeclared EBML → WebM, never video/mp4.
    assert _sniff_mime(ebml, "") == "video/webm"
    assert _sniff_mime(ebml, "application/octet-stream") == "video/webm"


def test_flow_paths_actually_call_the_idempotency_lock():
    """B3: the flow handlers must CALL `flow_lock_acquired` — not merely have a
    content-stable digest. The old test only checked the digest shape, so
    deleting the two lock lines in the bridge left 21/21 green (a silent
    regression back to duplicate flow messages). Pin the exact call in BOTH the
    bridge and the REST route."""
    import inspect

    from app.modules.chat.api import bridge, routes

    bsrc = inspect.getsource(bridge._flow)
    assert "flow_lock_acquired(key, digest)" in bsrc, "bridge flow lost its lock"
    # It must gate the save on the lock result (return early when locked).
    assert "if not await flow_lock_acquired(key, digest):" in bsrc

    rsrc = inspect.getsource(routes.flow_complete)
    assert "flow_lock_acquired(body.session_key, digest)" in rsrc, (
        "route flow lost its lock"
    )
    assert "if not await flow_lock_acquired(body.session_key, digest):" in rsrc

