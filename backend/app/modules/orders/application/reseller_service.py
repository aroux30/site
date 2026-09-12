"""B2B Reseller API Hub service (Karta Phase 4).

Implements:
- Reseller API key generation, validation, and IP whitelisting
- Automated wholesale catalog inquiry with live digital stock levels
- Atomic bulk purchase and immediate PIN revelation
- Pre-paid credit balance management and deduction
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.modules.catalog.domain.models import Product, ProductStatus
from app.modules.inventory.application import card_service
from app.modules.inventory.domain.digital_models import DigitalCard, DigitalCardStatus
from app.modules.orders.domain.models import Order, OrderStatus
from app.modules.orders.domain.reseller_models import ResellerApiKey

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── API Key Management ───────────────────────────────────────────────────


async def create_reseller_api_key(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    ip_whitelist: list[str] | None = None,
    initial_credit: int = 0,
    expires_at: datetime | None = None,
    rate_limit_per_minute: int = 60,
) -> tuple[ResellerApiKey, str]:
    """Create a new partner API key.

    Returns the DB record and the plaintext key (revealed only once).
    """
    safe_user_id = uuid.UUID(str(user_id))
    prefix = f"b2b_{secrets.token_hex(4)}"
    secret = secrets.token_urlsafe(32)
    plaintext_key = f"{prefix}_{secret}"
    key_hash = hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest()

    record = ResellerApiKey(
        user_id=safe_user_id,
        name=name.strip(),
        key_prefix=prefix,
        key_hash=key_hash,
        ip_whitelist=ip_whitelist,
        credit_balance=initial_credit,
        is_active=True,
        rate_limit_per_minute=rate_limit_per_minute,
        expires_at=expires_at,
    )
    db.add(record)
    await db.flush()

    await logger.ainfo("reseller_api_key_created", reseller_id=str(record.id), name=name)
    return record, plaintext_key


async def verify_reseller_api_key(
    db: AsyncSession,
    raw_api_key: str,
    client_ip: str | None = None,
) -> ResellerApiKey:
    """Validate incoming API key from header and verify IP whitelisting."""
    if not raw_api_key:
        raise UnauthorizedError(detail="Missing X-API-KEY header")

    clean_key = raw_api_key.strip()
    key_hash = hashlib.sha256(clean_key.encode("utf-8")).hexdigest()

    # Load active keys and match hash in memory to avoid dynamic SQL queries
    stmt = select(ResellerApiKey).where(ResellerApiKey.is_active.is_(True))
    active_keys = list((await db.execute(stmt)).scalars().all())
    record = next((k for k in active_keys if k.key_hash == key_hash), None)

    if record is None:
        raise UnauthorizedError(detail="کلید API همکار نامعتبر یا غیرفعال است")

    now = datetime.now(UTC)
    if record.expires_at and record.expires_at < now:
        raise UnauthorizedError(detail="اعتبار کلید API همکار منقضی شده است")

    # IP Whitelist check
    if record.ip_whitelist and client_ip:
        clean_ip = client_ip.split(",")[0].strip()
        if clean_ip not in record.ip_whitelist:
            await logger.awarning(
                "reseller_ip_rejected",
                reseller_id=str(record.id),
                client_ip=clean_ip,
                allowed=record.ip_whitelist,
            )
            raise ForbiddenError(detail=f"دسترسی از این آدرس آی‌پی مجاز نیست: {clean_ip}")

    return record


# ── Wholesale Catalog Stock Inquiry ───────────────────────────────────────


async def get_b2b_catalog_stock(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Return active digital products with their live available stock count."""
    prod_stmt = (
        select(Product)
        .where(
            Product.is_active.is_(True),
            Product.status == ProductStatus.ACTIVE,
        )
        .order_by(Product.name.asc())
    )
    products = list((await db.execute(prod_stmt)).scalars().all())

    now = datetime.now(UTC)
    count_stmt = (
        select(DigitalCard.product_id, func.count(DigitalCard.id))
        .where(
            DigitalCard.status == DigitalCardStatus.AVAILABLE,
            (DigitalCard.expire_at.is_(None)) | (DigitalCard.expire_at > now),
        )
        .group_by(DigitalCard.product_id)
    )
    stock_counts = dict((await db.execute(count_stmt)).all())

    result = []
    for prod in products:
        available = stock_counts.get(prod.id, 0)
        result.append(
            {
                "product_id": prod.id,
                "name": prod.name,
                "slug": prod.slug,
                "available_stock": available,
                "is_in_stock": available > 0,
            }
        )
    return result


# ── Wholesale Purchase & Instant PIN Allocation ───────────────────────────


async def b2b_purchase_cards(
    db: AsyncSession,
    reseller_key: ResellerApiKey,
    product_id: uuid.UUID,
    quantity: int,
    unit_price: int | None = None,
) -> dict[str, Any]:
    """Execute automated B2B order, deduct credit, and immediately return PINs.

    The payable unit price is always resolved server-side from the active
    volume tiers (falling back to the cheapest active variant price); the
    caller-supplied ``unit_price`` is only accepted when it matches.
    """
    if quantity <= 0:
        raise ValidationError("تعداد خرید باید حداقل ۱ باشد")

    # Lock the reseller key row so concurrent purchases cannot overdraw the
    # pre-paid credit balance (read-modify-write race).
    locked_key = await db.get(ResellerApiKey, reseller_key.id, with_for_update=True)
    if locked_key is None or not locked_key.is_active:
        raise UnauthorizedError(detail="کلید API همکار نامعتبر یا غیرفعال است")
    reseller_key = locked_key

    # Resolve the price server-side: load the product with its variants via
    # the primary key, then apply volume tiers on top of the base price.
    from app.modules.inventory.application import pricing_service

    product = await db.get(
        Product,
        uuid.UUID(str(product_id)),
        options=(selectinload(Product.variants),),
    )
    if product is None or not product.is_active or product.status != ProductStatus.ACTIVE:
        raise NotFoundError(resource="Product", detail="محصول همکار یافت نشد یا غیرفعال است")

    variant_prices = [v.price for v in product.variants if v.is_active and v.price > 0]
    if not variant_prices:
        raise ConflictError(detail="این محصول هیچ گونه قیمت فعالی برای فروش ندارد")

    pricing = await pricing_service.calculate_dynamic_price(
        db,
        product_id=product.id,
        quantity=quantity,
        base_unit_price=min(variant_prices),
    )
    resolved_unit_price = int(pricing["unit_price"])
    if unit_price is not None and int(unit_price) != resolved_unit_price:
        raise ConflictError(
            detail=(
                "قیمت ارسالی با قیمت سیستم هم‌خوانی ندارد. "
                f"قیمت صحیح برای {quantity} عدد: {resolved_unit_price:,} ریال"
            )
        )

    total_cost = resolved_unit_price * quantity
    if reseller_key.credit_balance < total_cost:
        raise ConflictError(
            detail=(
                f"اعتبار ریالی حساب همکار کافی نیست. "
                f"هزینه: {total_cost:,} ریال، اعتبار موجود: {reseller_key.credit_balance:,} ریال"
            )
        )

    # 1. Deduct pre-paid credit
    reseller_key.credit_balance -= total_cost

    # 2. Create internal order record for audit
    order_num = f"B2B-{datetime.now(UTC).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
    order = Order(
        user_id=reseller_key.user_id,
        order_number=order_num,
        status=OrderStatus.COMPLETED,
        subtotal=total_cost,
        shipping_cost=0,
        tax=0,
        discount_amount=0,
        total=total_cost,
        notes=f"B2B purchase via API key: {reseller_key.name}",
    )
    db.add(order)
    await db.flush()

    # 3. Atomically allocate digital cards from stock
    await card_service.allocate_cards_for_order(
        db,
        product_id=product_id,
        order_id=order.id,
        quantity=quantity,
    )

    # 4. Decrypt PINs for immediate API response
    delivered = await card_service.get_delivered_cards_for_order(db, order_id=order.id)

    await logger.ainfo(
        "b2b_order_completed",
        order_number=order_num,
        reseller_id=str(reseller_key.id),
        quantity=quantity,
        total_cost=total_cost,
        remaining_credit=reseller_key.credit_balance,
    )

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "product_id": product_id,
        "quantity": quantity,
        "total_cost": total_cost,
        "remaining_credit": reseller_key.credit_balance,
        "cards": delivered,
    }


async def get_reseller_balance(
    db: AsyncSession,
    reseller_key_id: uuid.UUID,
) -> int:
    """Return live pre-paid credit balance in IRR."""
    safe_id = uuid.UUID(str(reseller_key_id))
    record = await db.get(ResellerApiKey, safe_id)
    if record is None:
        raise NotFoundError(resource="ResellerApiKey", detail="کلید همکار یافت نشد")
    return record.credit_balance
