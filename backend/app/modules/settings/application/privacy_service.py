"""GDPR/Privacy tools service (WordPress privacy parity).

Provides data export and erasure capabilities for user data as required
by GDPR (General Data Protection Regulation) and similar privacy laws.

Features:
- Export the account, profile and addresses as JSON
- Anonymize/erase user data on request

Scope note: the full per-source export and erasure is implemented by
``privacy_sources`` / ``privacy_core_sources`` — 45 registered sources covering
every user-owned table. This module keeps the account-level entry points and the
rich field-level payloads; the registry drives coverage counting and the
per-source report that accompanies a data-subject request.

Deliberately not implemented here: a consent log. A docstring once claimed one
and no code existed behind it; the claim was removed rather than left standing.

Usage:
    data = await PrivacyService.export_user_data(db, user_id)
    result = await PrivacyService.erase_user_data(db, user_id)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import or_, select

from app.core.security.ip_anonymize import anonymize_ip
from app.modules.users.domain.models import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _comments_by_subject(author_id: uuid.UUID, email: str | None):
    """Every comment a subject wrote, signed-in or as a guest.

    A guest comment has no ``author_id`` — it carries an email and nothing else.
    Selecting on the id alone therefore misses all of them, which meant a subject
    who had commented before registering got an export with no comments in it and
    an erasure that left their email and IP sitting in a public comment table
    forever. Both are the same defect seen from two sides, so both call this.

    The email is matched case-insensitively because a comment form lowercases
    what it is given while an account address is stored as typed, and a guest who
    wrote ``Ali@Example.com`` and later registered ``ali@example.com`` is the
    same person.

    A NULL email matches nothing: the comparison is written so that an account
    with no address cannot pick up every anonymous comment in the table.
    """
    from app.modules.blog.domain.models import BlogComment

    # No address on the account means guest comments cannot be attributed to it,
    # and an ilike against NULL matches nothing, so the fallback is simply the id.
    conditions = (
        [BlogComment.author_id == author_id, BlogComment.author_email.ilike(email)]
        if email
        else [BlogComment.author_id == author_id]
    )

    return select(BlogComment).where(or_(*conditions))



class PrivacyService:
    """GDPR-compliant data export and erasure."""

    @staticmethod
    async def export_user_data(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
        """Export all stored data for a user as a JSON-serializable dict."""
        # Eager-load relationships: attribute access on lazy("select")
        # relationships raises MissingGreenlet inside an async session.
        from sqlalchemy.orm import selectinload

        user = (
            await db.execute(
                select(User)
                .options(selectinload(User.profile), selectinload(User.addresses))
                .where(User.id == user_id)
            )
        ).scalar_one_or_none()
        if not user:
            return {"error": "User not found"}

        export: dict[str, Any] = {
            "export_date": datetime.now(UTC).isoformat(),
            "user_id": str(user_id),
            "account": {
                "phone": user.phone,
                "email": user.email,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "created_at": str(user.created_at),
                "last_login": str(user.last_login) if user.last_login else None,
            },
        }

        # Profile
        if user.profile:
            export["profile"] = {
                "first_name": user.profile.first_name,
                "last_name": user.profile.last_name,
                "national_code": user.profile.national_code,
                "birth_date": str(user.profile.birth_date) if user.profile.birth_date else None,
                "gender": user.profile.gender,
                "company_name": user.profile.company_name,
            }

        # Addresses. Every column is exported, not just the id: Article 15 is a
        # right of *access* to the data, and an address row reduced to an id and
        # a timestamp tells the subject nothing about the address they gave us.
        if user.addresses:
            export["addresses"] = [
                {
                    "id": str(addr.id),
                    "title": addr.title,
                    "province": addr.province,
                    "city": addr.city,
                    "district": addr.district,
                    "postal_code": addr.postal_code,
                    "full_address": addr.full_address,
                    # Coordinates are personal data too — they are part of what
                    # the subject gave us, so they travel with the export rather
                    # than being quietly dropped.
                    "lat": addr.lat,
                    "lng": addr.lng,
                    "is_default": addr.is_default,
                    "created_at": str(addr.created_at),
                }
                for addr in user.addresses
            ]

        # Blog comments, signed-in and guest alike — see _comments_by_subject.
        try:
            stmt = _comments_by_subject(user_id, user.email)
            comments = (await db.execute(stmt)).scalars().all()
            export["blog_comments"] = [
                {
                    "id": str(c.id),
                    "post_id": str(c.post_id),
                    # Which of the two it was, because a subject reading their own
                    # export otherwise cannot tell a comment they signed in to post
                    # from one they left under a different name before registering.
                    "guest": c.author_id is None,
                    "content": c.content[:200],
                    "created_at": str(c.created_at),
                }
                for c in comments
            ]
        except Exception as exc:
            # Recorded, not swallowed: a schema error here used to produce an
            # empty list, so the export looked complete while silently omitting
            # the subject's own writing. The per-source registry exists to make
            # exactly this visible.
            logger.exception("privacy_export_blog_comments_failed", user_id=str(user_id))
            export["blog_comments"] = []
            export.setdefault("incomplete", []).append(f"blog_comments: {exc}")

        # User meta
        try:
            from app.modules.blog.domain.wp_parity_models import UserMeta
            stmt = select(UserMeta).where(UserMeta.user_id == user_id)
            metas = (await db.execute(stmt)).scalars().all()
            export["user_meta"] = {m.meta_key: m.meta_value for m in metas}
        except Exception as exc:
            logger.exception("privacy_export_user_meta_failed", user_id=str(user_id))
            export["user_meta"] = {}
            export.setdefault("incomplete", []).append(f"user_meta: {exc}")

        logger.info("privacy_data_exported", user_id=str(user_id))
        return export

    @staticmethod
    async def erase_user_data(
        db: AsyncSession,
        user_id: uuid.UUID,
        *,
        anonymize: bool = True,
    ) -> dict[str, Any]:
        """Erase or anonymize a user's personal data (GDPR right to erasure).

        When anonymize=True (default), replaces PII with placeholder values
        but keeps the account shell for referential integrity.
        When anonymize=False, performs a hard delete.
        """
        # Same async eager-load requirement as export_user_data.
        from sqlalchemy.orm import selectinload

        user = (
            await db.execute(
                select(User)
                .options(selectinload(User.profile))
                .where(User.id == user_id)
            )
        ).scalar_one_or_none()
        if not user:
            return {"error": "User not found"}

        erased: list[str] = []

        if anonymize:
            # Captured before it is cleared below. The guest-comment pass needs
            # the address to find the comments this subject left before they had
            # an account, and running that pass after `user.email = None` finds
            # nothing — which is how the original code came to leave every one of
            # them, with their email and IP, in a public comment table.
            subject_email = user.email

            # Anonymize account.
            # The placeholder is 7 + 7 chars, not "deleted-" + 8: users.phone
            # is String(15), and the longer form raised StringDataRightTruncation
            # on commit — so every anonymisation ever attempted on this schema
            # failed and rolled back rather than half-erasing an account. The
            # leading "d" also keeps it clear of a real Iranian mobile number.
            user.phone = f"deleted-{str(user_id)[:7]}"
            user.email = None
            user.password_hash = None
            user.is_active = False
            user.totp_secret = None
            user.totp_enabled = False
            user.deleted_at = datetime.now(UTC)
            erased.append("account_anonymized")

            # Anonymize profile
            if user.profile:
                user.profile.first_name = "Deleted"
                user.profile.last_name = "User"
                user.profile.national_code = None
                user.profile.birth_date = None
                user.profile.avatar_url = None
                user.profile.gender = None
                user.profile.company_name = None
                user.profile.tax_exemption_certificate_no = None
                erased.append("profile_anonymized")

            # Anonymize blog comments, guest ones included. The bare
            # `pass` here used to hide a failure that left the subject's email
            # and IP in a comment everyone can read, so the count is reported
            # only when the pass actually completed.
            try:
                stmt = _comments_by_subject(user_id, subject_email)
                comments = (await db.execute(stmt)).scalars().all()
                for comment in comments:
                    comment.author_name = "Anonymous"
                    comment.author_email = None
                    comment.author_url = None
                    # Masked to the network, not blanked. WordPress's
                    # wp_comments_personal_data_eraser does the same: a flood
                    # check still groups comments by network, so spam from one
                    # subnet keeps being caught, while an operator can no longer
                    # read which household a particular comment came from. NULL
                    # throws the column away for everyone and loses the
                    # anti-abuse signal with it.
                    comment.author_ip = anonymize_ip(comment.author_ip)
                    comment.author_user_agent = None
                erased.append(f"comments_anonymized:{len(comments)}")
            except Exception as exc:
                # A failure must be visible in the per-source report, not just
                # in a worker log: the subject is told which sources did not
                # finish, and "everything was erased" is not one of them.
                logger.exception("privacy_erase_blog_comments_failed", user_id=str(user_id))
                erased.append(f"comments_anonymize_failed: {exc}")

            # Delete user meta
            try:
                from sqlalchemy import delete

                from app.modules.blog.domain.wp_parity_models import UserMeta
                await db.execute(delete(UserMeta).where(UserMeta.user_id == user_id))
                erased.append("user_meta_deleted")
            except Exception:
                pass

            await db.commit()

            # The account is deactivated, but every access token the subject
            # already holds stays valid until it expires on its own: the
            # auth dependency consults the revocation denylist, not
            # ``users.is_active``. Without this the "erased" user could keep
            # reading their own (now anonymised) data for the rest of the
            # token's TTL, and — for a hard delete, which drops the row — could
            # keep calling endpoints whose handler never reloads the user.
            from app.core.security import revocation

            await revocation.denylist_user(user_id)
            erased.append("sessions_revoked")
        else:
            # Hard delete. The cascade takes signed-in comments with it, because
            # they hang off the user by foreign key. Guest comments do not hang
            # off anything — they carry an email and an IP and no owner — so the
            # cascade cannot reach them and the account can be deleted while the
            # subject's identifying data is still sitting in a public table. They
            # are anonymized first, using the address captured before the delete.
            guest_pass_ok = True
            try:
                stmt = _comments_by_subject(user_id, user.email)
                comments = (await db.execute(stmt)).scalars().all()
                for comment in comments:
                    comment.author_name = "Anonymous"
                    comment.author_email = None
                    comment.author_url = None
                    comment.author_ip = anonymize_ip(comment.author_ip)
                    comment.author_user_agent = None
                await db.commit()
                erased.append(f"comments_anonymized:{len(comments)}")
            except Exception as exc:
                await db.rollback()
                guest_pass_ok = False
                logger.exception(
                    "privacy_erase_guest_comments_failed", user_id=str(user_id)
                )
                erased.append(f"comments_anonymize_failed: {exc}")

            await db.delete(user)
            await db.commit()
            if not guest_pass_ok:
                # Said plainly rather than reported as a clean delete: the account
                # is gone either way, so the caller cannot retry, and whoever
                # reads this has to know the guest comments outlived it.
                logger.error(
                    "privacy_erase_account_deleted_with_comments_intact",
                    user_id=str(user_id),
                )
            erased.append("account_deleted")

        logger.info("privacy_data_erased", user_id=str(user_id), actions=erased)
        return {
            "user_id": str(user_id),
            "actions": erased,
            "erased_at": datetime.now(UTC).isoformat(),
        }
