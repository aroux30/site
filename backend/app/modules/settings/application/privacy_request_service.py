"""Data-subject request queue (GDPR articles 15 & 17).

``PrivacyService`` in ``privacy_service.py`` does the *work* — it exports or
erases a user's data. It was reachable only by an operator typing a UUID.
This service adds the part GDPR actually requires: the subject raises the
request, sees its status, and collects the result, without an operator in the
loop.

Owner scoping is the load-bearing property of every method here. The subject's
identity comes from the access token and is passed in as ``user_id``; it is
never read from a request body, path, or query. There is deliberately no
method signature that accepts both an actor and a subject, because a
``process(user_id, request_id)`` pair is one missing ``where`` clause away
from leaking one customer's data to another.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, null, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.core.security.password import verify_dummy_password, verify_password
from app.modules.settings.application.privacy_service import PrivacyService
from app.modules.settings.domain.models import (
    PrivacyRequest,
    PrivacyRequestStatus,
    PrivacyRequestType,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: How long a produced export stays readable. Article 12(3) gives the subject
#: one month to collect a copy; the payload is a full PII dump sitting in a
#: table operators can query, so it is not kept beyond a working day by
#: default. The subject can always request a new one — the queue exists for it.
EXPORT_RESULT_TTL = timedelta(hours=24)

#: Site option holding the export-result retention window, in hours. An
#: operator with a longer internal SLA (or a legal review that wants the
#: copy gone sooner) sets this without a deploy. 0 or unset keeps the default.
EXPORT_RETENTION_HOURS_OPTION = "privacy.export_retention_hours"


async def export_result_ttl(db: "AsyncSession") -> timedelta:
    """The operator's export-result window, or the 24-hour default.

    Clamped low-to-high: a negative or absurd value is a typo, and the two
    failure directions are both bad — too short and the subject's copy expires
    before they open it, too long and a PII dump outlives its justification.
    The floor is 1 hour, the ceiling is Article 12(3)'s 30 days.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    hours = await SiteOptionsService.get_int(
        db,
        EXPORT_RETENTION_HOURS_OPTION,
        int(EXPORT_RESULT_TTL.total_seconds() // 3600),
        minimum=1,
        maximum=30 * 24,
    )
    return timedelta(hours=hours)

#: An erase request must be re-confirmed by password. It is irreversible, and
#: a hijacked session cookie is a much easier theft than a password.
ERASE_REQUIRES_PASSWORD = True


def _codes_match(stored: str, supplied: str) -> bool:
    """Constant-time comparison of two OTP codes.

    ``hmac.compare_digest`` rather than ``==``: a six-digit code has a million
    possibilities, and a timing side channel here would let an attacker narrow
    the value without ever seeing the code.
    """
    import hmac

    return hmac.compare_digest(str(stored or "").strip(), str(supplied or "").strip())


def _hash_confirm_token(token: str) -> str:
    """SHA-256 of an email confirmation token.

    Only the hash is stored, like the reset and email-change tokens: the
    plaintext exists solely in the email, so a database leak cannot be
    replayed to confirm somebody else's request.
    """
    import hashlib

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _confirm_link(token: str) -> str:
    """The public URL the confirmation email points at.

    Lands on the account privacy page rather than a dedicated route: the
    token redeems via an unauthenticated POST from that page, and a signed-in
    subject also sees their request list right there afterwards.
    """
    from app.core.config.settings import get_settings

    base = get_settings().STOREFRONT_BASE_URL.rstrip("/")
    return f"{base}/account/privacy?privacy_confirm_token={token}"


class PrivacyRequestService:
    """Create, list, and resolve data-subject requests."""

    # ── Customer side ───────────────────────────────────────────────────────

    @staticmethod
    async def submit(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        request_type: PrivacyRequestType,
        reason: str | None = None,
        password: str | None = None,
    ) -> PrivacyRequest:
        """Raise a request for the *calling* subject.

        The identity check is the whole safety argument: the returned row's
        ``user_id`` is the token's subject, never anything the caller sent.
        """
        from app.modules.users.domain.models import User

        user = await db.get(User, user_id)
        if user is None:
            raise NotFoundError("User")

        if request_type is PrivacyRequestType.ERASE:
            # Verify even when password is None: a falsy password must still
            # cost a verify (dummy hash) rather than skip the branch, so a
            # caller cannot distinguish "account has no password" from
            # "password required" by timing or by status code.
            candidate = password or ""
            if ERASE_REQUIRES_PASSWORD and (
                user.password_hash is None
                or not verify_password(candidate, user.password_hash)
            ):
                if user.password_hash is None:
                    verify_dummy_password(candidate)
                raise ValidationError("Password confirmation failed")
        elif password is not None:
            # An export is not irreversible, so it does not demand the
            # password — but if the subject volunteered one it is verified
            # rather than ignored, so the UI cannot show a green check it
            # never performed.
            if user.password_hash is None or not verify_password(password, user.password_hash):
                if user.password_hash is None:
                    verify_dummy_password(password)
                raise ValidationError("Password confirmation failed")

        await PrivacyRequestService._assert_no_open_request(db, user_id, request_type)

        request = PrivacyRequest(
            user_id=user_id,
            type=request_type,
            status=PrivacyRequestStatus.PENDING,
            reason=(reason or "").strip()[:2000] or None,
            verified_at=datetime.now(UTC),
        )
        db.add(request)
        await db.commit()
        await db.refresh(request)
        logger.info(
            "privacy_request_submitted",
            request_id=str(request.id),
            user_id=str(user_id),
            type=request_type.value,
        )

        # Issue the confirmation code. `confirm()` looks for an OTP whose
        # purpose is "privacy_confirm" and nothing in the codebase ever created
        # one, so the confirmation step was unreachable in the product: a user
        # could raise an erase request but never confirm it. Only ERASE needs it
        # — an export is reversible, and demanding a second factor to read your
        # own data would be the wrong trade.
        #
        # Failure here must not lose the request: it is already committed, and
        # the user can ask for a new code.
        if request_type is PrivacyRequestType.ERASE and user.phone:
            from app.modules.auth.application.auth_service import request_otp

            try:
                await request_otp(db, phone=user.phone, purpose="privacy_confirm")
                await db.commit()
            except Exception as exc:
                await db.rollback()
                await db.refresh(request)
                logger.warning(
                    "privacy_confirm_otp_issue_failed",
                    request_id=str(request.id),
                    user_id=str(user_id),
                    error=str(exc)[:200],
                )

        return request

    @staticmethod
    async def confirm(
        db: AsyncSession,
        *,
        request_id: uuid.UUID,
        user_id: uuid.UUID,
        code: str,
    ) -> PrivacyRequest:
        """Second-factor confirmation of the subject's own request.

        The model carries two timestamps on purpose: ``verified_at`` records the
        password re-entry that proves possession of the account, and
        ``confirmed_at`` records the second factor proving the person is at the
        device that owns it. Only ``verified_at`` was ever written, so the
        column designed for this step was dead — and an irreversible erase was
        reachable with a password alone.

        Password re-entry is the *account* factor; a stolen password passes it.
        The OTP is checked against the request, not against a session, so it
        cannot be satisfied by a login the attacker performed instead.
        """
        from app.modules.users.domain.models import OTPRequest, User

        request = await db.get(PrivacyRequest, request_id)
        if request is None or request.user_id != user_id:
            # 404 rather than 403: a mismatched owner must not learn the id
            # exists, which is itself an enumeration of other people's requests.
            raise NotFoundError("PrivacyRequest")

        if request.status is not PrivacyRequestStatus.PENDING:
            raise ValidationError("این درخواست قبلاً بررسی شده است.")

        if request.confirmed_at is not None:
            raise ValidationError("این درخواست قبلاً تأیید شده است.")

        user = await db.get(User, user_id)
        if user is None:
            raise NotFoundError("User")

        now = datetime.now(UTC)
        otp = (
            await db.execute(
                select(OTPRequest)
                .where(
                    OTPRequest.phone == user.phone,
                    OTPRequest.purpose == "privacy_confirm",
                    OTPRequest.is_used.is_(False),
                )
                .order_by(OTPRequest.created_at.desc())
            )
        ).scalars().first()
        if otp is None:
            raise ValidationError("کد تأیید یافت نشد یا منقضی شده است.")
        if otp.expires_at <= now:
            raise ValidationError("کد تأیید منقضی شده است.")

        # The code itself is compared here rather than trusted from the query:
        # selecting "the newest unused code for this phone" and confirming
        # without checking would let anyone who triggered an OTP confirm with
        # nothing at all.
        if not _codes_match(otp.code, code):
            otp.attempts = (otp.attempts or 0) + 1
            await db.commit()
            raise ValidationError("کد تأیید نادرست است.")

        otp.is_used = True
        request.confirmed_at = now
        await db.commit()
        await db.refresh(request)
        await logger.ainfo(
            "privacy_request_confirmed", request_id=str(request_id), user_id=str(user_id)
        )
        return request

    # ── Email confirmation (second path beside the OTP) ─────────────────────

    #: How long an emailed confirmation link stays usable. WordPress's
    #: user-request confirmation uses a day; a shorter window here matches the
    #: reset/change flows and limits the value of a leaked inbox.
    CONFIRM_EMAIL_TTL_HOURS = 24

    @staticmethod
    async def issue_email_confirmation(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Mail a confirmation link for the subject's own pending request.

        The OTP path proves the phone; this proves the mailbox. A subject whose
        number changed, or who is travelling without their SIM, otherwise has
        no way to confirm their own request — WordPress offers the same second
        path via ``wp_send_user_request``.

        Returns what happened rather than raising on a mail failure: the token
        is stored and can be re-sent, and the request itself is untouched.
        """
        import secrets

        from app.modules.users.domain.models import User

        request = await PrivacyRequestService.get_for_user(
            db, user_id=user_id, request_id=request_id
        )
        if request.status is not PrivacyRequestStatus.PENDING:
            raise ValidationError("این درخواست قبلاً بررسی شده است.")
        if request.confirmed_at is not None:
            raise ValidationError("این درخواست قبلاً تأیید شده است.")

        user = await db.get(User, user_id)
        target = (user.email or "").strip().lower() if user else ""
        if not target or "@" not in target:
            return {
                "sent": False,
                "reason": "no_email",
                "message": "این حساب ایمیل ثبت‌شده‌ای ندارد؛ از کد پیامکی استفاده کنید.",
            }

        token = secrets.token_urlsafe(48)
        request.confirm_token_hash = _hash_confirm_token(token)
        request.confirm_token_expires_at = datetime.now(UTC) + timedelta(
            hours=PrivacyRequestService.CONFIRM_EMAIL_TTL_HOURS
        )
        await db.commit()

        sent = False
        try:
            from app.modules.notifications.application.email_service import send_email

            link = _confirm_link(token)
            sent, _log = await send_email(
                db,
                recipient=target,
                subject="تأیید درخواست حریم خصوصی",
                html_body=(
                    '<div dir="rtl" style="font-family:Tahoma,sans-serif">'
                    "<p>برای تأیید درخواست حریم خصوصی خود روی پیوند زیر کلیک کنید:</p>"
                    f'<p><a href="{link}">{link}</a></p>'
                    f"<p>این پیوند تا {PrivacyRequestService.CONFIRM_EMAIL_TTL_HOURS} ساعت معتبر است "
                    "و فقط یک‌بار قابل استفاده است. "
                    "اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید و رمز عبور خود را تغییر دهید.</p>"
                    "</div>"
                ),
                text_body=(
                    "برای تأیید درخواست حریم خصوصی خود روی پیوند زیر کلیک کنید:\n\n"
                    f"{link}\n\n"
                    f"این پیوند تا {PrivacyRequestService.CONFIRM_EMAIL_TTL_HOURS} ساعت معتبر است."
                ),
            )
            sent = bool(sent)
        except Exception:  # noqa: BLE001 — a mail outage must not lose the token
            logger.exception(
                "privacy_confirm_email_send_failed",
                request_id=str(request_id),
                user_id=str(user_id),
            )

        return {
            "sent": sent,
            "reason": None if sent else "send_failed",
            "expires_in_hours": PrivacyRequestService.CONFIRM_EMAIL_TTL_HOURS,
            "message": (
                "پیوند تأیید به ایمیل شما فرستاده شد."
                if sent
                else "ارسال ایمیل ناموفق بود. لطفاً کمی بعد دوباره تلاش کنید."
            ),
        }

    @staticmethod
    async def confirm_by_email_token(
        db: AsyncSession,
        *,
        token: str,
    ) -> PrivacyRequest:
        """Redeem an emailed confirmation link.

        Unauthenticated by design, exactly like the email-change confirmation:
        the token was mailed to the account's own address, so possession is
        the proof being asked for, and requiring a session would break the
        flow for anyone whose login has since expired. High-entropy, stored
        hashed, single-use and short-lived.
        """
        supplied = (token or "").strip()
        if not supplied:
            raise ValidationError("توکن تأیید ارسال نشده است.")

        digest = _hash_confirm_token(supplied)
        request = (
            await db.execute(
                select(PrivacyRequest).where(
                    PrivacyRequest.confirm_token_hash == digest
                )
            )
        ).scalar_one_or_none()
        if request is None:
            raise ValidationError("لینک تأیید معتبر نیست.")

        if request.status is not PrivacyRequestStatus.PENDING:
            raise ValidationError("این درخواست قبلاً بررسی شده است.")
        if request.confirmed_at is not None:
            raise ValidationError("این درخواست قبلاً تأیید شده است.")

        now = datetime.now(UTC)
        if (
            request.confirm_token_expires_at is None
            or request.confirm_token_expires_at <= now
        ):
            raise ValidationError("مهلت این لینک به پایان رسیده است. لطفاً لینک تازه‌ای درخواست کنید.")

        request.confirmed_at = now
        # Consumed: a second click must not confirm twice, and the token should
        # not sit in the row after it has done its one job.
        request.confirm_token_hash = None
        request.confirm_token_expires_at = None
        await db.commit()
        await db.refresh(request)
        logger.info(
            "privacy_request_confirmed_by_email",
            request_id=str(request.id),
            user_id=str(request.user_id),
        )
        return request

    async def _assert_no_open_request(
        db: AsyncSession,
        user_id: uuid.UUID,
        request_type: PrivacyRequestType,
    ) -> None:
        """Refuse a second open request of the same type.

        Without this a subject can stack a hundred pending erases; the
        operator queue then shows work that can never be actioned because the
        first one already deleted the row the second names.
        """
        existing = (
            await db.execute(
                select(PrivacyRequest.id)
                .where(
                    PrivacyRequest.user_id == user_id,
                    PrivacyRequest.type == request_type,
                    PrivacyRequest.status.in_(
                        [PrivacyRequestStatus.PENDING, PrivacyRequestStatus.PROCESSING]
                    ),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(
                "An open request of this type already exists for this account"
            )

    @staticmethod
    async def list_for_user(db: AsyncSession, *, user_id: uuid.UUID) -> list[PrivacyRequest]:
        """Every request this subject has raised, newest first."""
        rows = (
            await db.execute(
                select(PrivacyRequest)
                .where(PrivacyRequest.user_id == user_id)
                .order_by(PrivacyRequest.created_at.desc())
            )
        ).scalars().all()
        return list(rows)

    @staticmethod
    async def get_for_user(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> PrivacyRequest:
        """One of the caller's own requests.

        The ``user_id`` predicate is the authorization check. A request
        belonging to somebody else is reported as not-found rather than
        forbidden: a 403 would confirm that the id exists, which is itself a
        small disclosure about another account.
        """
        request = (
            await db.execute(
                select(PrivacyRequest).where(
                    PrivacyRequest.id == request_id,
                    PrivacyRequest.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if request is None:
            raise NotFoundError("Privacy request")
        return request

    @staticmethod
    async def get_result(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Return the produced export payload, honouring its expiry.

        Reading the payload clears it in the same transaction: an export is a
        complete copy of the subject's personal data and the rule of thumb for
        data minimization is that a copy you already gave away should not sit
        in a database indefinitely waiting for a second download.
        """
        request = await PrivacyRequestService.get_for_user(
            db, user_id=user_id, request_id=request_id
        )
        if request.type is not PrivacyRequestType.EXPORT:
            raise ValidationError("Only export requests carry a downloadable result")
        if request.status not in (
            PrivacyRequestStatus.COMPLETED,
            PrivacyRequestStatus.PARTIAL,
        ):
            raise ValidationError("This request has no result yet")
        if request.result_payload is None:
            raise NotFoundError("Stored export")

        if request.result_expires_at is not None and request.result_expires_at <= datetime.now(
            UTC
        ):
            request.result_payload = None
            await db.commit()
            raise NotFoundError("Stored export")

        payload = request.result_payload
        request.result_payload = None
        await db.commit()
        return payload

    # ── Operator side ───────────────────────────────────────────────────────

    @staticmethod
    async def list_all(
        db: AsyncSession,
        *,
        status_filter: PrivacyRequestStatus | None = None,
        type_filter: PrivacyRequestType | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[PrivacyRequest], int]:
        """Paged queue for the admin screen, unhandled rows first."""
        stmt = select(PrivacyRequest)
        count_stmt = select(func.count()).select_from(PrivacyRequest)
        if status_filter is not None:
            stmt = stmt.where(PrivacyRequest.status == status_filter)
            count_stmt = count_stmt.where(PrivacyRequest.status == status_filter)
        if type_filter is not None:
            stmt = stmt.where(PrivacyRequest.type == type_filter)
            count_stmt = count_stmt.where(PrivacyRequest.type == type_filter)

        rows = (
            await db.execute(
                stmt.order_by(PrivacyRequest.created_at.asc()).offset(skip).limit(limit)
            )
        ).scalars().all()
        total = (await db.execute(count_stmt)).scalar_one()
        return rows, int(total)

    @staticmethod
    async def claim(
        db: AsyncSession,
        *,
        request_id: uuid.UUID,
        admin_id: uuid.UUID,
    ) -> PrivacyRequest:
        """Move a pending request to ``processing`` so only one operator acts.

        ``SELECT ... FOR UPDATE`` plus the status predicate is the whole
        guard: two operators clicking "process" at the same moment must not
        both run the erasure. A row already claimed is a conflict, not a
        silent success.
        """
        row = (
            await db.execute(
                select(PrivacyRequest)
                .where(PrivacyRequest.id == request_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Privacy request")
        if row.status is PrivacyRequestStatus.PROCESSING:
            raise ConflictError("This request is already being processed")
        if row.status in (PrivacyRequestStatus.COMPLETED, PrivacyRequestStatus.REJECTED):
            raise ConflictError(f"Request is already {row.status.value}")

        row.status = PrivacyRequestStatus.PROCESSING
        row.resolved_by = admin_id
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def _finish(
        db: AsyncSession,
        *,
        request: PrivacyRequest,
        payload: dict[str, Any],
        incomplete_sources: list[str] | None = None,
    ) -> PrivacyRequest:
        """Close out a request, honestly.

        ``incomplete_sources`` names the sources that did not finish. When it is
        non-empty the request is recorded as ``partial`` rather than
        ``completed``: an erasure that left the subject's orders or sessions
        intact is not an erasure that succeeded, and a subject told otherwise
        has been lied to about their own data.
        """
        request.status = (
            PrivacyRequestStatus.PARTIAL
            if incomplete_sources
            else PrivacyRequestStatus.COMPLETED
        )
        request.resolved_at = datetime.now(UTC)
        if request.type is PrivacyRequestType.EXPORT:
            request.result_payload = payload
            request.result_expires_at = datetime.now(UTC) + (
                await export_result_ttl(db)
            )
        else:
            # An erase produces actions, not a copy of the subject's data -- but
            # the per-source report is kept when something failed, because that
            # report is the only evidence an operator has of what is still
            # outstanding.
            request.result_payload = (
                None
                if not incomplete_sources
                else {"incomplete_sources": incomplete_sources}
            )
            request.result_expires_at = None
        await db.commit()
        # `db.refresh` raises "not persistent within this Session" on an instance
        # that belongs to a different session, or one already detached. That is
        # not this app's own session -- the factory sets expire_on_commit=False
        # -- but this method is also called from contexts where the request
        # object was loaded elsewhere. `db.get` re-reads by primary key and is
        # correct in every case, with a fallback if the row is somehow gone.
        stored = await db.get(PrivacyRequest, request.id)
        return stored if stored is not None else request

    @staticmethod
    async def run_export(
        db: AsyncSession,
        *,
        request_id: uuid.UUID,
        admin_id: uuid.UUID,
    ) -> PrivacyRequest:
        """Run the GDPR export for a queued request and store the payload.

        Uses the same registry-backed collection as the admin endpoint, so the
        archive a subject downloads is the one that was actually claimed complete
        — and the per-source report travels with it, which is what makes
        ``report["complete"]`` meaningful to whoever fulfils the request.
        """
        from app.modules.settings.application.privacy_sources import collect_export

        request = await PrivacyRequestService.claim(
            db, request_id=request_id, admin_id=admin_id
        )
        account = await PrivacyService.export_user_data(db, request.user_id)
        if "error" in account:
            request.status = PrivacyRequestStatus.PENDING
            request.resolved_by = None
            await db.commit()
            raise NotFoundError("User")

        archive = await collect_export(db, request.user_id)
        export = {
            **account,
            "sources": archive["data"],
            "report": archive["report"],
        }
        # The report is what says which sources failed, and the archive route's
        # own contract says a caller that serves the file MUST check it. Leaving
        # the status COMPLETED on a partial archive means the account page --
        # which only reads `status` -- offers a full download while 27 sources
        # are missing from it. The file is still produced: a partial archive
        # beats no archive, and the subject can see what is missing.
        await PrivacyRequestService._finish(
            db,
            request=request,
            payload=export,
            incomplete_sources=archive["report"]["failed_sources"] or None,
        )
        logger.info(
            "privacy_request_export_completed",
            request_id=str(request.id),
            user_id=str(request.user_id),
            admin_id=str(admin_id),
            # Logged so an incomplete archive is visible to an operator even
            # though the request itself succeeded and the subject was served.
            complete=archive["report"]["complete"],
            failed_sources=len(archive["report"]["failed_sources"]),
        )
        return request

    @staticmethod
    async def run_erase(
        db: AsyncSession,
        *,
        request_id: uuid.UUID,
        admin_id: uuid.UUID,
    ) -> PrivacyRequest:
        """Run the erasure for a queued request.

        ``anonymize`` is hard-coded True. The service's ``anonymize=False``
        branch is a hard delete that drops the account row, and a hard delete
        is the operator's tool for handling a support escalation — it is not
        something a customer can request of themselves through a web form.
        """
        request = await PrivacyRequestService.claim(
            db, request_id=request_id, admin_id=admin_id
        )
        result = await PrivacyService.erase_user_data(db, request.user_id, anonymize=True)
        if "error" in result:
            request.status = PrivacyRequestStatus.PENDING
            request.resolved_by = None
            await db.commit()
            raise NotFoundError("User")

        # The registry is the source of truth, not the hand-written pass above.
        # `erase_user_data` knew about four things (account, profile, comments,
        # user meta) while ~30 more were registered and never reached, so a
        # request reported success with orders, payments, wallet, tickets and
        # sessions still intact. Running the registered erasers first means the
        # payload reflects what actually happened, and a source that failed is
        # recorded as failed rather than counted as done.
        from app.modules.settings.application.privacy_sources import run_erasers

        try:
            eraser_results = await run_erasers(db, request.user_id)
            result = {
                **result,
                "sources": [
                    {
                        "source": r.exporter,
                        "items_removed": r.items_removed,
                        "items_retained": r.items_retained,
                        "retained_reason": r.retained_reason,
                        "error": r.error,
                    }
                    for r in eraser_results
                ],
            }
        except Exception as exc:  # noqa: BLE001
            # The core anonymisation above already ran; failing loudly here beats
            # recording a "complete" erasure that skipped the registry. The
            # registry itself failing counts as incomplete too -- it means none
            # of the registered sources were attempted.
            eraser_results = []
            incomplete = ["__registry__"]
            result = {**result, "sources_error": str(exc)[:300]}
        else:
            incomplete = [r.exporter for r in eraser_results if r.error]

        # Gate the status on what actually happened. Computing `failed` and
        # logging it is not the same as acting on it: without this, every
        # erasure was recorded as COMPLETED no matter how many sources blew up.
        await PrivacyRequestService._finish(
            db,
            request=request,
            payload=result,
            incomplete_sources=incomplete,
        )
        logger.info(
            "privacy_request_erase_completed",
            request_id=str(request.id),
            user_id=str(request.user_id),
            admin_id=str(admin_id),
            actions=result.get("actions"),
            eraser_sources=len(eraser_results),
            eraser_failed=len(incomplete),
        )
        return request

    @staticmethod
    async def reject(
        db: AsyncSession,
        *,
        request_id: uuid.UUID,
        admin_id: uuid.UUID,
        note: str,
    ) -> PrivacyRequest:
        """Decline a request with a reason the operator writes.

        The note is mandatory: a rejected GDPR request with no stated reason
        is not a decision, it is an omission, and the subject has a right to
        contest it.
        """
        text = (note or "").strip()
        if not text:
            raise ValidationError("A rejection reason is required")

        request = (
            await db.execute(
                select(PrivacyRequest).where(PrivacyRequest.id == request_id)
            )
        ).scalar_one_or_none()
        if request is None:
            raise NotFoundError("Privacy request")
        if request.status in (PrivacyRequestStatus.COMPLETED, PrivacyRequestStatus.REJECTED):
            raise ConflictError(f"Request is already {request.status.value}")

        request.status = PrivacyRequestStatus.REJECTED
        request.admin_note = text[:2000]
        request.resolved_by = admin_id
        request.resolved_at = datetime.now(UTC)
        # A rejected request never produced data, so nothing may linger in the
        # payload column even if a previous operator had filled it.
        request.result_payload = None
        request.result_expires_at = None
        await db.commit()
        stored = await db.get(PrivacyRequest, request.id)
        request = stored if stored is not None else request
        logger.info(
            "privacy_request_rejected",
            request_id=str(request.id),
            user_id=str(request.user_id),
            admin_id=str(admin_id),
        )
        return request

    @staticmethod
    async def purge_expired(db: AsyncSession) -> int:
        """Delete export payloads past their expiry. Returns rows touched.

        Expiry-on-read already clears a payload when the subject collects it;
        this is the path for a subject who never comes back for theirs.

        The type is compared by member name, not by the enum's value: this
        project's SQLAlchemy enums persist the NAME ("EXPORT"), and this method
        compared against the value ("export"), so it matched nothing. The purge
        had never run once — the route worked, the schedule called it, and it
        cleared zero rows every time, silently.

        The clearing itself is a bulk UPDATE to SQL NULL rather than an
        assignment of ``None`` to the ORM attribute, and the difference is the
        whole bug. ``result_payload`` is JSONB, and JSONB has its own null: an
        ORM assignment of ``None`` serializes to the JSON value ``null``, which
        is *not* SQL NULL — ``'null'::jsonb IS NULL`` is false. So the rows the
        purge "cleared" kept a non-null payload column, failed their own
        ``result_payload IS NOT NULL`` filter on the next run, and were
        re-selected and re-cleared every day forever. A subject's full data dump
        sat in the table permanently, under a task whose logs said it worked.
        """
        result = await db.execute(
            update(PrivacyRequest)
            .where(
                PrivacyRequest.type == PrivacyRequestType.EXPORT.name,
                PrivacyRequest.result_payload.is_not(None),
                PrivacyRequest.result_expires_at.is_not(None),
                PrivacyRequest.result_expires_at <= datetime.now(UTC),
            )
            .values(result_payload=null())
            .execution_options(synchronize_session=False)
        )
        await db.commit()
        purged = int(result.rowcount or 0)
        logger.info("privacy_request_results_purged", count=purged)
        return purged
