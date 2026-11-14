"""Chat application service — sessions, messages, presence, admin console.

All queries live here (no repository layer, per the repo convention). Routes
commit; the service flushes. Enums are stored as NAMES (``native_enum=False``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import delete, func, select, update

from app.core.exceptions.handlers import NotFoundError
from app.modules.chat.domain.models import (
    ChatMessage,
    ChatPresence,
    ChatRole,
    ChatSession,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

#: A presence row older than this is "offline" (plugin used 15s).
ONLINE_WINDOW_SECONDS = 15


def _now() -> datetime:
    return datetime.now(UTC)


def _fmt_time(dt: datetime | None) -> str:
    """``HH:MM`` in Tehran local time (the plugin used ``mysql2date('H:i')``)."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    # Tehran is UTC+3:30 year-round (no DST since 2022).
    local = dt.astimezone(UTC) + timedelta(hours=3, minutes=30)
    return local.strftime("%H:%M")


class ChatService:
    """Session/message/presence CRUD for the live-chat widget."""

    # ── Sessions ──────────────────────────────────────────────────────

    @staticmethod
    async def get_session_by_key(db: AsyncSession, session_key: str) -> ChatSession | None:
        stmt = select(ChatSession).where(ChatSession.session_key == session_key)
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def start_session(
        db: AsyncSession,
        *,
        session_key: str,
        user_name: str = "",
        user_email: str = "",
        user_phone: str = "",
        user_data: dict[str, Any] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> ChatSession:
        """Create the session or update its identity fields (plugin parity)."""
        session = await ChatService.get_session_by_key(db, session_key)
        if session is None:
            session = ChatSession(
                session_key=session_key,
                user_id=user_id,
                user_name=user_name or "مهمان",
                user_email=user_email,
                user_phone=user_phone,
                user_data=user_data or {},
            )
            db.add(session)
            await db.flush()
            logger.info("chat_session_started", session_key=session_key)
        else:
            if user_name:
                session.user_name = user_name
            if user_email:
                session.user_email = user_email
            if user_phone:
                session.user_phone = user_phone
            if user_data is not None:
                session.user_data = user_data
            if user_id is not None:
                session.user_id = user_id
            session.last_activity_at = _now()
            await db.flush()
        return session

    @staticmethod
    async def touch_session(db: AsyncSession, session: ChatSession) -> None:
        session.last_activity_at = _now()
        await db.flush()

    @staticmethod
    async def sync_session_identity(
        db: AsyncSession, session: ChatSession, user_id: uuid.UUID
    ) -> str | None:
        """Sync a session's identity from the authenticated user (G8).

        The authenticated user is the TRUSTED source: their real display name
        and phone replace a guest placeholder, and ``user_id`` is bound. A
        session whose name was already set by a signed-in user is not
        downgraded. Returns the name now on the session, or ``None`` if the
        user has no profile to read.
        """
        from app.modules.users.domain.models import User, UserProfile

        user = await db.get(User, user_id)
        if user is None:
            return None
        profile = (
            await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        ).scalar_one_or_none()
        name = ""
        if profile is not None:
            name = (profile.display_name or "").strip()
            if not name:
                name = " ".join(filter(None, [profile.first_name, profile.last_name])).strip()
        if not name:
            name = (user.phone or "").strip()

        session.user_id = user_id
        # Upgrade a guest/placeholder name; keep a real one already set.
        current = (session.user_name or "").strip()
        if name and (not current or current.startswith("مهمان")):
            session.user_name = name
        if user.phone and not session.user_phone:
            session.user_phone = user.phone
        await db.flush()
        return session.user_name

    # ── Messages ──────────────────────────────────────────────────────

    @staticmethod
    async def add_message(
        db: AsyncSession,
        *,
        session_key: str,
        role: ChatRole,
        body: str,
        sender_name: str = "",
    ) -> ChatMessage:
        """Append a message; auto-creates the session if it is missing.

        The plugin promoted an unknown session on first message; a message for a
        session row that does not exist yet must still land (a heartbeat-only
        visitor who types before the start call resolves).
        """
        session = await ChatService.get_session_by_key(db, session_key)
        if session is None:
            session = await ChatService.start_session(db, session_key=session_key)
        message = ChatMessage(
            session_id=session.id,
            role=role,
            body=body,
            sender_name=sender_name,
        )
        db.add(message)
        session.last_activity_at = _now()
        await db.flush()
        return message

    @staticmethod
    async def list_messages_since(
        db: AsyncSession, session_key: str, last_id: int = 0
    ) -> list[ChatMessage]:
        session = await ChatService.get_session_by_key(db, session_key)
        if session is None:
            return []
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id, ChatMessage.id > last_id)
            .order_by(ChatMessage.id.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def list_all_messages(db: AsyncSession, session_key: str) -> list[ChatMessage]:
        session = await ChatService.get_session_by_key(db, session_key)
        if session is None:
            return []
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.id.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def mark_read(db: AsyncSession, session_key: str, *, by_user: bool) -> None:
        """Mark messages read.

        ``by_user=True`` marks admin/AI messages read (the visitor opened the
        chat); ``by_user=False`` marks user messages read (the admin opened it).
        """
        session = await ChatService.get_session_by_key(db, session_key)
        if session is None:
            return
        roles = [ChatRole.ADMIN, ChatRole.AI] if by_user else [ChatRole.USER]
        await db.execute(
            update(ChatMessage)
            .where(
                ChatMessage.session_id == session.id,
                ChatMessage.role.in_(roles),
                ChatMessage.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await db.flush()

    @staticmethod
    async def read_updates(db: AsyncSession, session_key: str) -> list[dict[str, Any]]:
        """Read receipts for the last 20 messages (the poller's ``updates``)."""
        session = await ChatService.get_session_by_key(db, session_key)
        if session is None:
            return []
        stmt = (
            select(ChatMessage.id, ChatMessage.is_read)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.id.desc())
            .limit(20)
        )
        rows = (await db.execute(stmt)).all()
        return [{"id": r.id, "is_read": r.is_read} for r in rows]

    @staticmethod
    async def unread_count(db: AsyncSession, session_key: str, *, for_admin: bool) -> int:
        """Count unread messages: user-side (admin/AI) or admin-side (user)."""
        session = await ChatService.get_session_by_key(db, session_key)
        if session is None:
            return 0
        roles = [ChatRole.USER] if for_admin else [ChatRole.ADMIN, ChatRole.AI]
        stmt = select(func.count()).select_from(ChatMessage).where(
            ChatMessage.session_id == session.id,
            ChatMessage.role.in_(roles),
            ChatMessage.is_read.is_(False),
        )
        return int((await db.execute(stmt)).scalar_one())

    @staticmethod
    async def unread_counts_for(
        db: AsyncSession, session_keys: list[str], *, for_admin: bool
    ) -> dict[str, int]:
        """Batch unread counts, keyed by session_key (the badge poller)."""
        out: dict[str, int] = {}
        for key in session_keys:
            out[key] = await ChatService.unread_count(db, key, for_admin=for_admin)
        return out

    @staticmethod
    async def valid_session_keys(db: AsyncSession, session_keys: list[str]) -> list[str]:
        """Which of the given keys exist as real sessions (client dedup guard)."""
        if not session_keys:
            return []
        stmt = select(ChatSession.session_key).where(ChatSession.session_key.in_(session_keys))
        return list((await db.execute(stmt)).scalars().all())

    # ── Handoff ───────────────────────────────────────────────────────

    @staticmethod
    async def set_handoff(
        db: AsyncSession, session_key: str, *, until: datetime | None
    ) -> None:
        session = await ChatService.get_session_by_key(db, session_key)
        if session is None:
            raise NotFoundError(resource="ChatSession", detail="گفتگو یافت نشد.")
        session.handoff_until = until
        await db.flush()

    @staticmethod
    def handoff_active(session: ChatSession) -> bool:
        """Whether a human currently owns the thread (AI muted)."""
        if session.handoff_until is None:
            return False
        until = session.handoff_until
        if until.tzinfo is None:
            until = until.replace(tzinfo=UTC)
        return _now() < until

    # ── Presence / heartbeat ──────────────────────────────────────────

    @staticmethod
    async def heartbeat(
        db: AsyncSession,
        *,
        session_key: str,
        tab_id: str,
        user_name: str,
        user_ip: str,
        user_agent: str,
        page_url: str,
        page_title: str,
        user_id: uuid.UUID | None,
    ) -> None:
        db_key = f"{session_key}|{tab_id}"
        stmt = select(ChatPresence).where(ChatPresence.session_key == db_key)
        row = (await db.execute(stmt)).scalar_one_or_none()
        data = {
            "user_name": user_name,
            "user_ip": user_ip,
            "user_agent": user_agent,
            "page_url": page_url,
            "page_title": page_title,
            "user_id": user_id,
            "last_seen": _now(),
        }
        if row is None:
            db.add(ChatPresence(session_key=db_key, **data))
        else:
            for key, value in data.items():
                setattr(row, key, value)
        await db.flush()

    @staticmethod
    async def online_users(db: AsyncSession) -> list[dict[str, Any]]:
        """Grouped online visitors (one card per name, tabs merged)."""
        cutoff = _now() - timedelta(seconds=ONLINE_WINDOW_SECONDS)
        stmt = (
            select(ChatPresence)
            .where(ChatPresence.last_seen >= cutoff)
            .order_by(ChatPresence.last_seen.desc())
        )
        rows = list((await db.execute(stmt)).scalars().all())

        grouped: dict[str, dict[str, Any]] = {}
        # Cache contact lookups per user so a signed-in visitor with several
        # presence rows (multiple tabs) costs ONE profile query, not N.
        contact_cache: dict[uuid.UUID, tuple[str, str]] = {}
        for r in rows:
            real_key = r.session_key.split("|", 1)[0]
            name = r.user_name or f"مهمان {real_key[-4:]}"
            if name not in grouped:
                # For a signed-in visitor resolve phone/email from the user
                # profile (G9 — the plugin read billing_phone → user_phone →
                # phone meta). Guests keep their pre-chat form values, which
                # live on the session and show in the console's info panel.
                if r.user_id is not None and r.user_id not in contact_cache:
                    contact_cache[r.user_id] = await ChatService._profile_contact(
                        db, r.user_id
                    )
                phone, email = (
                    contact_cache.get(r.user_id, ("", "")) if r.user_id else ("", "")
                )
                grouped[name] = {
                    "session_key": real_key,
                    "user_name": name,
                    "last_seen": r.last_seen.isoformat() if r.last_seen else "",
                    "user_ip": r.user_ip or "",
                    "user_agent": r.user_agent or "",
                    "user_phone": phone,
                    "user_email": email,
                    "is_wp_user": r.user_id is not None,
                    "tabs": [],
                }
            tab = {"url": r.page_url or "", "title": r.page_title or "بدون عنوان"}
            if tab not in grouped[name]["tabs"]:
                grouped[name]["tabs"].append(tab)

        return list(grouped.values())

    @staticmethod
    async def _profile_contact(
        db: AsyncSession, user_id: uuid.UUID | None
    ) -> tuple[str, str]:
        """Phone + email for a signed-in visitor, from the user profile (G9)."""
        if user_id is None:
            return "", ""
        from app.modules.users.domain.models import User

        user = await db.get(User, user_id)
        # The store is phone-first — email was dropped 2026-10-07 (migration
        # rmemail1), so there is no email column to read. The console shows the
        # phone and renders the empty email as "—".
        return (user.phone if user else "") or "", ""

    # ── Admin console ─────────────────────────────────────────────────

    @staticmethod
    async def list_conversations(db: AsyncSession, *, limit: int = 50) -> list[dict[str, Any]]:
        """Conversation list for the live console, newest activity first."""
        stmt = (
            select(ChatSession)
            .order_by(ChatSession.last_activity_at.desc())
            .limit(limit)
        )
        sessions = list((await db.execute(stmt)).scalars().all())

        cutoff = _now() - timedelta(seconds=ONLINE_WINDOW_SECONDS)
        presence_stmt = select(ChatPresence).where(
            ChatPresence.last_seen >= cutoff
        )
        presence_rows = list((await db.execute(presence_stmt)).scalars().all())
        online_keys = {p.session_key.split("|", 1)[0] for p in presence_rows}

        # N3: newest presence row per session (ANY age) → last_seen_text +
        # current_page, like the plugin (php:1355/1363 reads the online table
        # for every listed session, not only online ones).
        latest_presence: dict[str, ChatPresence] = {}
        for p in (
            await db.execute(select(ChatPresence).order_by(ChatPresence.last_seen.desc()))
        ).scalars():
            real = p.session_key.split("|", 1)[0]
            if real not in latest_presence:
                latest_presence[real] = p

        from app.modules.chat.application import chat_config

        config = await chat_config.get_config(db)
        date_format = str(config.get("date_format") or "shamsi")

        out: list[dict[str, Any]] = []
        for s in sessions:
            last = (
                await db.execute(
                    select(ChatMessage.body)
                    .where(ChatMessage.session_id == s.id)
                    .order_by(ChatMessage.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            unread = await ChatService.unread_count(db, s.session_key, for_admin=True)
            name = s.user_name or f"مهمان {s.session_key[-4:]}"
            preview = (last or "شروع چت (بدون پیام)")[:40]
            pres = latest_presence.get(s.session_key)
            out.append(
                {
                    "session_key": s.session_key,
                    "user_name": name,
                    "time_ago": _human_ago(s.last_activity_at),
                    "last_message": preview + ("..." if last and len(last) > 40 else ""),
                    "unread_count": unread,
                    "is_online": s.session_key in online_keys,
                    "last_seen_text": _format_last_seen(pres.last_seen, date_format) if pres else "",
                    "current_page": (pres.page_title or "") if pres else "",
                }
            )
        out.sort(key=lambda r: (not r["is_online"],))
        return out

    @staticmethod
    async def session_info(db: AsyncSession, session_key: str) -> list[dict[str, str]]:
        """Pre-chat form values for the admin info panel (plugin parity)."""
        session = await ChatService.get_session_by_key(db, session_key)
        if session is None:
            return []
        from app.modules.chat.application import chat_config

        config = await chat_config.get_config(db)
        fields: list[dict[str, str]] = []
        extra = session.user_data or {}
        for fd in config.get("prechat_fields", []):
            key = fd.get("key")
            label = fd.get("label")
            if not key or not label:
                continue
            value = extra.get(key, "")
            if not value:
                if key == "name":
                    value = session.user_name
                elif key == "email":
                    value = session.user_email
                elif key == "phone":
                    value = session.user_phone
            if value:
                fields.append({"label": str(label), "value": str(value)})
        if session.created_at:
            fields.append({"label": "شروع چت", "value": _fmt_time(session.created_at)})
        return fields

    @staticmethod
    async def delete_session(db: AsyncSession, session_key: str) -> None:
        session = await ChatService.get_session_by_key(db, session_key)
        if session is None:
            return
        await db.delete(session)
        await db.execute(delete(ChatPresence).where(ChatPresence.session_key.like(f"{session_key}|%")))
        await db.flush()
        logger.info("chat_session_deleted", session_key=session_key)

    @staticmethod
    async def cleanup_old_sessions(db: AsyncSession, days: int) -> int:
        """Delete sessions idle longer than ``days`` (the daily cron)."""
        if days <= 0:
            return 0
        cutoff = _now() - timedelta(days=days)
        old = list(
            (
                await db.execute(
                    select(ChatSession).where(ChatSession.last_activity_at < cutoff)
                )
            ).scalars().all()
        )
        for s in old:
            await db.delete(s)
            await db.execute(
                delete(ChatPresence).where(ChatPresence.session_key.like(f"{s.session_key}|%"))
            )
        await db.execute(
            delete(ChatPresence).where(ChatPresence.last_seen < _now() - timedelta(days=1))
        )
        await db.flush()
        return len(old)


async def flow_lock_acquired(session_key: str, digest: str) -> bool:
    """Idempotency lock for a completed quick-flow (shared by routes + bridge).

    The SAME flow submitted twice within 5s must store once (plugin parity —
    php:1142 has a transient 5s lock; the REST route had it, the bridge did not,
    so a double-click on the last flow button stored duplicate messages).

    Returns ``True`` when the caller MAY proceed, ``False`` when this exact flow
    was already handled moments ago. The digest MUST be a content hash (see the
    route: ``hash()`` is salted per process and a length collides). A Redis blip
    returns ``True`` — never drop a flow because the cache is down.
    """
    from app.core.cache.redis import get_redis

    lock_key = f"chat:flow_lock:{session_key}:{digest}"
    try:
        redis = await get_redis()
        return bool(await redis.set(lock_key, "1", nx=True, ex=5))
    except Exception:  # noqa: BLE001
        return True


def _human_ago(dt: datetime | None) -> str:
    """Persian relative time ("۳ دقیقه پیش") for the conversation list."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    diff = int((_now() - dt).total_seconds())
    if diff < 60:
        return "همین حالا"
    if diff < 3600:
        return f"{diff // 60} دقیقه پیش"
    if diff < 86400:
        return f"{diff // 3600} ساعت پیش"
    return f"{diff // 86400} روز پیش"


_JALALI_MONTHS = [
    "",
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]


def _format_last_seen(dt: datetime | None, date_format: str = "shamsi") -> str:
    """Relative "last seen" label, plugin parity (php `format_last_seen` L1780).

    <15s online, then seconds/minutes/hours ago; older shows a clock time with
    today/yesterday (shamsi month names when `date_format == "shamsi"`).
    """
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    now = _now()
    diff = int((now - dt).total_seconds())
    if diff < 15:
        return "🟢 آنلاین"
    if diff < 60:
        return f"{diff} ثانیه پیش"
    if diff < 3600:
        return f"{diff // 60} دقیقه پیش"
    if diff < 86400:
        return f"{diff // 3600} ساعت پیش"

    from app.core.jalali import gregorian_to_jalali

    time_part = dt.strftime("%H:%M")
    if date_format == "shamsi":
        jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
        ty, tm, td = gregorian_to_jalali(now.year, now.month, now.day)
        y = now - timedelta(days=1)
        yy, ym, yd = gregorian_to_jalali(y.year, y.month, y.day)
        if (jy, jm, jd) == (ty, tm, td):
            return f"امروز {time_part}"
        if (jy, jm, jd) == (yy, ym, yd):
            return f"دیروز {time_part}"
        return f"{jd} {_JALALI_MONTHS[jm]} {time_part}"
    if dt.date() == now.date():
        return f"Today {time_part}"
    if dt.date() == (now - timedelta(days=1)).date():
        return f"Yesterday {time_part}"
    return dt.strftime("%b %d") + f" {time_part}"
