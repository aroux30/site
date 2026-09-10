"""Real PostgreSQL database concurrency and race-condition integration tests.

Mandatory testing suite executing actual concurrent PostgreSQL transactions:
- TEST-CONCURRENCY-001: 100 concurrent transactions for stock=1 -> exactly 1 success, oversold=0
- TEST-CONCURRENCY-002: 50 concurrent transactions redeeming 1-use coupon -> exactly 1 success
- TEST-CONCURRENCY-003: 2 concurrent wallet debits exceeding balance -> exactly 1 success, balance >= 0
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.database.session import async_session_factory
from app.core.exceptions.handlers import ConflictError, ValidationError
from app.modules.catalog.domain.models import Brand, Category, Product, ProductStatus, ProductType, ProductVariant
from app.modules.discounts.application import discount_service
from app.modules.discounts.domain.models import Coupon, Discount, DiscountScope, DiscountType
from app.modules.inventory.application import inventory_service
from app.modules.inventory.domain.models import InventoryItem, InventoryReservation, ReservationStatus
from app.modules.users.domain.models import User
from app.modules.wallet.application import wallet_service
from app.modules.wallet.domain.models import Wallet, WalletTransactionType


@pytest.mark.asyncio
async def test_real_postgres_100_concurrent_inventory_reservations():
    """TEST-CONCURRENCY-001: Execute 100 real concurrent PostgreSQL transactions on stock=1."""
    # 1. Setup real variant and inventory item in PostgreSQL
    async with async_session_factory() as setup_db:
        cat = Category(name="تست کانکارنسی", slug=f"test-cat-{uuid.uuid4().hex[:8]}")
        setup_db.add(cat)
        await setup_db.flush()

        prod = Product(
            name="کالای تست همزمانی",
            slug=f"prod-conc-{uuid.uuid4().hex[:8]}",
            category_id=cat.id,
            product_type=ProductType.SIMPLE,
            status=ProductStatus.ACTIVE,
            is_active=True,
        )
        setup_db.add(prod)
        await setup_db.flush()

        variant = ProductVariant(
            product_id=prod.id,
            sku=f"SKU-CONC-{uuid.uuid4().hex[:6]}",
            price=1_000_000,
            is_active=True,
        )
        setup_db.add(variant)
        await setup_db.flush()

        inv_item = InventoryItem(
            variant_id=variant.id,
            available=1,  # Only 1 item available
            reserved=0,
            committed=0,
            track_inventory=True,
            backorder_allowed=False,
        )
        setup_db.add(inv_item)
        await setup_db.commit()

        target_variant_id = variant.id
        target_inv_id = inv_item.id

    # 2. Launch 100 independent concurrent database transactions
    async def _buyer_transaction(buyer_idx: int):
        async with async_session_factory() as session:
            try:
                # Executes SELECT ... FOR UPDATE in PostgreSQL
                res = await inventory_service.reserve_stock(
                    session,
                    variant_id=target_variant_id,
                    quantity=1,
                    order_id=uuid.uuid4(),
                )
                await session.commit()
                return ("SUCCESS", res.id)
            except ConflictError:
                await session.rollback()
                return ("REJECTED_STOCK", None)
            except Exception as e:
                await session.rollback()
                return ("ERROR", str(e))

    results = await asyncio.gather(*[_buyer_transaction(i) for i in range(100)])

    successes = [r for r in results if r[0] == "SUCCESS"]
    rejections = [r for r in results if r[0] == "REJECTED_STOCK"]

    # 3. Assert invariants in the real PostgreSQL database
    assert len(successes) == 1, f"Expected exactly 1 successful reservation, got {len(successes)}"
    assert len(rejections) == 99, f"Expected 99 rejections due to stock depletion, got {len(rejections)}"

    async with async_session_factory() as verify_db:
        # Check actual database row
        stmt = select(InventoryItem).where(InventoryItem.id == target_inv_id)
        row = (await verify_db.execute(stmt)).scalar_one()

        assert row.available == 0, f"Available stock in DB must be 0, found {row.available}"
        assert row.reserved == 1, f"Reserved stock in DB must be 1, found {row.reserved}"

        # Verify reservations table has exactly 1 pending reservation
        res_stmt = select(InventoryReservation).where(
            InventoryReservation.inventory_item_id == target_inv_id,
            InventoryReservation.status == ReservationStatus.PENDING,
        )
        reservations = list((await verify_db.execute(res_stmt)).scalars().all())
        assert len(reservations) == 1, "Exactly one reservation record must exist in PostgreSQL"


@pytest.mark.asyncio
async def test_real_postgres_50_concurrent_single_use_coupon_redemptions():
    """TEST-CONCURRENCY-002: Execute 50 concurrent transactions for a single-use coupon."""
    async with async_session_factory() as setup_db:
        now = datetime.now(timezone.utc)
        disc = Discount(
            name="کوپن تست همزمانی",
            type=DiscountType.FIXED,
            value=100_000,
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1),
            is_active=True,
            scope=DiscountScope.GLOBAL,
        )
        setup_db.add(disc)
        await setup_db.flush()

        coupon = Coupon(
            discount_id=disc.id,
            code=f"CONC-{uuid.uuid4().hex[:6].upper()}",
            is_active=True,
            usage_limit=1,
            usage_count=0,
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1),
        )
        setup_db.add(coupon)
        await setup_db.commit()

        target_coupon_id = coupon.id
        target_discount_id = disc.id

    async def _redeem_transaction(buyer_num: int):
        user_id = uuid.uuid4()
        order_id = uuid.uuid4()
        async with async_session_factory() as session:
            try:
                # Apply discount in transaction with lock
                redemption = await discount_service.apply_discount(
                    session,
                    coupon_id=target_coupon_id,
                    user_id=user_id,
                    order_id=order_id,
                    amount=100_000,
                )
                await session.commit()
                return ("SUCCESS", redemption.id)
            except Exception:
                await session.rollback()
                return ("REJECTED", None)

    results = await asyncio.gather(*[_redeem_transaction(i) for i in range(50)])

    successes = [r for r in results if r[0] == "SUCCESS"]
    rejections = [r for r in results if r[0] == "REJECTED"]

    assert len(successes) == 1, f"Expected exactly 1 redemption, got {len(successes)}"
    assert len(rejections) == 49, f"Expected 49 rejections, got {len(rejections)}"

    async with async_session_factory() as verify_db:
        stmt = select(Coupon).where(Coupon.id == target_coupon_id)
        c_row = (await verify_db.execute(stmt)).scalar_one()
        assert c_row.usage_count == 1, "Usage count in PostgreSQL must be exactly 1"


@pytest.mark.asyncio
async def test_real_postgres_concurrent_wallet_debits_prevent_double_spending():
    """TEST-CONCURRENCY-003: 2 concurrent transactions trying to debit full wallet balance."""
    async with async_session_factory() as setup_db:
        user = User(
            phone=f"0912{uuid.uuid4().hex[:7]}",
            password_hash="testhash",
            is_active=True,
        )
        setup_db.add(user)
        await setup_db.flush()

        wallet = Wallet(
            user_id=user.id,
            balance=1_000_000,  # 1,000,000 Rials
            is_active=True,
        )
        setup_db.add(wallet)
        await setup_db.commit()

        target_user_id = user.id

    async def _debit_transaction(req_id: int):
        async with async_session_factory() as session:
            try:
                tx = await wallet_service.debit(
                    session,
                    user_id=target_user_id,
                    amount=1_000_000,
                    tx_type=WalletTransactionType.PURCHASE,
                    description=f"Purchase attempt {req_id}",
                )
                await session.commit()
                return ("SUCCESS", tx.id)
            except ValidationError:
                await session.rollback()
                return ("INSUFFICIENT_FUNDS", None)
            except Exception as e:
                await session.rollback()
                return ("ERROR", str(e))

    # Run two parallel full-balance debits simultaneously
    results = await asyncio.gather(_debit_transaction(1), _debit_transaction(2))

    successes = [r for r in results if r[0] == "SUCCESS"]
    failures = [r for r in results if r[0] == "INSUFFICIENT_FUNDS"]

    assert len(successes) == 1, "Exactly one debit transaction must succeed"
    assert len(failures) == 1, "Second concurrent debit must be rejected with insufficient funds"

    async with async_session_factory() as verify_db:
        balance = await wallet_service.get_balance(verify_db, target_user_id)
        assert balance == 0, f"Wallet balance in DB must be exactly 0, got {balance}"
