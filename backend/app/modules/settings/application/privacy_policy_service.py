"""The privacy policy a consent form links to.

WordPress's ``get_privacy_policy_link()`` returns the URL of the published
privacy-policy page, or an empty string when there is none. That empty string
*is* the contract, not an edge case: a form that links to a 404 while asking a
visitor for their phone number is worse than a form that says nothing, because
the visitor has no way to tell the difference between "this store has no policy"
and "the page is broken".

So this service answers one question with three outcomes — a published, public
page; nothing at all; and everything else, which does not exist. A draft is a
document nobody consented to, and a private page is one the operator chose to
hide, so both are treated as "there is no policy" rather than leaked by their
existence.

The page is named by the ``privacy.policy_page`` setting, the same way
WordPress names it: an option holding a slug, so an operator can publish the
policy as an ordinary CMS page and edit it without a deploy.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.domain.models import (
    CmsPage,
    PageStatus,
    PageVisibility,
)
from app.modules.settings.application.site_options_service import SiteOptionsService

#: The site option naming the policy page. A slug, not an id, so the setting
#: survives a re-import of the content table.
PRIVACY_POLICY_OPTION = "privacy.policy_page"


class PrivacyPolicyService:
    """Resolve the published privacy policy for public surfaces."""

    @staticmethod
    async def get_policy(db: AsyncSession) -> dict[str, Any] | None:
        """The policy's ``title``, ``slug`` and ``url``, or ``None``.

        ``None`` is the normal answer for a store that has not published a
        policy, and the route turns it into an all-``None`` response rather than
        a 404 — a 404 would read to the client as a network failure and every
        form would treat it as an error to report.
        """
        slug = (
            await SiteOptionsService.get(db, PRIVACY_POLICY_OPTION, "") or ""
        ).strip()
        if not slug:
            return None

        page = (
            await db.execute(select(CmsPage).where(CmsPage.slug == slug))
        ).scalar_one_or_none()
        if page is None:
            return None

        # Both conditions, not either. `status` and `visibility` are separate
        # axes by design (see PageVisibility's docstring): a page can be
        # published *and* private, and requiring only `published` would serve a
        # document the operator deliberately hid — and its very existence on a
        # public page leaks that it is there.
        if page.status != PageStatus.PUBLISHED:
            return None
        if page.visibility != PageVisibility.PUBLIC:
            return None

        return {
            "title": page.title,
            "slug": page.slug,
            "url": f"/{page.slug}",
        }
