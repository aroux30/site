"""Admin global search: one box over orders, customers, tickets, products.

ERP benchmark gap analysis (feature #12 Search, P1). The platform's search was
storefront-only: Elasticsearch indexes *products*, so support staff hunting an
order number, a customer's phone, or a ticket number had to know which admin
page to open and what identifier to type. The gap is not ranking quality — it
is that three of the four things an operator looks for are not in any index.

Why PostgreSQL rather than the Elasticsearch projection
------------------------------------------------------
ADR-009 is explicit: PostgreSQL is the source of truth and Elasticsearch is a
read-only projection kept current by events. For a *storefront* search that
trade is right — relevance ranking matters and a few seconds of lag is
invisible. For a *support* search it is backwards:

* an operator looking up the order a customer is on the phone about needs the
  order that was created 30 seconds ago, not the one the projection has;
* ticket subjects and customer names are exact-ish lookups over modest tables,
  where ``ILIKE`` with an index is already fast;
* a lagging index produces "not found" for a record the operator can see on
  another screen, which reads as a bug and destroys trust in the tool.

So this service queries the source of truth directly. If search volume ever
makes that a problem, the right move is a projection *of these tables too*,
not a partial one that lies about recency.

Scope note: the query text is never interpolated into SQL — every term goes
through SQLAlchemy's bound parameters, and the ``ILIKE`` patterns escape the
wildcards a user can type (``%``, ``_``) so a search for "50%" does not become
a match-everything.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import or_, select

from app.modules.catalog.domain.models import Product
from app.modules.orders.domain.models import Order
from app.modules.support.domain.models import SupportTicket
from app.modules.users.domain.models import User, UserProfile
from app.modules.vendors.domain.models import Vendor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Rows returned per entity type. Small on purpose: this is a "jump to the
#: right record" box, not a report — the operator narrows by opening the
#: entity's own page, which has real filters.
DEFAULT_PER_TYPE_LIMIT = 5

#: A term shorter than this matches almost everything (`a`), which is both
#: useless and expensive. Two characters is the shortest useful
#: discriminator for a Persian query.
MIN_TERM_LENGTH = 2

#: Entity types this box searches, with their Persian labels.
SEARCHABLE_ENTITIES = {
    "order": "سفارش",
    "customer": "مشتری",
    "ticket": "تیکت",
    "product": "محصول",
    "vendor": "فروشنده",
    "blog_post": "نوشته",
    "cms_page": "صفحه",
}


def escape_like(term: str) -> str:
    """Escape LIKE wildcards so a user's ``%`` is a literal. Pure.

    Without this, searching for "50%" turns into "match anything starting
    with 50", and searching for "_" matches everything. The escape character
    is declared explicitly in the ``ilike(..., escape=...)`` calls below.
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def normalise_term(raw: str) -> str:
    """Trim and convert Persian/Arabic-Indic digits to ASCII. Pure.

    An operator reading an order number off a Persian receipt copies it in
    Persian digits; the column stores ASCII. Normalising means both forms
    find the same row.
    """
    if not raw:
        return ""
    persian = "۰۱۲۳۴۵۶۷۸۹"
    arabic = "٠١٢٣٤٥٦٧٨٩"
    table = {ord(p): str(i) for i, p in enumerate(persian)}
    table.update({ord(a): str(i) for i, a in enumerate(arabic)})
    return raw.translate(table).strip()


@dataclass
class SearchHit:
    """One result row, shaped the same regardless of which table it came from.

    ``url`` is built here rather than in the frontend so the mapping from
    entity to admin route lives next to the query that produced the row —
    adding an entity type does not require touching the UI.
    """

    entity_type: str
    entity_id: str
    title: str
    subtitle: str | None = None
    status: str | None = None
    url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_label": SEARCHABLE_ENTITIES.get(self.entity_type, self.entity_type),
            "entity_id": self.entity_id,
            "title": self.title,
            "subtitle": self.subtitle,
            "status": self.status,
            "url": self.url,
            "extra": self.extra,
        }


def _like(term: str) -> str:
    return f"%{escape_like(term)}%"


async def _search_orders(
    db: AsyncSession, term: str, limit: int
) -> list[SearchHit]:
    """Orders by number, or by the customer's phone/name.

    Order-number matches are exact-prefix and sorted first: an operator who
    pastes a full order number wants that order, not the five others that
    happen to contain the digits.
    """
    pattern = _like(term)
    stmt = (
        select(Order)
        .outerjoin(User, Order.user_id == User.id)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(
            or_(
                Order.order_number.ilike(pattern, escape="\\"),
                User.phone.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
                UserProfile.first_name.ilike(pattern, escape="\\"),
                UserProfile.last_name.ilike(pattern, escape="\\"),
            )
        )
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return [
        SearchHit(
            entity_type="order",
            entity_id=str(order.id),
            title=order.order_number,
            subtitle=None,
            status=getattr(order.status, "value", str(order.status)),
            url=f"/admin/orders?search={order.order_number}",
            extra={"total_rial": order.total, "created_at": order.created_at.isoformat()},
        )
        for order in rows
    ]


async def _search_customers(
    db: AsyncSession, term: str, limit: int
) -> list[SearchHit]:
    """Customers by phone, email, or name."""
    pattern = _like(term)
    stmt = (
        select(User, UserProfile)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(
            or_(
                User.phone.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
                UserProfile.first_name.ilike(pattern, escape="\\"),
                UserProfile.last_name.ilike(pattern, escape="\\"),
            )
        )
        .order_by(User.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    hits: list[SearchHit] = []
    for user, profile in rows:
        name = " ".join(
            part
            for part in (
                getattr(profile, "first_name", None),
                getattr(profile, "last_name", None),
            )
            if part
        )
        hits.append(
            SearchHit(
                entity_type="customer",
                entity_id=str(user.id),
                title=name or user.phone,
                subtitle=user.phone,
                status="active" if user.is_active else "inactive",
                url=f"/admin/users?search={user.phone}",
                extra={"email": user.email},
            )
        )
    return hits


async def _search_tickets(
    db: AsyncSession, term: str, limit: int
) -> list[SearchHit]:
    """Support tickets by number or subject."""
    pattern = _like(term)
    stmt = (
        select(SupportTicket)
        .where(
            or_(
                SupportTicket.ticket_number.ilike(pattern, escape="\\"),
                SupportTicket.subject.ilike(pattern, escape="\\"),
            )
        )
        .order_by(SupportTicket.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return [
        SearchHit(
            entity_type="ticket",
            entity_id=str(ticket.id),
            title=ticket.subject,
            subtitle=ticket.ticket_number,
            status=getattr(ticket.status, "value", str(ticket.status)),
            url=f"/admin/tickets?search={ticket.ticket_number}",
        )
        for ticket in rows
    ]


async def _search_products(
    db: AsyncSession, term: str, limit: int
) -> list[SearchHit]:
    """Products by name or SKU.

    Deliberately the source-of-truth table rather than the ES index: an
    operator checking whether a product exists wants the answer now, and the
    product they just created must be findable.
    """
    from app.modules.catalog.domain.models import ProductVariant

    pattern = _like(term)
    stmt = (
        select(Product)
        .outerjoin(ProductVariant, ProductVariant.product_id == Product.id)
        .where(
            or_(
                Product.name.ilike(pattern, escape="\\"),
                Product.slug.ilike(pattern, escape="\\"),
                ProductVariant.sku.ilike(pattern, escape="\\"),
            )
        )
        .order_by(Product.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).unique().scalars().all()

    return [
        SearchHit(
            entity_type="product",
            entity_id=str(product.id),
            title=product.name,
            subtitle=product.slug,
            status=getattr(product.status, "value", str(product.status)),
            url=f"/admin/products?search={product.slug}",
        )
        for product in rows
    ]


async def _search_vendors(
    db: AsyncSession, term: str, limit: int
) -> list[SearchHit]:
    """Vendors by store name or slug."""
    pattern = _like(term)
    stmt = (
        select(Vendor)
        .where(
            or_(
                Vendor.store_name.ilike(pattern, escape="\\"),
                Vendor.slug.ilike(pattern, escape="\\"),
            )
        )
        .order_by(Vendor.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return [
        SearchHit(
            entity_type="vendor",
            entity_id=str(vendor.id),
            title=vendor.store_name,
            subtitle=vendor.slug,
            status="active" if getattr(vendor, "is_active", True) else "inactive",
            url=f"/admin/procurement/suppliers?search={vendor.slug}",
        )
        for vendor in rows
    ]


async def _search_blog_posts(
    db: AsyncSession, term: str, limit: int
) -> list[SearchHit]:
    """Blog posts by title or slug.

    The source-of-truth table rather than the ES index, like the other
    collectors: an editor checking whether their post exists wants the answer
    now, and a post created a minute ago must be findable.
    """
    from app.modules.blog.domain.models import BlogPost

    pattern = _like(term)
    stmt = (
        select(BlogPost)
        .where(
            or_(
                BlogPost.title.ilike(pattern, escape="\\"),
                BlogPost.slug.ilike(pattern, escape="\\"),
            ),
            BlogPost.deleted_at.is_(None),
        )
        .order_by(BlogPost.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        SearchHit(
            entity_type="blog_post",
            entity_id=str(post.id),
            title=post.title,
            subtitle=post.slug,
            status=getattr(post.status, "value", str(post.status)),
            url=f"/admin/blog?post={post.id}",
            extra={"locale": post.locale},
        )
        for post in rows
    ]


async def _search_cms_pages(
    db: AsyncSession, term: str, limit: int
) -> list[SearchHit]:
    """CMS pages by title or slug — the other half of the content tree."""
    from app.modules.content.domain.models import CmsPage

    pattern = _like(term)
    stmt = (
        select(CmsPage)
        .where(
            or_(
                CmsPage.title.ilike(pattern, escape="\\"),
                CmsPage.slug.ilike(pattern, escape="\\"),
            ),
            CmsPage.deleted_at.is_(None),
        )
        .order_by(CmsPage.updated_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        SearchHit(
            entity_type="cms_page",
            entity_id=str(page.id),
            title=page.title,
            subtitle=page.slug,
            status=getattr(page.status, "value", str(page.status)),
            url=f"/admin/pages?page={page.id}",
        )
        for page in rows
    ]


#: entity type -> collector. Order matters only for output grouping.
_COLLECTORS = {
    "order": _search_orders,
    "customer": _search_customers,
    "ticket": _search_tickets,
    "product": _search_products,
    "vendor": _search_vendors,
    "blog_post": _search_blog_posts,
    "cms_page": _search_cms_pages,
}


async def global_search(
    db: AsyncSession,
    term: str,
    *,
    entities: list[str] | None = None,
    per_type_limit: int = DEFAULT_PER_TYPE_LIMIT,
) -> dict[str, Any]:
    """Search every entity type and group the results.

    Per-entity failures are reported, not propagated: one broken table must
    not turn a support lookup into a 500 when the other four answered. The
    response says which entity errored so a partial answer is visibly partial.
    """
    cleaned = normalise_term(term)
    if len(cleaned) < MIN_TERM_LENGTH:
        return {
            "term": cleaned,
            "groups": {},
            "total": 0,
            "errors": {},
            "note": f"حداقل {MIN_TERM_LENGTH} نویسه لازم است",
        }

    wanted = [e for e in (entities or list(_COLLECTORS)) if e in _COLLECTORS]

    groups: dict[str, list[dict[str, Any]]] = {}
    errors: dict[str, str] = {}

    for entity in wanted:
        try:
            hits = await _COLLECTORS[entity](db, cleaned, per_type_limit)
            groups[entity] = [h.to_dict() for h in hits]
        except Exception as exc:  # noqa: BLE001 — one entity must not break the box
            await logger.awarning(
                "admin_search_entity_failed", entity=entity, error=str(exc)
            )
            errors[entity] = str(exc)[:200]
            groups[entity] = []

    total = sum(len(v) for v in groups.values())

    return {
        "term": cleaned,
        "groups": groups,
        "total": total,
        "errors": errors,
        "searched_at": datetime.now(UTC).isoformat(),
    }
