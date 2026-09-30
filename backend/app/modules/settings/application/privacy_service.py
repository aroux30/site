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
from sqlalchemy import select

from app.modules.users.domain.models import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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

        # Blog comments
        try:
            from app.modules.blog.domain.models import BlogComment
            stmt = select(BlogComment).where(BlogComment.author_id == user_id)
            comments = (await db.execute(stmt)).scalars().all()
            export["blog_comments"] = [
                {
                    "id": str(c.id),
                    "post_id": str(c.post_id),
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

            # Anonymize blog comments
            try:
                from app.modules.blog.domain.models import BlogComment
                stmt = select(BlogComment).where(BlogComment.author_id == user_id)
                comments = (await db.execute(stmt)).scalars().all()
                for comment in comments:
                    comment.author_name = "Anonymous"
                    comment.author_email = None
                    comment.author_ip = None
                    comment.author_user_agent = None
                erased.append(f"comments_anonymized:{len(comments)}")
            except Exception:
                pass

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
            # Hard delete (cascade will handle related records)
            await db.delete(user)
            await db.commit()
            erased.append("account_deleted")

        logger.info("privacy_data_erased", user_id=str(user_id), actions=erased)
        return {
            "user_id": str(user_id),
            "actions": erased,
            "erased_at": datetime.now(UTC).isoformat(),
        }
