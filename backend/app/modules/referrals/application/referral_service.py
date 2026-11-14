"""Referral application service – code generation, tracking, gifts, and commissions.

Ported from the VPN project's referral/bonus system (the owner's reference
implementation) onto this codebase's wallet + settings + sweep patterns,
with the 2026-10-13 arena hardening applied:

* **at-most-once money** — every payout carries a ``reference_type`` that the
  partial unique index ``uq_wallet_referral_rewards_once`` covers, and the
  credit is attempted inside a savepoint: a duplicate attempt rolls back only
  the savepoint and is recognised as "already paid". The claim and the money
  movement are the *same write*, so a recoverable failure never burns the
  claim (the arena champion's release() lesson, expressed structurally).
* **at-least-once retry** — anything unpaid stays PENDING and the periodic
  sweep (:mod:`app.modules.referrals.application.tasks`) retries it. No
  payout can be lost to a transient failure.
* **per-order uniqueness** — ``uq_referral_commissions_order_earner`` keeps
  one commission per order per earner even under concurrent sweeps.
* **integer math** — amounts are Rial (ADR-012); percents are clamped 0..100
  in :mod:`referral_config`.

Level 2 is derived by walking the chain at payout time (the referrer's own
referrer); there is no level-2 ``referrals`` row — ``referrals.referred_id``
is UNIQUE, and inserting a second row sharing it was a latent constraint
violation in the previous implementation.
"""

from __future__ import annotations

import secrets
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.modules.referrals.application import referral_config
from app.modules.referrals.domain.models import (
    CommissionStatus,
    Referral,
    ReferralCode,
    ReferralCommission,
    ReferralStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()

MAX_REFERRAL_LEVEL = 2

#: Wallet ``reference_type`` values this module writes. The partial unique
#: index ``uq_wallet_referral_rewards_once`` (migration refbon1) covers exactly
#: these — the money-level at-most-once backstop.
REF_SIGNUP_GIFT_L1 = "referral_signup_gift_l1"
REF_SIGNUP_GIFT_L2 = "referral_signup_gift_l2"
REF_COMMISSION_L1 = "referral_commission_l1"
REF_COMMISSION_L2 = "referral_commission_l2"
REF_RECHARGE_BONUS = "recharge_bonus"

_COMMISSION_REF = {1: REF_COMMISSION_L1, 2: REF_COMMISSION_L2}


def _generate_referral_code(length: int = 8) -> str:
    """Generate a URL-safe unique referral code."""
    return secrets.token_urlsafe(length)[:length].upper()


def _before_program_start(created_at: Any, cfg: dict[str, Any]) -> bool:
    """Whether *created_at* predates the program's first configuration.

    Compares real datetimes (never ISO strings — offsets can differ). A naive
    timestamp from the DB is treated as UTC, which is how Postgres stores it.
    """
    from datetime import UTC, datetime

    started_at = referral_config._started_at(cfg)
    if started_at is None:
        return True
    try:
        start = datetime.fromisoformat(started_at)
    except ValueError:
        return True
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    created = created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return created < start


async def _credit_reward(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount: int,
    reference_type: str,
    reference_id: uuid.UUID,
    description: str,
) -> bool:
    """Credit a reward exactly once per ``(reference_type, reference_id)``.

    Returns True when this call performed the credit, False when it was
    already paid (the partial unique index rejected the duplicate inside a
    savepoint, leaving outer state untouched). Any *other* failure propagates
    so the caller's transaction rolls back — the reward stays unpaid and the
    sweep retries it.
    """
    if amount <= 0:
        return False
    from app.modules.wallet.application import wallet_service
    from app.modules.wallet.domain.models import WalletTransactionType

    try:
        async with db.begin_nested():
            await wallet_service.credit(
                db,
                user_id=user_id,
                amount=amount,
                tx_type=WalletTransactionType.BONUS,
                reference_type=reference_type,
                reference_id=reference_id,
                description=description,
            )
    except IntegrityError:
        # uq_wallet_referral_rewards_once — already paid. Not an error.
        return False
    return True


async def _notify_reward(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    notif_type: str,
    title: str,
    template: str,
    amount_rial: int,
    idempotency_key: str,
) -> None:
    """Best-effort in-app notification for a paid reward."""
    try:
        from app.modules.notifications.application.notification_service import (
            NotificationService,
        )

        notification = await NotificationService.create_notification(
            db,
            user_id=user_id,
            type=notif_type,
            title=title,
            body=referral_config.render_template(template, amount_rial=amount_rial),
            data={"amount": amount_rial},
            idempotency_key=idempotency_key,
        )
        try:
            from app.modules.notifications.application.tasks import send_notification_task

            send_notification_task.delay(str(notification.id))
        except Exception as exc:  # dispatch is fire-and-forget
            await logger.awarning("referral_notify_dispatch_skipped", error=str(exc))
    except Exception as exc:
        await logger.awarning("referral_notify_skipped", error=str(exc))


class ReferralService:
    """Handles referral code generation, tracking, and reward payouts."""

    # ── Referral Code ─────────────────────────────────────────────────

    @staticmethod
    async def get_or_create_referral_code(db: AsyncSession, user_id: uuid.UUID) -> str:
        """Return the user's referral code, creating and persisting it once.

        The code must be stable across requests — a referral link handed to a
        user has to keep working, so a freshly generated value is written to
        ``referral_codes`` (unique per user) rather than merely returned.
        """
        existing_code: str | None = (
            await db.execute(
                select(ReferralCode.code).where(ReferralCode.user_id == user_id).limit(1)
            )
        ).scalar_one_or_none()
        if existing_code:
            return existing_code

        # Generate a code that collides with no other code (in either table).
        code = ""
        for _ in range(10):
            candidate = _generate_referral_code()
            taken = await db.execute(
                select(ReferralCode.id).where(ReferralCode.code == candidate).limit(1)
            )
            if taken.scalar_one_or_none() is None:
                code = candidate
                break
        else:
            code = _generate_referral_code(12)

        db.add(ReferralCode(user_id=user_id, code=code))
        try:
            await db.flush()
        except IntegrityError:
            # A concurrent request created this user's code first; use theirs.
            await db.rollback()
            existing = (
                await db.execute(
                    select(ReferralCode.code).where(ReferralCode.user_id == user_id).limit(1)
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return existing

        await db.commit()
        await logger.ainfo("referral_code_created", user_id=str(user_id), code=code)
        return code

    @staticmethod
    async def resolve_referrer_by_code(
        db: AsyncSession, code: str
    ) -> uuid.UUID | None:
        """Return the user id owning *code*, or None when unknown/inactive."""
        if not code:
            return None
        owner_id: uuid.UUID | None = (
            await db.execute(
                select(ReferralCode.user_id)
                .where(
                    ReferralCode.code == code.upper().strip(),
                    ReferralCode.is_active.is_(True),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return owner_id

    # ── Track Referral ────────────────────────────────────────────────

    @staticmethod
    async def track_referral(
        db: AsyncSession,
        referrer_id: uuid.UUID,
        referred_id: uuid.UUID,
        code: str,
    ) -> Referral:
        """Record a level-1 referral.

        Only the level-1 row is written: ``referrals.referred_id`` is UNIQUE,
        so a level-2 row sharing the same ``referred_id`` cannot exist. The
        level-2 relationship is derived by walking the chain (the referrer's
        own referrer) wherever it is needed.
        """
        if referrer_id == referred_id:
            raise ValueError("A user cannot refer themselves.")

        # Check if referred user already has a referral
        existing = await db.execute(
            select(Referral).where(Referral.referred_id == referred_id).limit(1)
        )
        if existing.scalar_one_or_none():
            await logger.awarning("referral_already_exists", referred_id=str(referred_id))
            raise ValueError("User already has a referral record.")

        # Cycle guard: the reverse edge must not exist. A↔B is not exploitable
        # (each side earns only the other's L1 gift, and the buyer-as-L2-earner
        # guard stops self-commission on own orders — verified by red-team
        # 2026-10-14), but it pollutes the chain walk: A's L2 lookup would
        # resolve B and vice-versa, making every downstream report read as if
        # the pair were their own upline. Cheap to refuse at the door.
        reverse_edge = await db.execute(
            select(Referral.id)
            .where(
                Referral.referrer_id == referred_id,
                Referral.referred_id == referrer_id,
            )
            .limit(1)
        )
        if reverse_edge.scalar_one_or_none() is not None:
            await logger.awarning(
                "referral_cycle_refused",
                referrer_id=str(referrer_id),
                referred_id=str(referred_id),
            )
            raise ValueError("This referral would create a cycle.")

        level1 = Referral(
            referrer_id=referrer_id,
            referred_id=referred_id,
            code=code,
            level=1,
            status=ReferralStatus.PENDING,
        )
        db.add(level1)
        await db.flush()

        await logger.ainfo(
            "referral_tracked",
            referral_id=str(level1.id),
            referrer_id=str(referrer_id),
            referred_id=str(referred_id),
            level=1,
        )
        return level1

    @staticmethod
    async def _resolve_level2_earner(
        db: AsyncSession, level1_referrer_id: uuid.UUID
    ) -> uuid.UUID | None:
        """The referrer's own referrer, or None when the chain ends here."""
        row = (
            await db.execute(
                select(Referral.referrer_id)
                .where(Referral.referred_id == level1_referrer_id)
                .limit(1)
            )
        ).scalar_one_or_none()
        return row

    @staticmethod
    async def _earner_is_eligible(db: AsyncSession, earner_id: uuid.UUID) -> bool:
        """A deactivated account must not earn new rewards."""
        from app.modules.users.domain.models import User

        user = await db.get(User, earner_id)
        return bool(user and user.is_active)

    @staticmethod
    async def _invited_is_verified(db: AsyncSession, referred_id: uuid.UUID) -> bool:
        """Whether the INVITED user has proven their phone (anti-farming gate).

        The password-registration path creates ``is_verified=False`` rows, so
        without this check an attacker farms gifts with fake phone numbers.
        """
        from app.modules.users.domain.models import User

        user = await db.get(User, referred_id)
        return bool(user and user.is_verified)

    # ── Signup gifts (paid to the referrer(s), not the new user) ──────

    @staticmethod
    async def pay_signup_gift_for_referral(
        db: AsyncSession, referral: Referral
    ) -> dict[str, int]:
        """Pay the fixed signup gift(s) for one referral row.

        L1 goes to the referrer; L2 (when the chain has a grandparent) goes to
        the referrer's own referrer. Each leg is at-most-once via the wallet
        partial unique index; the referral is marked COMPLETED once every
        configured leg is settled. Safe to call repeatedly (the sweep does).

        **Anti-farming gate:** the INVITED user must have a VERIFIED phone
        before any money moves. Without this, an attacker registers unlimited
        fake phone numbers (the password path creates is_verified=False rows)
        and each registration pays the referrer a gift — free money for a
        fake invite. The site's own welcome gift (Karta signup_gift) has the
        same gate; this one must match it. The referral row stays PENDING and
        the sweep retries, so a legitimate invite that verifies later still
        pays.
        """
        cfg = await referral_config.get_config(db)
        paid: dict[str, int] = {}

        if not cfg.get("enabled", True):
            return paid
        # Per-module switch: the signup-gift module can be off while
        # commissions stay on (and vice versa).
        if not referral_config.module_enabled(cfg, "gift"):
            return paid

        # Cut-off: referrals that predate the program's first configuration
        # never pay (no retroactive payouts on historical rows).
        if referral_config._started_at(cfg) is None:
            return paid
        if _before_program_start(referral.created_at, cfg):
            # Settle the row so it stops being swept.
            referral.status = ReferralStatus.COMPLETED
            return paid

        # Anti-farming: do NOT pay until the invited account proved its
        # phone. The row stays PENDING — the sweep pays it the moment the
        # invited user verifies (see the OTP-verify hook in auth_service).
        if not await ReferralService._invited_is_verified(db, referral.referred_id):
            logger.ainfo(
                "referral_gift_held_unverified",
                referral_id=str(referral.id),
                referred_id=str(referral.referred_id),
            )
            return paid

        # ── Level 1 ──
        gift_l1 = int(cfg.get("signup_gift_l1", 0))
        l1_settled = gift_l1 <= 0  # no gift configured → nothing to pay
        if gift_l1 > 0 and await ReferralService._earner_is_eligible(
            db, referral.referrer_id
        ):
            credited = await _credit_reward(
                db,
                user_id=referral.referrer_id,
                amount=gift_l1,
                reference_type=REF_SIGNUP_GIFT_L1,
                reference_id=referral.id,
                description="پاداش ثبت‌نام زیرمجموعه (دعوت دوستان)",
            )
            l1_settled = True  # credited now, or already paid before
            if credited:
                paid["l1"] = gift_l1
                if cfg.get("notify_on_gift", True):
                    await _notify_reward(
                        db,
                        user_id=referral.referrer_id,
                        notif_type="wallet_referral_gift",
                        title="پاداش دعوت دوستان",
                        template=str(cfg.get("gift_notif_text", "")),
                        amount_rial=gift_l1,
                        idempotency_key=f"referral-gift:{referral.id}:l1",
                    )
        elif gift_l1 > 0:
            # Earner ineligible — settle the leg so the row stops being swept.
            l1_settled = True

        # ── Level 2 ──
        gift_l2 = int(cfg.get("signup_gift_l2", 0))
        l2_settled = True
        if gift_l2 > 0:
            earner_l2 = await ReferralService._resolve_level2_earner(
                db, referral.referrer_id
            )
            if earner_l2 is None or not await ReferralService._earner_is_eligible(
                db, earner_l2
            ):
                l2_settled = True  # no chain / ineligible — nothing will ever pay
            else:
                credited = await _credit_reward(
                    db,
                    user_id=earner_l2,
                    amount=gift_l2,
                    reference_type=REF_SIGNUP_GIFT_L2,
                    reference_id=referral.id,
                    description="پاداش ثبت‌نام زیرمجموعه لایه دوم (دعوت دوستان)",
                )
                l2_settled = True
                if credited:
                    paid["l2"] = gift_l2
                    if cfg.get("notify_on_gift", True):
                        await _notify_reward(
                            db,
                            user_id=earner_l2,
                            notif_type="wallet_referral_gift",
                            title="پاداش دعوت دوستان (لایه دوم)",
                            template=str(cfg.get("gift_notif_text", "")),
                            amount_rial=gift_l2,
                            idempotency_key=f"referral-gift:{referral.id}:l2",
                        )

        if l1_settled and l2_settled and referral.status != ReferralStatus.COMPLETED:
            referral.status = ReferralStatus.COMPLETED
        return paid

    @staticmethod
    async def pay_pending_signup_gifts(
        db: AsyncSession, *, limit: int = 100
    ) -> dict[str, Any]:
        """Sweep PENDING referrals and settle their signup gift legs."""
        rows = (
            (
                await db.execute(
                    select(Referral)
                    .where(Referral.status == ReferralStatus.PENDING)
                    .order_by(Referral.created_at.asc())
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        paid_count = 0
        total = 0
        for referral in rows:
            paid = await ReferralService.pay_signup_gift_for_referral(db, referral)
            if paid:
                paid_count += 1
                total += sum(paid.values())
        return {"referrals_settled": len(rows), "paid_count": paid_count, "total_paid": total}

    # ── Order commissions ─────────────────────────────────────────────

    @staticmethod
    async def process_order_commissions(
        db: AsyncSession, order_id: uuid.UUID
    ) -> list[ReferralCommission]:
        """Create PENDING commission rows for a completed order's buyer.

        One row per eligible earner (L1 referrer, L2 chain referrer). Amounts
        are integer math; percents are clamped by the config layer; the
        per-event cap and minimum order total are honoured. Idempotent by
        ``uq_referral_commissions_order_earner`` (concurrent sweeps cannot
        double-create).
        """
        from app.modules.orders.domain.models import Order, OrderStatus

        cfg = await referral_config.get_config(db)
        if not cfg.get("enabled", True):
            return []
        # Per-module switch: commissions can be off while gifts stay on.
        if not referral_config.module_enabled(cfg, "commission"):
            return []

        order = await db.get(Order, order_id)
        if order is None or order.status != OrderStatus.COMPLETED:
            return []

        # Cut-off: orders placed before the program's first configuration
        # never earn commissions (no retroactive payouts on history).
        if _before_program_start(order.created_at, cfg):
            return []

        min_total = int(cfg.get("min_order_total", 0))
        if min_total > 0 and order.total < min_total:
            return []

        cap = int(cfg.get("commission_max_per_event", 0))

        # Buyer must be a referred user.
        level1 = (
            await db.execute(
                select(Referral).where(Referral.referred_id == order.user_id).limit(1)
            )
        ).scalar_one_or_none()
        if level1 is None:
            return []

        earner_l1 = level1.referrer_id
        earner_l2 = await ReferralService._resolve_level2_earner(db, earner_l1)

        candidates: list[tuple[int, uuid.UUID, Referral]] = [(1, earner_l1, level1)]
        if earner_l2 is not None and earner_l2 not in (order.user_id, earner_l1):
            # level-2 rows reuse the level-1 referral row (the chain link).
            candidates.append((2, earner_l2, level1))

        created: list[ReferralCommission] = []
        for level, earner_id, referral in candidates:
            if earner_id == order.user_id:
                continue  # never pay the buyer themselves
            if not await ReferralService._earner_is_eligible(db, earner_id):
                continue
            percent_bp = referral_config.percent_to_bp(
                cfg.get(f"commission_percent_l{level}", 0)
            )
            if percent_bp <= 0:
                continue
            # Integer money math: Rial × bp / 10,000 (1% = 100 bp).
            amount = (order.total * percent_bp) // 10_000
            if cap > 0 and amount > cap:
                amount = cap
            if amount <= 0:
                continue

            try:
                async with db.begin_nested():
                    commission = ReferralCommission(
                        referral_id=referral.id,
                        earner_id=earner_id,
                        order_id=order.id,
                        amount=amount,
                        level=level,
                        status=CommissionStatus.PENDING,
                    )
                    db.add(commission)
                    await db.flush()
            except IntegrityError:
                # uq_referral_commissions_order_earner — already created.
                continue
            created.append(commission)
            await logger.ainfo(
                "commission_created",
                commission_id=str(commission.id),
                order_id=str(order.id),
                earner_id=str(earner_id),
                amount=amount,
                level=level,
            )
        return created

    @staticmethod
    async def _pay_commission_row(
        db: AsyncSession,
        commission: ReferralCommission,
        *,
        order: Any,
        cfg: dict[str, Any],
    ) -> tuple[bool, bool]:
        """Pay one PENDING commission row in place. Returns (paid, expired).

        The single payout implementation shared by the eager path
        (:meth:`settle_order_rewards`) and the retry sweep
        (:meth:`pay_pending_commissions`) — two copies would drift.
        """
        from app.modules.orders.domain.models import OrderStatus

        if order is None:
            commission.status = CommissionStatus.EXPIRED
            return False, True
        if order.status in (OrderStatus.CANCELED, OrderStatus.REFUNDED):
            commission.status = CommissionStatus.EXPIRED
            return False, True
        if order.status != OrderStatus.COMPLETED:
            return False, False  # not settled yet; a later pass decides
        if not cfg.get("enabled", True):
            return False, False  # program paused — keep rows PENDING
        if not referral_config.module_enabled(cfg, "commission"):
            # Commission module switched off — keep rows PENDING so turning
            # it back on pays them (pausing is not cancelling).
            return False, False
        if not await ReferralService._earner_is_eligible(db, commission.earner_id):
            commission.status = CommissionStatus.EXPIRED
            return False, True

        credited = await _credit_reward(
            db,
            user_id=commission.earner_id,
            amount=commission.amount,
            reference_type=_COMMISSION_REF[commission.level],
            reference_id=commission.id,
            description=f"پورسانت خرید زیرمجموعه (سفارش {order.order_number})",
        )
        commission.status = CommissionStatus.PAID
        if credited and cfg.get("notify_on_commission", True):
            await _notify_reward(
                db,
                user_id=commission.earner_id,
                notif_type="wallet_referral_commission",
                title="پورسانت خرید زیرمجموعه",
                template=str(cfg.get("commission_notif_text", "")),
                amount_rial=commission.amount,
                idempotency_key=f"referral-commission:{commission.id}",
            )
        return credited, False

    @staticmethod
    async def settle_order_rewards(
        db: AsyncSession, order_id: uuid.UUID
    ) -> dict[str, Any]:
        """Eager payout: create + pay this order's commissions right now.

        Called from the order-completion paths (admin status change, shipment
        delivered) so a reward is paid at the moment the event happens instead
        of waiting for the periodic sweep. Best-effort by contract — callers
        wrap it so the order flow never fails on referral logic; anything
        unpaid stays PENDING and the sweep retries it (the at-least-once half).
        """
        from app.modules.orders.domain.models import Order

        created = await ReferralService.process_order_commissions(db, order_id)
        cfg = await referral_config.get_config(db)
        order = await db.get(Order, order_id)
        rows = (
            (
                await db.execute(
                    select(ReferralCommission)
                    .where(
                        ReferralCommission.order_id == order_id,
                        ReferralCommission.status == CommissionStatus.PENDING,
                    )
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        paid = 0
        total = 0
        for commission in rows:
            credited, _expired = await ReferralService._pay_commission_row(
                db, commission, order=order, cfg=cfg
            )
            if credited:
                paid += 1
                total += commission.amount
        return {"created": len(created), "paid": paid, "total_paid": total}

    @staticmethod
    async def pay_pending_commissions(
        db: AsyncSession, *, limit: int = 100
    ) -> dict[str, Any]:
        """Credit wallet for PENDING commissions; expire dead ones (retry pass).

        Each credit is at-most-once via the wallet partial unique index and
        the commission flips to PAID only after the credit succeeded in the
        same transaction — a failure anywhere rolls both back and the next
        sweep retries.
        """
        cfg = await referral_config.get_config(db)
        from app.modules.orders.domain.models import Order

        rows = (
            (
                await db.execute(
                    select(ReferralCommission)
                    .where(ReferralCommission.status == CommissionStatus.PENDING)
                    .order_by(ReferralCommission.created_at.asc())
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )

        paid_count = 0
        total = 0
        expired = 0
        for commission in rows:
            order = await db.get(Order, commission.order_id)
            credited, was_expired = await ReferralService._pay_commission_row(
                db, commission, order=order, cfg=cfg
            )
            if credited:
                paid_count += 1
                total += commission.amount
            if was_expired:
                expired += 1

        return {"processed": len(rows), "paid_count": paid_count, "total_paid": total, "expired": expired}

    # ── Recharge bonus ────────────────────────────────────────────────

    @staticmethod
    async def apply_recharge_bonus(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        payment_id: uuid.UUID,
        amount_rial: int,
    ) -> int:
        """Credit the recharge bonus for a wallet top-up. Returns the amount.

        At-most-once per payment via the wallet partial unique index. Called
        inline from the two top-up credit sites and re-attempted by the sweep
        for any top-up that missed it (the at-least-once half).
        """
        cfg = await referral_config.get_config(db)
        if not cfg.get("enabled", True):
            return 0
        # Per-module switch: the recharge-bonus module can be off while the
        # referral modules stay on.
        if not referral_config.module_enabled(cfg, "recharge_bonus"):
            return 0
        percent_bp = referral_config.percent_to_bp(cfg.get("recharge_bonus_percent", 0))
        if percent_bp <= 0:
            return 0
        if referral_config._started_at(cfg) is None:
            return 0
        # Integer money math: Rial × bp / 10,000 (1% = 100 bp).
        bonus = (amount_rial * percent_bp) // 10_000
        if bonus <= 0:
            return 0

        credited = await _credit_reward(
            db,
            user_id=user_id,
            amount=bonus,
            reference_type=REF_RECHARGE_BONUS,
            reference_id=payment_id,
            description="بونوس شارژ کیف پول (پاداش بونوس)",
        )
        if credited and cfg.get("notify_on_recharge_bonus", True):
            await _notify_reward(
                db,
                user_id=user_id,
                notif_type="wallet_recharge_bonus",
                title="بونوس شارژ کیف پول",
                template=str(cfg.get("recharge_bonus_notif_text", "")),
                amount_rial=bonus,
                idempotency_key=f"recharge-bonus:{payment_id}",
            )
        return bonus if credited else 0

    @staticmethod
    async def pay_pending_recharge_bonuses(
        db: AsyncSession, *, limit: int = 100, lookback_days: int = 90
    ) -> dict[str, Any]:
        """Sweep recent wallet top-ups that never got their bonus.

        The inline call sites are best-effort (a top-up must never fail
        because of the bonus); this sweep is the durable half. Discovers
        top-up credits whose payment has no ``recharge_bonus`` wallet row.
        """
        from datetime import UTC, datetime, timedelta

        from app.modules.wallet.domain.models import Wallet, WalletTransaction

        cfg = await referral_config.get_config(db)
        if not cfg.get("enabled", True):
            return {"checked": 0, "paid_count": 0, "total_paid": 0}
        if not referral_config.module_enabled(cfg, "recharge_bonus"):
            return {"checked": 0, "paid_count": 0, "total_paid": 0}
        if referral_config.percent_to_bp(cfg.get("recharge_bonus_percent", 0)) <= 0:
            return {"checked": 0, "paid_count": 0, "total_paid": 0}
        # Only top-ups from after the program started earn the bonus.
        started_at = referral_config._started_at(cfg)
        if started_at is None:
            return {"checked": 0, "paid_count": 0, "total_paid": 0}
        program_start = datetime.fromisoformat(started_at)

        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
        if program_start > cutoff:
            cutoff = program_start
        # A bonus row exists for this payment when a recharge_bonus wallet
        # transaction shares its reference_id.
        bonus_exists = (
            select(WalletTransaction.id)
            .where(
                WalletTransaction.reference_type == REF_RECHARGE_BONUS,
                WalletTransaction.reference_id == WalletTransaction.reference_id,
            )
            .exists()
        )
        topups = (
            await db.execute(
                select(WalletTransaction, Wallet.user_id)
                .join(Wallet, Wallet.id == WalletTransaction.wallet_id)
                .where(
                    WalletTransaction.reference_type == "wallet_topup",
                    WalletTransaction.reference_id.is_not(None),
                    WalletTransaction.created_at >= cutoff,
                    ~bonus_exists,
                )
                .order_by(WalletTransaction.created_at.asc())
                .limit(limit)
            )
        ).all()

        paid_count = 0
        total = 0
        for topup, user_id in topups:
            bonus = await ReferralService.apply_recharge_bonus(
                db,
                user_id=user_id,
                payment_id=topup.reference_id,
                amount_rial=topup.amount,
            )
            if bonus:
                paid_count += 1
                total += bonus
        return {"checked": len(topups), "paid_count": paid_count, "total_paid": total}

    # ── Sweep orchestration ───────────────────────────────────────────

    @staticmethod
    async def run_reward_sweep(db: AsyncSession) -> dict[str, Any]:
        """Run every referral/bonus payout pass once (idempotent)."""
        from app.modules.orders.domain.models import Order, OrderStatus

        # 1. Create missing commission rows for completed referred orders.
        existing = select(ReferralCommission.order_id).distinct()
        order_rows = (
            (
                await db.execute(
                    select(Order.id)
                    .join(Referral, Referral.referred_id == Order.user_id)
                    .where(
                        Order.status == OrderStatus.COMPLETED,
                        Order.id.not_in(existing),
                    )
                    .order_by(Order.created_at.asc())
                    .limit(100)
                    .with_for_update(of=Order, skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        created = 0
        for order_id in order_rows:
            created += len(await ReferralService.process_order_commissions(db, order_id))

        # 2. Pay PENDING commissions + expire dead ones.
        commissions = await ReferralService.pay_pending_commissions(db)

        # 3. Settle PENDING signup gifts.
        gifts = await ReferralService.pay_pending_signup_gifts(db)

        # 4. Catch up missed recharge bonuses.
        bonuses = await ReferralService.pay_pending_recharge_bonuses(db)

        return {
            "commissions_created": created,
            "commissions": commissions,
            "signup_gifts": gifts,
            "recharge_bonuses": bonuses,
        }

    # ── Queries ───────────────────────────────────────────────────────

    @staticmethod
    async def get_referrals(
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Referral], int]:
        """Return paginated referrals where the user is the referrer."""
        count_stmt = (
            select(func.count()).select_from(Referral).where(Referral.referrer_id == user_id)
        )
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Referral)
            .where(Referral.referrer_id == user_id)
            .order_by(Referral.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def get_referral_stats(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
        """Aggregate referral statistics for a user."""
        # Total / status counts
        stmt = select(
            func.count().label("total"),
            func.count().filter(Referral.status == ReferralStatus.COMPLETED).label("completed"),
            func.count().filter(Referral.status == ReferralStatus.PENDING).label("pending"),
            func.count().filter(Referral.level == 1).label("level1"),
        ).where(Referral.referrer_id == user_id)
        row = (await db.execute(stmt)).one()

        # Level-2 count: referrals whose referrer is themselves referred by
        # this user (chain walk — there are no level-2 rows).
        level2_stmt = (
            select(func.count())
            .select_from(Referral)
            .where(
                Referral.referrer_id.in_(
                    select(Referral.referred_id).where(Referral.referrer_id == user_id)
                )
            )
        )
        level2 = (await db.execute(level2_stmt)).scalar_one()

        # Commission totals (by earner — covers both levels).
        earned_stmt = select(
            func.coalesce(func.sum(ReferralCommission.amount), 0)
        ).where(
            ReferralCommission.earner_id == user_id,
            ReferralCommission.status == CommissionStatus.PAID,
        )
        earned = (await db.execute(earned_stmt)).scalar_one()

        pending_stmt = select(
            func.coalesce(func.sum(ReferralCommission.amount), 0)
        ).where(
            ReferralCommission.earner_id == user_id,
            ReferralCommission.status == CommissionStatus.PENDING,
        )
        pending_amount = (await db.execute(pending_stmt)).scalar_one()

        return {
            "total_referrals": row.total,
            "completed_referrals": row.completed,
            "pending_referrals": row.pending,
            "level1_count": row.level1,
            "level2_count": level2,
            "total_commission_earned": earned,
            "total_commission_pending": pending_amount,
        }

    @staticmethod
    async def get_commissions(
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ReferralCommission], int]:
        """Return paginated commissions for an earner."""
        base = select(ReferralCommission).where(ReferralCommission.earner_id == user_id)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = base.order_by(ReferralCommission.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total
