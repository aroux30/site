"""Reward payout history — the admin's audit view of the money that moved.

Reads the wallet ledger (``wallet_transactions``) because that is the single
source of truth for money that actually left the system; the referral tables
hold *intent* (PENDING rows), the ledger holds *payment*. Each row is joined
to the context that explains it:

* signup gifts  → the referral row → the invited user's name (who joined)
* commissions   → the commission row → the order (which order, what amount)
* recharge bonus→ the top-up payment (how much was recharged)

Names come from ``UserProfile`` (display_name → first+last) — ``User`` itself
has no name columns. Missing profiles degrade to a phone number, never blank.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.modules.referrals.application.referral_service import (
    REF_COMMISSION_L1,
    REF_COMMISSION_L2,
    REF_RECHARGE_BONUS,
    REF_SIGNUP_GIFT_L1,
    REF_SIGNUP_GIFT_L2,
)
from app.modules.referrals.domain.models import Referral, ReferralCommission
from app.modules.users.domain.models import User, UserProfile
from app.modules.wallet.domain.models import Wallet, WalletTransaction

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

#: The five wallet reference types this program writes, mapped to the
#: history kind the admin filters by.
_REF_KIND = {
    REF_SIGNUP_GIFT_L1: "signup_gift",
    REF_SIGNUP_GIFT_L2: "signup_gift",
    REF_COMMISSION_L1: "commission",
    REF_COMMISSION_L2: "commission",
    REF_RECHARGE_BONUS: "recharge_bonus",
}

#: kind → the reference types it covers (for the SQL filter).
_KIND_REFS = {
    "signup_gift": (REF_SIGNUP_GIFT_L1, REF_SIGNUP_GIFT_L2),
    "commission": (REF_COMMISSION_L1, REF_COMMISSION_L2),
    "recharge_bonus": (REF_RECHARGE_BONUS,),
}

_ALL_REFS = tuple(_REF_KIND.keys())


def _display_name(display_name: str | None, first: str | None, last: str | None) -> str | None:
    """Profile display_name → first+last; None when the profile is empty."""
    if display_name and display_name.strip():
        return display_name.strip()
    joined = " ".join(part for part in (first, last) if part and part.strip()).strip()
    return joined or None


async def fetch_reward_history(
    db: AsyncSession,
    *,
    kind: str | None = None,
    q: str | None = None,
    date_from: Any = None,
    date_to: Any = None,
    skip: int = 0,
    limit: int = 25,
) -> tuple[list[dict[str, Any]], int]:
    """Return (page of reward rows, total count), newest first.

    Filters: ``kind`` (reward type), ``q`` (free text over earner name/phone,
    order number, invited user name/phone), ``date_from``/``date_to``
    (inclusive dates over ``created_at``).
    """
    refs = _KIND_REFS.get(kind or "", _ALL_REFS) if kind else _ALL_REFS

    base_where: tuple[Any, ...] = (
        WalletTransaction.reference_type.in_(refs),
        WalletTransaction.reference_id.is_not(None),
    )

    if date_from is not None:
        base_where = (*base_where, WalletTransaction.created_at >= date_from)
    if date_to is not None:
        # Inclusive end date: everything before the NEXT day starts.
        from datetime import timedelta

        base_where = (
            *base_where,
            WalletTransaction.created_at < date_to + timedelta(days=1),
        )

    if q:
        like = f"%{q.strip()}%"
        # Reference ids whose CONTEXT matches: commission rows via their
        # order number, gift rows via the invited user's name/phone.
        from app.modules.orders.domain.models import Order
        from app.modules.users.domain.models import User as _User

        matching_orders = select(ReferralCommission.id).join(
            Order, Order.id == ReferralCommission.order_id
        ).where(Order.order_number.ilike(like))
        invited_match = select(Referral.id).join(
            _User, _User.id == Referral.referred_id
        ).outerjoin(UserProfile, UserProfile.user_id == _User.id).where(
            _User.phone.ilike(like)
            | UserProfile.display_name.ilike(like)
            | UserProfile.first_name.ilike(like)
            | UserProfile.last_name.ilike(like)
        )
        base_where = (
            *base_where,
            User.phone.ilike(like)
            | UserProfile.display_name.ilike(like)
            | UserProfile.first_name.ilike(like)
            | UserProfile.last_name.ilike(like)
            | WalletTransaction.reference_id.in_(matching_orders)
            | WalletTransaction.reference_id.in_(invited_match),
        )

    total = (
        await db.execute(
            select(func.count())
            .select_from(WalletTransaction)
            .join(Wallet, Wallet.id == WalletTransaction.wallet_id)
            .join(User, User.id == Wallet.user_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(*base_where)
        )
    ).scalar_one()

    # ── Main page: ledger rows + earner identity ──────────────────────
    rows = (
        await db.execute(
            select(
                WalletTransaction.id,
                WalletTransaction.reference_type,
                WalletTransaction.reference_id,
                WalletTransaction.amount,
                WalletTransaction.created_at,
                WalletTransaction.description,
                User.id.label("earner_id"),
                User.phone.label("earner_phone"),
                UserProfile.display_name,
                UserProfile.first_name,
                UserProfile.last_name,
            )
            .join(Wallet, Wallet.id == WalletTransaction.wallet_id)
            .join(User, User.id == Wallet.user_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(*base_where)
            .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
            .offset(skip)
            .limit(limit)
        )
    ).all()

    # ── Per-kind context, batched by reference id ─────────────────────
    gift_ids = [r.reference_id for r in rows if r.reference_type in _KIND_REFS["signup_gift"]]
    commission_ids = [r.reference_id for r in rows if r.reference_type in _KIND_REFS["commission"]]

    # Signup gifts: the referral row → who was invited.
    gift_ctx: dict[Any, str | None] = {}
    if gift_ids:
        gift_rows = (
            await db.execute(
                select(Referral.id, Referral.referred_id).where(Referral.id.in_(gift_ids))
            )
        ).all()
        referred_ids = [g.referred_id for g in gift_rows]
        names: dict[Any, str] = {}
        if referred_ids:
            name_rows = (
                await db.execute(
                    select(
                        User.id,
                        User.phone,
                        UserProfile.display_name,
                        UserProfile.first_name,
                        UserProfile.last_name,
                    )
                    .outerjoin(UserProfile, UserProfile.user_id == User.id)
                    .where(User.id.in_(referred_ids))
                )
            ).all()
            for n in name_rows:
                names[n.id] = _display_name(n.display_name, n.first_name, n.last_name) or n.phone
        for g in gift_rows:
            gift_ctx[g.id] = names.get(g.referred_id)

    # Commissions: the commission row → its order.
    commission_ctx: dict[Any, tuple[str | None, int | None]] = {}
    if commission_ids:
        from app.modules.orders.domain.models import Order

        commission_rows = (
            await db.execute(
                select(ReferralCommission.id, ReferralCommission.order_id).where(
                    ReferralCommission.id.in_(commission_ids)
                )
            )
        ).all()
        order_ids = [c.order_id for c in commission_rows]
        orders: dict[Any, tuple[str | None, int | None]] = {}
        if order_ids:
            order_rows = (
                await db.execute(
                    select(Order.id, Order.order_number, Order.total).where(
                        Order.id.in_(order_ids)
                    )
                )
            ).all()
            for o in order_rows:
                orders[o.id] = (o.order_number, o.total)
        for c in commission_rows:
            commission_ctx[c.id] = orders.get(c.order_id, (None, None))

    # Recharge bonuses: the top-up payment's amount.
    bonus_ids = [r.reference_id for r in rows if r.reference_type == REF_RECHARGE_BONUS]
    bonus_ctx: dict[Any, int | None] = {}
    if bonus_ids:
        from app.modules.payments.domain.models import Payment

        payment_rows = (
            await db.execute(
                select(Payment.id, Payment.amount).where(Payment.id.in_(bonus_ids))
            )
        ).all()
        bonus_ctx = {p.id: p.amount for p in payment_rows}

    # ── Assemble ──────────────────────────────────────────────────────
    items: list[dict[str, Any]] = []
    for r in rows:
        row_kind = _REF_KIND[r.reference_type]
        level = 2 if r.reference_type in (REF_SIGNUP_GIFT_L2, REF_COMMISSION_L2) else 1
        item: dict[str, Any] = {
            "id": str(r.id),
            "kind": row_kind,
            "amount": r.amount,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "earner_id": str(r.earner_id),
            "earner_name": _display_name(r.display_name, r.first_name, r.last_name)
            or r.earner_phone,
            "earner_phone": r.earner_phone,
            "level": level,
        }
        if row_kind == "signup_gift":
            item["invited_user_name"] = gift_ctx.get(r.reference_id)
        elif row_kind == "commission":
            order_number, order_total = commission_ctx.get(r.reference_id, (None, None))
            item["order_number"] = order_number
            item["payment_amount"] = order_total
        elif row_kind == "recharge_bonus":
            item["payment_amount"] = bonus_ctx.get(r.reference_id)
        items.append(item)

    return items, total


#: Hard cap for one export request — beyond this the operator should narrow
#: the filters (a 200k-row CSV is a spreadsheet that will not open anyway).
_EXPORT_MAX_ROWS = 50_000


async def build_reward_history_csv(
    db: AsyncSession,
    *,
    kind: str | None = None,
    q: str | None = None,
    date_from: Any = None,
    date_to: Any = None,
) -> bytes:
    """Render the FILTERED reward history as an Excel-safe CSV (UTF-8 BOM).

    Same filters as the tab; no pagination (up to ``_EXPORT_MAX_ROWS``).
    Reuses the reporting module's builder so formula-injection hardening and
    the BOM convention are shared, never re-implemented.
    """
    from app.modules.reporting.application.csv_builder import build_csv_bytes

    rows: list[dict[str, Any]] = []
    batch = 500
    skip = 0
    while len(rows) < _EXPORT_MAX_ROWS:
        page, total = await fetch_reward_history(
            db, kind=kind, q=q, date_from=date_from, date_to=date_to,
            skip=skip, limit=batch,
        )
        rows.extend(page)
        skip += batch
        if skip >= total or not page:
            break

    from app.modules.referrals.application.referral_config import (
        format_toman as _fmt_toman,
    )

    kind_labels = {
        "signup_gift": "هدیهٔ ثبت‌نام",
        "commission": "پورسانت خرید",
        "recharge_bonus": "بونوس شارژ",
    }
    header = ["نوع پاداش", "گیرنده", "شماره تماس", "لایه", "بابت", "مبلغ (تومان)", "تاریخ"]
    body: list[list[Any]] = []
    for item in rows:
        if item["kind"] == "signup_gift":
            reason = (
                f"عضویت {item.get('invited_user_name')} با لینک دعوت"
                if item.get("invited_user_name")
                else "عضویت با لینک دعوت"
            )
        elif item["kind"] == "commission":
            reason = f"سفارش {item.get('order_number') or '—'}"
            if item.get("payment_amount") is not None:
                reason += f" (مبلغ سفارش: {_fmt_toman(item['payment_amount'])} تومان)"
        else:
            reason = "شارژ کیف پول"
            if item.get("payment_amount") is not None:
                reason += f" (مبلغ شارژ: {_fmt_toman(item['payment_amount'])} تومان)"
        body.append(
            [
                kind_labels.get(item["kind"], item["kind"]),
                item["earner_name"],
                item.get("earner_phone") or "",
                item.get("level") if item["kind"] != "recharge_bonus" else "",
                reason,
                _fmt_toman(item["amount"]),
                item.get("created_at") or "",
            ]
        )
    return build_csv_bytes(header, body)
