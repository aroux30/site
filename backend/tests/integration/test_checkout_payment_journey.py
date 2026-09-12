"""End-to-end checkout → payment → order journey against real PostgreSQL.

TEST-JOURNEY-001 (TASK P5-01): customer login state → cart → server-priced
checkout with inventory reservation → mock-gateway payment → webhook verify
→ order CONFIRMED → cancel → restock.  Plus the P0 rejection matrix from
the audit (amount mismatch, foreign order, non-payable order).

TEST-JOURNEY-002/003 (TASK P5-02): duplicate webhook deliveries and a
racing verify/webhook pair must each produce exactly one effect.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app.core.database.session import async_session_factory
from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.modules.cart.domain.models import Cart, CartItem, CartStatus
from app.modules.catalog.domain.models import (
    Category,
    Product,
    ProductStatus,
    ProductType,
    ProductVariant,
)
from app.modules.checkout.application import checkout_service
from app.modules.checkout.application.checkout_service import CreateOrderRequest
from app.modules.inventory.domain.models import InventoryItem
from app.modules.orders.application import order_service
from app.modules.orders.domain.models import (
    Order,
    OrderStatus,
    OrderStatusHistory,
)
from app.modules.payments.application import payment_service
from app.modules.payments.domain.models import (
    PaymentStatus,
    PaymentWebhookEvent,
)
from app.modules.shipping.domain.models import ShippingMethod, ShippingRate
from app.modules.users.domain.models import Address, User


async def _seed_journey(order_total_hint: int = 2_000_000):
    """Seed one customer with a 2-item cart ready for checkout.

    Returns a dict of the created ids (user, cart, variant, address,
    shipping_method) and the inventory item id.
    """
    suffix = uuid.uuid4().hex[:8]
    async with async_session_factory() as db:
        user = User(
            phone=f"0912{suffix[:8]}",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()

        cat = Category(name=f"کیف پول تست {suffix}", slug=f"cat-j-{suffix}")
        db.add(cat)
        await db.flush()

        product = Product(
            name="کالای سفر تست",
            slug=f"prod-j-{suffix}",
            category_id=cat.id,
            product_type=ProductType.SIMPLE,
            status=ProductStatus.ACTIVE,
            is_active=True,
        )
        db.add(product)
        await db.flush()

        variant = ProductVariant(
            product_id=product.id,
            sku=f"SKU-J-{suffix}",
            price=1_000_000,
            is_active=True,
        )
        db.add(variant)
        await db.flush()

        inv = InventoryItem(
            variant_id=variant.id,
            available=10,
            reserved=0,
            committed=0,
            track_inventory=True,
            backorder_allowed=False,
        )
        db.add(inv)

        address = Address(
            user_id=user.id,
            title="خانه",
            province="تهران",
            city="تهران",
            postal_code="1234567890",
            full_address="خیابان تست، پلاک ۱",
        )
        db.add(address)

        method = ShippingMethod(
            name=f"پست پیشتاز {suffix}",
            slug=f"post-j-{suffix}",
            is_active=True,
        )
        db.add(method)
        await db.flush()
        db.add(
            ShippingRate(
                method_id=method.id,
                province="تهران",
                price=50_000,
                min_order_amount=None,
            )
        )

        cart = Cart(user_id=user.id, status=CartStatus.ACTIVE)
        db.add(cart)
        await db.flush()
        db.add(
            CartItem(
                cart_id=cart.id,
                variant_id=variant.id,
                quantity=2,
                price_snapshot=1_000_000,
            )
        )

        await db.commit()
        return {
            "user_id": user.id,
            "cart_id": cart.id,
            "variant_id": variant.id,
            "inventory_item_id": inv.id,
            "address_id": address.id,
            "shipping_method_id": method.id,
        }


def _create_order_request(fixture: dict) -> CreateOrderRequest:
    return CreateOrderRequest(
        cart_id=fixture["cart_id"],
        address_id=fixture["address_id"],
        shipping_method_id=fixture["shipping_method_id"],
        coupon_code=None,
        payment_method="mock",
        idempotency_key=f"journey-{uuid.uuid4().hex[:12]}",
        notes=None,
    )


async def _committed_stock(inventory_item_id) -> int:
    async with async_session_factory() as db:
        item = await db.get(InventoryItem, inventory_item_id)
        assert item is not None
        return item.committed


async def _order_row(order_id) -> Order:
    async with async_session_factory() as db:
        return await db.get(Order, order_id)


@pytest.mark.asyncio
async def test_journey_checkout_payment_confirm_cancel_restock():
    """TEST-JOURNEY-001: the full happy-path purchase, then cancel+restock."""
    fx = await _seed_journey()

    # ── 1. Server-priced checkout ────────────────────────────────────
    async with async_session_factory() as db:
        result = await checkout_service.create_order(
            db, user_id=fx["user_id"], data=_create_order_request(fx)
        )
        await db.commit()

    assert result.total == 2_000_000 + 50_000 + result.tax  # subtotal + shipping + tax
    assert result.subtotal == 2_000_000
    order_id = result.order_id

    order = await _order_row(order_id)
    assert order.status == OrderStatus.PENDING
    assert await _committed_stock(fx["inventory_item_id"]) == 2  # reserved+committed

    # Cart converted — the cart must not be reusable
    async with async_session_factory() as db:
        cart = await db.get(Cart, fx["cart_id"])
        assert cart is not None and cart.status == CartStatus.CONVERTED

    # ── 2. Pay with the mock gateway (server-side amount enforced) ──
    async with async_session_factory() as db:
        payment = await payment_service.create_payment(
            db,
            user_id=fx["user_id"],
            order_id=order_id,
            provider="mock",
            amount=result.total,
            idempotency_key=f"pay-{uuid.uuid4().hex[:12]}",
        )
        # Read attributes BEFORE commit: expire_on_commit would lazy-refresh
        # the ORM object outside the greenlet.
        payment_id = payment.id
        payment_authority = payment.authority or ""
        payment_status = payment.status
        await db.commit()
    assert payment_status == PaymentStatus.PROCESSING

    # ── 3. Webhook verify → order CONFIRMED exactly once ────────────
    async with async_session_factory() as db:
        verified = await payment_service.process_callback(
            db,
            provider="mock",
            callback_data=type(
                "CB",
                (),
                {
                    "authority": payment_authority,
                    "status": "OK",
                    "track_id": None,
                    "id": None,
                    "order_id": None,
                    "amount": None,
                    "card_no": None,
                    "hashed_card_no": None,
                    "date": None,
                    "extra": None,
                    "payment_id": None,
                    "payment_status": None,
                    "model_dump": lambda self, mode="json": {
                        "authority": payment_authority,
                        "status": "OK",
                    },
                },
            )(),
        )
        await db.commit()
    assert verified.status == PaymentStatus.COMPLETED

    order = await _order_row(order_id)
    assert order.status == OrderStatus.CONFIRMED

    confirmed_rows = 0
    async with async_session_factory() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(OrderStatusHistory)
            .where(
                OrderStatusHistory.order_id == order_id,
                OrderStatusHistory.to_status == OrderStatus.CONFIRMED.value,
            )
        )
        confirmed_rows = int(count or 0)
    assert confirmed_rows == 1

    # ── 4. Customer cancel → CANCELED + stock returned ───────────────
    async with async_session_factory() as db:
        await order_service.cancel_order(
            db, user_id=fx["user_id"], order_id=order_id, reason="تست سفر"
        )
        await db.commit()

    order = await _order_row(order_id)
    assert order.status == OrderStatus.CANCELED
    assert await _committed_stock(fx["inventory_item_id"]) == 0


@pytest.mark.asyncio
async def test_journey_rejects_amount_mismatch():
    """PAY-01 e2e: paying 1 IRR for a 2M IRR order is rejected."""
    fx = await _seed_journey()
    async with async_session_factory() as db:
        result = await checkout_service.create_order(
            db, user_id=fx["user_id"], data=_create_order_request(fx)
        )
        await db.commit()

    with pytest.raises(ValidationError) as exc:
        async with async_session_factory() as db:
            await payment_service.create_payment(
                db,
                user_id=fx["user_id"],
                order_id=result.order_id,
                provider="mock",
                amount=1,
            )
    assert "does not match" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_journey_rejects_foreign_and_non_pending_order():
    """PAY-02/03 e2e: foreign order → 404-style; non-PENDING → conflict."""
    fx = await _seed_journey()
    async with async_session_factory() as db:
        result = await checkout_service.create_order(
            db, user_id=fx["user_id"], data=_create_order_request(fx)
        )
        await db.commit()
    order_id = result.order_id
    outsider = uuid.uuid4()

    with pytest.raises(NotFoundError):
        async with async_session_factory() as db:
            await payment_service.create_payment(
                db,
                user_id=outsider,
                order_id=order_id,
                provider="mock",
                amount=result.total,
            )

    # Cancel → order no longer payable
    async with async_session_factory() as db:
        await order_service.cancel_order(
            db, user_id=fx["user_id"], order_id=order_id, reason="انصراف"
        )
        await db.commit()

    with pytest.raises(ConflictError):
        async with async_session_factory() as db:
            await payment_service.create_payment(
                db,
                user_id=fx["user_id"],
                order_id=order_id,
                provider="mock",
                amount=result.total,
            )


class _CallbackShim:
    """Duck-typed PaymentCallbackData for process_callback tests."""

    def __init__(self, authority: str) -> None:
        self.authority = authority
        self.status = "OK"
        self.track_id = None
        self.id = None
        self.order_id = None
        self.amount = None
        self.card_no = None
        self.hashed_card_no = None
        self.date = None
        self.extra = None
        self.payment_id = None
        self.payment_status = None

    def model_dump(self, mode: str = "json") -> dict:
        return {"authority": self.authority, "status": "OK"}


@pytest.mark.asyncio
async def test_journey_duplicate_webhooks_are_idempotent():
    """TEST-JOURNEY-002 (P5-02): 3 identical webhook deliveries produce
    exactly one payment completion, one order confirmation, one webhook row.
    """
    fx = await _seed_journey()
    async with async_session_factory() as db:
        result = await checkout_service.create_order(
            db, user_id=fx["user_id"], data=_create_order_request(fx)
        )
        await db.commit()
        async with async_session_factory() as pay_db:
            payment = await payment_service.create_payment(
                pay_db,
                user_id=fx["user_id"],
                order_id=result.order_id,
                provider="mock",
                amount=result.total,
                idempotency_key=f"pay-{uuid.uuid4().hex[:12]}",
            )
            pay_authority = payment.authority or ""
            await pay_db.commit()

    cb = _CallbackShim(pay_authority)
    for _ in range(3):
        async with async_session_factory() as db:
            await payment_service.process_callback(db, provider="mock", callback_data=cb)
            await db.commit()

    order = await _order_row(result.order_id)
    assert order.status == OrderStatus.CONFIRMED

    async with async_session_factory() as db:
        webhook_rows = (
            await db.scalars(
                select(PaymentWebhookEvent).where(
                    PaymentWebhookEvent.provider == "mock",
                    PaymentWebhookEvent.event_id == pay_authority,
                )
            )
        ).all()
        assert len(webhook_rows) == 1
        assert webhook_rows[0].processed is True

        confirm_count = await db.scalar(
            select(func.count())
            .select_from(OrderStatusHistory)
            .where(
                OrderStatusHistory.order_id == result.order_id,
                OrderStatusHistory.to_status == OrderStatus.CONFIRMED.value,
            )
        )
        assert int(confirm_count or 0) == 1


@pytest.mark.asyncio
async def test_journey_verify_and_webhook_race_confirm_once():
    """TEST-JOURNEY-003 (P5-02): a racing verify + webhook pair must not
    double-confirm the order — the payment row lock serializes them.
    """
    fx = await _seed_journey()
    async with async_session_factory() as db:
        result = await checkout_service.create_order(
            db, user_id=fx["user_id"], data=_create_order_request(fx)
        )
        await db.commit()
        async with async_session_factory() as pay_db:
            payment = await payment_service.create_payment(
                pay_db,
                user_id=fx["user_id"],
                order_id=result.order_id,
                provider="mock",
                amount=result.total,
                idempotency_key=f"pay-{uuid.uuid4().hex[:12]}",
            )
            pay_id = payment.id
            pay_authority = payment.authority or ""
            await pay_db.commit()

    async def _do_verify():
        async with async_session_factory() as db:
            return await payment_service.verify_payment(
                db,
                payment_id=pay_id,
                authority=pay_authority,
                status="OK",
            )

    async def _do_webhook():
        async with async_session_factory() as db:
            return await payment_service.process_callback(
                db, provider="mock", callback_data=_CallbackShim(pay_authority)
            )

    results = await asyncio.gather(_do_verify(), _do_webhook())
    assert all(r.status == PaymentStatus.COMPLETED for r in results)

    order = await _order_row(result.order_id)
    assert order.status == OrderStatus.CONFIRMED

    async with async_session_factory() as db:
        confirm_count = await db.scalar(
            select(func.count())
            .select_from(OrderStatusHistory)
            .where(
                OrderStatusHistory.order_id == result.order_id,
                OrderStatusHistory.to_status == OrderStatus.CONFIRMED.value,
            )
        )
        assert int(confirm_count or 0) == 1
