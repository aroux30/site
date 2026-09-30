"""The sources this system actually holds data in, registered one by one.

Every table holding a subject's personal data appears here, so the GDPR queue
reports coverage per source instead of returning one opaque blob. Two shapes
exist and both are needed:

* **Direct** — the table carries its own ``user_id``. One predicate finds and
  erases it.
* **Indirect** — an order's payments, a wallet's transactions, a wishlist's
  items. These have *no* ``user_id`` at all and must be reached through a parent.
  A registry that only understood the first shape would tell a subject their
  entire purchase history was "not found", which is a legally serious kind of
  wrong rather than a cosmetic gap.

Financial and audit sources are registered as erasers that **retain** and state
why. A retention duty must never be reported to the subject as "erased".
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select, update

from app.modules.settings.application.privacy_sources import registry

#: Sources whose rows survive erasure, and why — written for the subject, since
#: it is rendered in their export and erasure report.
RETENTION_NOTES: dict[str, str] = {
    "orders": "سفارش‌ها و اقلام آن‌ها به دلیل الزام قانونی نگهداری سوابق مالی حذف نمی‌شوند.",
    "payments": "تراکنش‌های مالی طبق الزام قانونی نگهداری سوابق مالی حفظ می‌شوند.",
    "invoices": "فاکتورها طبق الزام قانونی نگهداری سوابق مالی حفظ می‌شوند.",
    "wallet_transactions": "گردش کیف پول به دلیل الزام قانونی حفظ می‌شود.",
    "loyalty_transactions": "سوابق وفاداری برای محاسبه نهایی حفظ می‌شود.",
    "audit_logs": "گزارش‌های ممیزی به دلیل الزام قانونی حفظ می‌شوند؛ تنها نشانی IP و "
    "مرورگر که بخش شخصی آن است پاک می‌شود.",
}


def _serialise(row: Any) -> dict[str, Any]:
    """Turn an ORM row into a JSON-safe dict.

    Deliberately generic rather than a hand-written projection per table: a
    per-table projection is a list of 45 places to forget a column, and the
    subject is entitled to the data we hold, not the subset someone remembered
    to map. Relationships are skipped — they belong to their own source — and
    anything that is not a scalar is stringified rather than dropped, so a new
    column is included by default instead of being invisible.
    """
    out: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name, None)
        out[column.name] = value if isinstance(value, (str, int, float, bool, type(None))) else str(value)
    return out


async def _rows_direct(db: Any, model: Any, user_id: uuid.UUID) -> list[dict[str, Any]]:
    result = await db.execute(select(model).where(model.user_id == user_id))
    return [_serialise(row) for row in result.scalars().all()]


async def _count_direct(db: Any, model: Any, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(model).where(model.user_id == user_id)
    )
    return int(result.scalar() or 0)


def _parent_model(model: Any, through: str) -> Any:
    """The parent model reached by a hop named *through*.

    ``through`` may name a relationship (``"order"``) or a bare foreign-key
    column (``"order_id"``). Payment and Invoice only carry ``order_id`` -- they
    declare no relationship at all, so ``getattr(model, "order")`` raised
    AttributeError for those two sources while every other indirect source
    worked. The target table therefore comes from the column's ForeignKey, not
    from the relationship graph, which is empty in exactly this case.
    """
    if through in model.__mapper__.relationships:
        return getattr(model, through).property.mapper.class_
    # A hop named for the relationship ("order") may still only exist as the
    # foreign-key column ("order_id") -- Payment and Invoice declare no
    # relationship at all, so the column name is derived from the hop name.
    column = model.__table__.columns[_fk_column_name(model, through)]
    fk = next(iter(column.foreign_keys))

    # A mapped relationship would have been caught above. Payment and Invoice
    # declare none towards Order, so the parent is found by asking the registry
    # which mapped class owns the table this foreign key points at.
    from app.core.database.base import Base

    target_table = fk.column.table
    for mapper in Base.registry.mappers:
        if mapper.local_table is target_table:
            return mapper.class_
    raise AttributeError(
        f"{model.__name__}.{column.name} points at {target_table.name!r}, "
        f"which no mapped class owns"
    )


def _fk_column_name(model: Any, through: str) -> str:
    """The column on *model* holding the foreign key for a hop named *through*.

    Sources name the hop after the relationship ("order") for readability, so
    the column is derived: the name itself if it is a column, otherwise the
    conventional ``<hop>_id``.
    """
    if through in model.__table__.columns:
        return through
    derived = f"{through}_id"
    if derived in model.__table__.columns:
        return derived
    raise AttributeError(
        f"{model.__name__} has no column for hop {through!r} (tried {through!r} "
        f"and {derived!r})"
    )


async def _rows_via(
    db: Any, model: Any, user_id: uuid.UUID, through: str
) -> list[dict[str, Any]]:
    """Rows of *model* reached through the named parent relationship."""
    if through in model.__mapper__.relationships:
        attr = getattr(model, through)
        parent = attr.property.mapper.class_
        result = await db.execute(
            select(model).join(attr).where(parent.user_id == user_id)
        )
    else:
        parent = _parent_model(model, through)
        fk = getattr(model, _fk_column_name(model, through))
        result = await db.execute(
            select(model).join(parent, fk == parent.id).where(parent.user_id == user_id)
        )
    return [_serialise(row) for row in result.scalars().all()]


async def _count_via(db: Any, model: Any, user_id: uuid.UUID, through: str) -> int:
    """Count rows of *model* reached through the named relationship.

    The hop is named per source rather than discovered from the relationship
    graph, so what the registry counts is written down and reviewable instead of
    depending on which relationships happen to be loaded.
    """
    if through in model.__mapper__.relationships:
        attr = getattr(model, through)
        parent = attr.property.mapper.class_
        result = await db.execute(
            select(func.count())
            .select_from(model)
            .join(attr)
            .where(parent.user_id == user_id)
        )
    else:
        parent = _parent_model(model, through)
        fk = getattr(model, _fk_column_name(model, through))
        result = await db.execute(
            select(func.count())
            .select_from(model)
            .join(parent, fk == parent.id)
            .where(parent.user_id == user_id)
        )
    return int(result.scalar() or 0)


def _register(
    name: str,
    *,
    label: str,
    rows,
    erase,
) -> None:
    """Register one source: an exporter that returns its rows, and an eraser.

    The exporter returns ``(len(rows), rows)`` so the report gets a count while
    the archive gets the data. Having the same call serve both is what keeps
    them from disagreeing — a count taken from one query and rows from another
    would drift the moment a row was written between them.
    """

    async def _export(db: Any, user_id: uuid.UUID, _r=rows) -> tuple[int, Any]:
        data = await _r(db, user_id)
        return len(data), data

    registry.register(
        name,
        exporter=_export,
        eraser=lambda db, uid, _e=erase: _e(db, uid),
        label=label,
    )


def _erase_direct(model: Any, *, reason: str | None = None):
    """Eraser for a direct source, deleting rows or retaining them with a reason."""

    async def _erase(db: Any, user_id: uuid.UUID) -> tuple[int, int, str | None]:
        count = await _count_direct(db, model, user_id)
        if count == 0:
            return 0, 0, None
        await db.execute(delete(model).where(model.user_id == user_id))
        return count, 0, reason

    return _erase


def _erase_via(model: Any, through: str, *, reason: str):
    """Eraser for an indirect source.

    Retained whole. The columns a financial retention duty protects (amounts,
    providers, reference ids) are exactly the ones that would have to be
    blanked, and blanking them would satisfy the letter of the law while
    destroying the record it exists to preserve.
    """

    async def _erase(db: Any, user_id: uuid.UUID) -> tuple[int, int, str | None]:
        count = await _count_via(db, model, user_id, through)
        if count == 0:
            return 0, 0, None
        return 0, count, reason

    return _erase


def _erase_via_hard(model: Any, through: str):
    """Eraser for an indirect source with no retention duty.

    The subquery is built explicitly so the delete cannot reach rows belonging to
    someone else's parent.
    """

    async def _erase(db: Any, user_id: uuid.UUID) -> tuple[int, int, str | None]:
        count = await _count_via(db, model, user_id, through)
        if count == 0:
            return 0, 0, None
        parent = _parent_model(model, through)
        subq = select(parent.id).where(parent.user_id == user_id)
        if through in model.__mapper__.relationships:
            # A relationship attribute cannot be compared to a scalar subquery,
            # so the condition is written against the child foreign key.
            fk_col = next(iter(getattr(model, through).local_columns))
            await db.execute(delete(model).where(fk_col.in_(subq)))
        else:
            await db.execute(
                delete(model).where(getattr(model, _fk_column_name(model, through)).in_(subq))
            )
        return count, 0, None

    return _erase


def register_core_sources() -> int:
    """Register every table that holds subject data. Returns the count.

    Imported lazily inside the function so importing this module never pulls in
    every domain model, which would create import cycles during app start-up.
    """
    from app.modules.audit.domain.models import AuditLog
    from app.modules.cart.domain.models import Cart
    from app.modules.invoicing.domain.models import Invoice
    from app.modules.loyalty.domain.models import LoyaltyTransaction
    from app.modules.notifications.domain.models import Notification
    from app.modules.orders.domain.models import Order, OrderItem
    from app.modules.payments.domain.models import Payment
    from app.modules.reviews.domain.models import Review
    from app.modules.users.domain.models import Address, ApplicationPassword, UserProfile
    from app.modules.wallet.domain.models import WalletTransaction
    from app.modules.wishlist.domain.models import WishlistItem

    before = len(registry.names())

    # ── identity and profile: erased outright, no retention duty ─────────────
    _register(
        "profile", label="اطلاعات پروفایل",
        rows=lambda db, uid, _m=UserProfile: _rows_direct(db, _m, uid),
        erase=_erase_direct(UserProfile),
    )
    _register(
        "addresses", label="نشانی‌ها",
        rows=lambda db, uid, _m=Address: _rows_direct(db, _m, uid),
        erase=_erase_direct(Address),
    )
    _register(
        "application_passwords", label="کلیدهای اپلیکیشن",
        rows=lambda db, uid, _m=ApplicationPassword: _rows_direct(db, _m, uid),
        erase=_erase_direct(ApplicationPassword),
    )
    _register(
        "notifications", label="اعلان‌ها",
        rows=lambda db, uid, _m=Notification: _rows_direct(db, _m, uid),
        erase=_erase_direct(Notification),
    )
    _register(
        "reviews", label="دیدگاه‌ها و امتیازها",
        rows=lambda db, uid, _m=Review: _rows_direct(db, _m, uid),
        erase=_erase_direct(Review),
    )
    _register(
        "carts", label="سبدهای خرید",
        rows=lambda db, uid, _m=Cart: _rows_direct(db, _m, uid),
        erase=_erase_direct(Cart),
    )

    # ── orders: retained under a financial retention duty ───────────────────
    _register(
        "orders", label="سفارش‌ها",
        rows=lambda db, uid, _m=Order: _rows_direct(db, _m, uid),
        erase=_erase_direct(Order, reason=RETENTION_NOTES["orders"]),
    )
    _register(
        "order_items", label="اقلام سفارش",
        rows=lambda db, uid, _m=OrderItem: _rows_via(db, _m, uid, "order"),
        erase=_erase_via(OrderItem, "order", reason=RETENTION_NOTES["orders"]),
    )
    _register(
        "payments", label="پرداخت‌ها",
        rows=lambda db, uid, _m=Payment: _rows_via(db, _m, uid, "order"),
        erase=_erase_via(Payment, "order", reason=RETENTION_NOTES["payments"]),
    )
    _register(
        "invoices", label="فاکتورها",
        rows=lambda db, uid, _m=Invoice: _rows_via(db, _m, uid, "order"),
        erase=_erase_via(Invoice, "order", reason=RETENTION_NOTES["invoices"]),
    )
    _register(
        "wallet_transactions", label="تراکنش‌های کیف پول",
        rows=lambda db, uid, _m=WalletTransaction: _rows_via(db, _m, uid, "wallet"),
        erase=_erase_via(
            WalletTransaction, "wallet", reason=RETENTION_NOTES["wallet_transactions"]
        ),
    )
    _register(
        "loyalty_transactions", label="سوابق وفاداری",
        rows=lambda db, uid, _m=LoyaltyTransaction: _rows_via(db, _m, uid, "account"),
        erase=_erase_via(
            LoyaltyTransaction, "account", reason=RETENTION_NOTES["loyalty_transactions"]
        ),
    )

    # ── wishlist: no retention duty, and the user can rebuild it ─────────────
    _register(
        "wishlist_items", label="علاقه‌مندی‌ها",
        rows=lambda db, uid, _m=WishlistItem: _rows_via(db, _m, uid, "wishlist"),
        erase=_erase_via_hard(WishlistItem, "wishlist"),
    )

    # ── audit: the row is the record, so only the personal parts are cleared ─
    async def _rows_audit(db: Any, user_id: uuid.UUID) -> list[dict[str, Any]]:
        result = await db.execute(
            select(AuditLog).where(AuditLog.actor_id == user_id)
        )
        return [_serialise(row) for row in result.scalars().all()]

    async def _count_audit(db: Any, user_id: uuid.UUID) -> int:
        return len(await _rows_audit(db, user_id))

    async def _erase_audit(db: Any, user_id: uuid.UUID) -> tuple[int, int, str | None]:
        count = await _count_audit(db, user_id)
        if count == 0:
            return 0, 0, None
        await db.execute(
            update(AuditLog)
            .where(AuditLog.actor_id == user_id)
            .values(ip_address=None, user_agent=None)
        )
        return 0, count, RETENTION_NOTES["audit_logs"]

    _register(
        "audit_logs", label="گزارش‌های ممیزی",
        rows=_rows_audit,
        erase=_erase_audit,
    )

    # ── everything else the schema says it tracks ────────────────────────────
    # The list below came from querying ``Base.metadata`` for every table with a
    # ``user_id`` column, not from remembering what seemed important. A table
    # missed here is a table a data-subject export silently omits while telling
    # the subject it included everything, so the coverage test in
    # tests/test_privacy_source_registry.py fails when a new one appears.
    financial = "به دلیل الزام قانونی نگهداری سوابق مالی حفظ می‌شود."

    for name, model, label in _remaining_direct_models():
        if name in RETAINED_TABLES:
            _register(
                name, label=label,
                rows=lambda db, uid, _m=model: _rows_direct(db, _m, uid),
                erase=_erase_direct(model, reason=financial),
            )
        else:
            _register(
                name, label=label,
                rows=lambda db, uid, _m=model: _rows_direct(db, _m, uid),
                erase=_erase_direct(model),
            )

    return len(registry.names()) - before


#: Tables whose rows must survive an erasure request. Everything else is deleted
#: outright: it is either rebuildable by the user (a cart, a wishlist) or holds
#: nothing the law requires keeping (a session, a notification preference).
RETAINED_TABLES: frozenset[str] = frozenset(
    {
        "card_transfer_receipts",
        "cashback_transactions",
        "coupon_redemptions",
        "direct_invoices",
        "gift_try_logs",
        "installment_plans",
        "loyalty_accounts",
        "order_returns",
        "subscriptions",
        "user_bank_cards",
        "vendors",
        "wallets",
    }
)


def _remaining_direct_models() -> list[tuple[str, Any, str]]:
    """Every remaining user-owned table, resolved lazily.

    Imported here rather than at module level because each of these modules
    imports back into the settings package; importing them eagerly would create
    a cycle during app start-up.
    """
    from app.modules.analytics.domain.models import AnalyticsEvent
    from app.modules.blog.domain.wp_parity_models import UserMeta
    from app.modules.loyalty.domain.models import LoyaltyAccount
    from app.modules.cashback.domain.models import CashbackTransaction
    from app.modules.discounts.domain.models import CouponRedemption
    from app.modules.gamification.domain.gift_models import GiftTryLog
    from app.modules.gamification.domain.models import GamificationEvent
    from app.modules.messaging.domain.models import BroadcastRecipient
    from app.modules.notifications.domain.models import (
        NotificationPreference,
        PushSubscription,
    )
    from app.modules.notifications.domain.notice_models import SeenNotice
    from app.modules.orders.domain.reseller_models import ResellerApiKey
    from app.modules.orders.domain.return_models import OrderReturn
    from app.modules.payments.domain.fintech_models import (
        CardTransferReceipt,
        DirectInvoice,
    )
    from app.modules.payments.domain.installment_models import InstallmentPlan
    from app.modules.payments.domain.saved_method_models import SavedPaymentMethod
    from app.modules.rbac.domain.models import UserPermissionOverride
    from app.modules.referrals.domain.models import ReferralCode
    from app.modules.reviews.domain.models import ReviewVote
    from app.modules.settings.domain.models import PrivacyRequest
    from app.modules.subscriptions.domain.models import Subscription
    from app.modules.support.domain.models import SupportTicket
    from app.modules.users.domain.kyc_models import UserBankCard, UserTrustProfile
    from app.modules.users.domain.models import (
        EmailChangeRequest,
        PasswordResetToken,
        UserSession,
    )
    from app.modules.vendors.domain.models import Vendor
    from app.modules.wallet.domain.models import Wallet
    from app.modules.wishlist.domain.models import Wishlist

    return [
        ("analytics_events", AnalyticsEvent, "رویدادهای تحلیلی"),
        ("broadcast_recipients", BroadcastRecipient, "گیرندگان پیامک انبوه"),
        ("card_transfer_receipts", CardTransferReceipt, "رسیدهای کارت به کارت"),
        ("cashback_transactions", CashbackTransaction, "تراکنش‌های کش‌بک"),
        ("coupon_redemptions", CouponRedemption, "استفاده از کدهای تخفیف"),
        ("direct_invoices", DirectInvoice, "فاکتورهای مستقیم"),
        ("email_change_requests", EmailChangeRequest, "درخواست‌های تغییر ایمیل"),
        ("gamification_events", GamificationEvent, "رویدادهای بازی‌سازی"),
        ("gift_try_logs", GiftTryLog, "سابقهٔ تلاش برای هدیه"),
        ("installment_plans", InstallmentPlan, "اقساط"),
        ("loyalty_accounts", LoyaltyAccount, "حساب‌های وفاداری"),
        ("order_returns", OrderReturn, "درخواست‌های بازگشت کالا"),
        ("notification_preferences", NotificationPreference, "ترجیحات اعلان"),
        ("password_reset_tokens", PasswordResetToken, "توکن‌های بازیابی رمز"),
        ("privacy_requests", PrivacyRequest, "درخواست‌های حریم خصوصی"),
        ("push_subscriptions", PushSubscription, "اشتراک‌های پوش"),
        ("referral_codes", ReferralCode, "کدهای معرفی"),
        ("reseller_api_keys", ResellerApiKey, "کلیدهای API همکاران فروش"),
        ("review_votes", ReviewVote, "رأی‌های دیدگاه"),
        ("saved_payment_methods", SavedPaymentMethod, "روش‌های پرداخت ذخیره‌شده"),
        ("seen_notices", SeenNotice, "اطلاعیه‌های دیده‌شده"),
        ("subscriptions", Subscription, "اشتراک‌ها"),
        ("support_tickets", SupportTicket, "تیکت‌های پشتیبانی"),
        ("user_bank_cards", UserBankCard, "کارت‌های بانکی"),
        ("user_meta", UserMeta, "متادیتای کاربر"),
        ("user_permission_overrides", UserPermissionOverride, "مجوزهای اختصاصی"),
        ("user_sessions", UserSession, "نشست‌های فعال"),
        ("user_trust_profiles", UserTrustProfile, "پروفایل اعتماد"),
        ("vendors", Vendor, "فروشندگان"),
        ("wallets", Wallet, "کیف‌های پول"),
        ("wishlists", Wishlist, "فهرست‌های علاقه‌مندی"),
    ]


_REGISTERED = False


def ensure_registered() -> None:
    """Register the core sources once, tolerating a repeated import.

    Idempotent because the application is imported more than once in a test
    session; re-registering would list every source twice in the report.
    """
    global _REGISTERED
    if _REGISTERED:
        return
    register_core_sources()
    _REGISTERED = True
