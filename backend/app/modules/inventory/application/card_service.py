"""Digital card stock management, atomic allocation, and delivery (Karta Phase 1/2).

Implements:
- Atomic card allocation with SELECT FOR UPDATE (Karta checkOrderCardsAgain & markCards)
- Customer decrypted card retrieval
- Legal reading timestamp tracking (Karta reading flag)
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, or_, select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.inventory.application.crypto_service import decrypt_pin, encrypt_pin
from app.modules.inventory.domain.digital_models import (
    DigitalCard,
    DigitalCardStatus,
    DigitalDeliveryType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _file_filters(product_id: uuid.UUID, now: datetime) -> tuple[Any, ...]:
    """Shared filters for sellable FILE rows (available, unexpired)."""
    return (
        DigitalCard.product_id == product_id,
        DigitalCard.status == DigitalCardStatus.AVAILABLE,
        DigitalCard.delivery_type == DigitalDeliveryType.FILE,
        (DigitalCard.expire_at.is_(None)) | (DigitalCard.expire_at > now),
    )


async def allocate_cards_for_order(
    db: AsyncSession,
    product_id: uuid.UUID,
    order_id: uuid.UUID,
    quantity: int,
) -> list[DigitalCard]:
    """Atomically allocate digital cards to an order upon verified payment.

    Karta checkOrderCardsAgain/markCards semantics: candidate rows are
    locked (``FOR UPDATE``) and sufficiency is validated **before any card
    is mutated**. If stock is insufficient the function raises
    ``ConflictError`` with the session left untouched, so a caller that
    rolls back can never persist a partially-allocated order (P0.4).
    Re-runs for the same order are idempotent: already-assigned unique
    cards are counted and not re-allocated.
    """
    if quantity <= 0:
        raise ValidationError("Quantity to allocate must be positive")

    now = datetime.now(UTC)
    not_expired = or_(DigitalCard.expire_at.is_(None), DigitalCard.expire_at > now)

    # Idempotency: unique cards already delivered for this (order, product).
    # ORM expressions bind parameters automatically — no string SQL here.
    already_allocated = (
        await db.execute(
            select(func.count())
            .select_from(DigitalCard)
            .where(
                DigitalCard.product_id == product_id,
                DigitalCard.assigned_order_id == order_id,
                DigitalCard.delivery_type == DigitalDeliveryType.UNIQUE,
            )
        )
    ).scalar_one()
    remaining_needed = quantity - int(already_allocated or 0)
    if remaining_needed <= 0:
        return []

    # 1. Lock available UNIQUE card rows without mutating them.
    unique_filters = (
        DigitalCard.product_id == product_id,
        DigitalCard.status == DigitalCardStatus.AVAILABLE,
        DigitalCard.delivery_type == DigitalDeliveryType.UNIQUE,
        not_expired,
    )
    unique_stmt = (
        select(DigitalCard)
        .where(*unique_filters)
        .order_by(DigitalCard.created_at.asc())
        .limit(remaining_needed)
        .with_for_update()
    )
    unique_cards = list((await db.execute(unique_stmt)).scalars().all())

    # 2. Lock available FILE asset rows without mutating them — a file
    #    product consumes one stocked copy per purchase (Karta file cards
    #    are sold exactly like PIN cards; the row just carries a file path).
    shared_needed = remaining_needed - len(unique_cards)
    file_cards: list[DigitalCard] = []
    if shared_needed > 0:
        file_stmt = (
            select(DigitalCard)
            .where(*_file_filters(product_id, now))
            .order_by(DigitalCard.created_at.asc())
            .limit(shared_needed)
            .with_for_update()
        )
        file_cards = list((await db.execute(file_stmt)).scalars().all())

    # 3. Lock available SHARED capacity rows without mutating them.
    shared_needed -= len(file_cards)
    shared_cards: list[DigitalCard] = []
    if shared_needed > 0:
        shared_filters = (
            DigitalCard.product_id == product_id,
            DigitalCard.status == DigitalCardStatus.AVAILABLE,
            DigitalCard.delivery_type == DigitalDeliveryType.SHARED,
            DigitalCard.used_count < DigitalCard.max_uses,
            not_expired,
        )
        shared_stmt = (
            select(DigitalCard)
            .where(*shared_filters)
            .order_by(DigitalCard.created_at.asc())
            .with_for_update()
        )
        shared_cards = list((await db.execute(shared_stmt)).scalars().all())

    # 4. Validate sufficiency across locked candidates BEFORE mutating any
    #    row — the ConflictError below leaves the session untouched.
    shared_capacity = sum(card.max_uses - card.used_count for card in shared_cards)
    available_total = len(unique_cards) + len(file_cards) + shared_capacity
    if available_total < remaining_needed:
        raise ConflictError(
            detail=(
                "Insufficient digital stock for the requested product: "
                f"requested {remaining_needed}, but only "
                f"{available_total} available"
            )
        )

    # 5. Sufficiency guaranteed — mutate every locked card now.
    allocated: list[DigitalCard] = []
    for card in [*unique_cards, *file_cards]:
        card.status = DigitalCardStatus.DELIVERED
        card.assigned_order_id = order_id
        card.used_count += 1
        card.used_at = now
        allocated.append(card)

    for card in shared_cards:
        if remaining_needed <= 0:
            break
        available_slots = card.max_uses - card.used_count
        slots_to_take = min(available_slots, remaining_needed)

        card.used_count += slots_to_take
        card.assigned_order_id = order_id
        card.used_at = now
        if card.used_count >= card.max_uses:
            card.status = DigitalCardStatus.DELIVERED

        allocated.append(card)
        remaining_needed -= slots_to_take

    await db.flush()
    await logger.ainfo(
        "digital_cards_allocated",
        order_id=str(order_id),
        product_id=str(product_id),
        allocated_count=len(allocated),
    )
    return allocated


async def has_delivered_cards(
    db: AsyncSession,
    order_id: uuid.UUID,
) -> bool:
    """Whether the order already handed out any digital goods.

    Guards ask this question, not "give me the PINs" — decrypting to answer it
    means a card whose ciphertext cannot be decrypted (a rotated or missing
    encryption key) turns a *refusal* into a 500 before the guard ever runs.
    """
    stmt = select(func.count()).select_from(DigitalCard).where(
        DigitalCard.assigned_order_id == order_id,
        DigitalCard.status == DigitalCardStatus.DELIVERED,
    )
    return (await db.execute(stmt)).scalar_one() > 0


async def get_delivered_cards_for_order(
    db: AsyncSession,
    order_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Fetch and decrypt PINs for cards assigned to an order (customer view)."""
    stmt = (
        select(DigitalCard)
        .where(DigitalCard.assigned_order_id == order_id)
        .order_by(DigitalCard.created_at.asc())
    )
    cards = list((await db.execute(stmt)).scalars().all())

    result = []
    for card in cards:
        decrypted = decrypt_pin(card.pin_ciphertext)
        if card.serial_ciphertext:
            serial = decrypt_pin(card.serial_ciphertext)
        else:
            serial = card.serial_number or ""  # legacy rows (NULL after migration)
        file_url: str | None = None
        if card.delivery_type == DigitalDeliveryType.FILE and card.file_path:
            # P0.6: never expose the raw storage path — files are served
            # through an authenticated, ownership-checked, expiring endpoint.
            file_url = f"/api/v1/inventory/digital/cards/{card.id}/file"
        result.append(
            {
                "id": card.id,
                "serial_number": serial,
                "pin": decrypted,
                "delivery_type": card.delivery_type,
                "file_download_url": file_url,
                "delivered_at": card.used_at,
                "reading_at": card.reading_at,
            }
        )
    return result


async def mark_card_viewed(
    db: AsyncSession,
    card_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> DigitalCard:
    """Record timestamp when customer first views the decrypted PIN (legal evidence).

    When ``user_id`` is supplied the card must belong to an order owned by
    that user, otherwise the card is reported as not found.
    """
    card = await db.get(DigitalCard, card_id, with_for_update=True)
    if card is None:
        raise NotFoundError(resource="DigitalCard", detail=f"Card {card_id} not found")

    if user_id is not None:
        from app.modules.orders.domain.models import Order

        order = (
            await db.get(Order, card.assigned_order_id)
            if card.assigned_order_id is not None
            else None
        )
        if order is None or order.user_id != user_id:
            raise NotFoundError(resource="DigitalCard", detail=f"Card {card_id} not found")

    if card.reading_at is None:
        card.reading_at = datetime.now(UTC)
        await db.flush()
        await logger.ainfo(
            "digital_card_read",
            card_id=str(card_id),
            at=card.reading_at.isoformat(),
        )

    return card


async def add_single_card(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    pin: str,
    serial_number: str | None = None,
    delivery_type: DigitalDeliveryType = DigitalDeliveryType.UNIQUE,
    max_uses: int = 1,
    expire_at: datetime | None = None,
    file_path: str | None = None,
) -> DigitalCard:
    """Add one card to inventory with hash, AES-256-GCM encryption, and
    duplicate detection (Karta card_hash / card_encrypt).

    The plaintext PIN is never persisted and never logged; only its
    ciphertext and SHA-256 hash are stored. A duplicate pin/serial pair is
    rejected both by the pre-check and by the ``uq_digital_cards_card_hash``
    unique constraint as the concurrency backstop (P1.2).
    """
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    from app.modules.catalog.domain.models import Product
    from app.modules.inventory.application.crypto_service import (
        compute_card_hash,
        encrypt_pin,
    )

    clean_pin = pin.strip()
    if not clean_pin:
        raise ValidationError("متن کد/پین الزامی است")

    product = await db.get(Product, product_id)
    if product is None:
        raise NotFoundError(resource="Product", detail=f"Product {product_id} not found")

    if delivery_type == DigitalDeliveryType.SHARED and max_uses < 2:
        raise ValidationError("برای اکانت اشتراکی، سقف استفاده باید بیش از ۱ باشد")
    if delivery_type == DigitalDeliveryType.FILE and not file_path:
        raise ValidationError("برای محصول فایلی، مسیر فایل الزامی است")

    clean_serial = serial_number.strip() if serial_number else None
    card_hash = compute_card_hash(clean_pin, clean_serial)

    duplicate_stmt = select(func.count()).select_from(DigitalCard).where(
        DigitalCard.card_hash == card_hash
    )
    if (await db.execute(duplicate_stmt)).scalar_one() > 0:
        raise ConflictError(detail="این کد قبلاً در انبار ثبت شده است (کد تکراری)")

    card = DigitalCard(
        product_id=product_id,
        delivery_type=delivery_type,
        serial_ciphertext=encrypt_pin(clean_serial) if clean_serial else None,
        pin_ciphertext=encrypt_pin(clean_pin),
        card_hash=card_hash,
        status=DigitalCardStatus.AVAILABLE,
        max_uses=max_uses,
        expire_at=expire_at,
        file_path=file_path,
    )
    db.add(card)
    try:
        async with db.begin_nested():
            await db.flush()
    except SAIntegrityError as exc:
        raise ConflictError(detail="این کد قبلاً در انبار ثبت شده است (کد تکراری)") from exc

    await logger.ainfo(
        "digital_card_added",
        card_id=str(card.id),
        product_id=str(product_id),
        delivery_type=delivery_type.value,
    )
    return card


async def get_card_file_for_owner(
    db: AsyncSession,
    card_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[DigitalCard, str]:
    """Resolve a file-type card for authenticated download (Karta file_to_cards).

    Mirrors the legacy ``Cards::download`` guards: logged-in buyer, order
    ownership, file-delivery type, and expiry — the raw path never leaves
    the server (P0.6).
    """
    from pathlib import Path

    from app.modules.orders.domain.models import Order, OrderStatus

    card = await db.get(DigitalCard, card_id)
    if card is None:
        raise NotFoundError(resource="DigitalCard", detail=f"Card {card_id} not found")

    order = (
        await db.get(Order, card.assigned_order_id)
        if card.assigned_order_id is not None
        else None
    )
    if order is None or order.user_id != user_id:
        raise NotFoundError(resource="DigitalCard", detail=f"Card {card_id} not found")

    if order.status not in (OrderStatus.CONFIRMED, OrderStatus.COMPLETED):
        raise ConflictError(detail="سفارش هنوز در وضعیت قابل تحویل نیست")

    if card.delivery_type != DigitalDeliveryType.FILE or not card.file_path:
        raise NotFoundError(resource="DigitalCard", detail="این کارت فایل دانلودی ندارد")

    now = datetime.now(UTC)
    if card.expire_at is not None and card.expire_at <= now:
        raise ConflictError(detail="لینک دانلود این فایل منقضی شده است")

    resolved = Path(card.file_path)
    # ASYNC240: a single stat() on a local file is effectively non-blocking;
    # offloading it to a thread costs more than it saves here.
    is_file = await asyncio.to_thread(resolved.is_file)
    if not is_file:
        logger.error("digital_file_missing_on_disk", card_id=str(card_id))
        raise NotFoundError(resource="DigitalCard", detail="فایل روی سرور یافت نشد")

    await logger.ainfo(
        "digital_file_downloaded",
        card_id=str(card_id),
        order_id=str(order.id),
        user_id=str(user_id),
    )
    return card, str(resolved)


async def add_file_cards(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    file_path: str,
    copies: int = 1,
    expire_at: datetime | None = None,
) -> list[DigitalCard]:
    """Stock N sellable copies of one uploaded file asset (Karta file cards).

    Every copy is an independent card row pointing at the same asset path,
    consumed by allocation exactly like a PIN card; the embedded "PIN" is a
    random license reference so the row satisfies the encrypted-payload
    contract and duplicate detection without any operator input.
    """
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    from app.modules.catalog.domain.models import Product

    if copies < 1 or copies > 1000:
        raise ValidationError("تعداد نسخه‌های فایل باید بین ۱ تا ۱۰۰۰ باشد")

    product = await db.get(Product, product_id)
    if product is None:
        raise NotFoundError(resource="Product", detail=f"Product {product_id} not found")

    from app.modules.inventory.application.crypto_service import compute_card_hash

    cards: list[DigitalCard] = []
    for _ in range(copies):
        license_ref = f"FILE-{uuid.uuid4().hex}"
        cards.append(
            DigitalCard(
                product_id=product_id,
                delivery_type=DigitalDeliveryType.FILE,
                pin_ciphertext=encrypt_pin(license_ref),
                card_hash=compute_card_hash(license_ref),
                status=DigitalCardStatus.AVAILABLE,
                max_uses=1,
                file_path=file_path,
                expire_at=expire_at,
            )
        )

    try:
        async with db.begin_nested():
            db.add_all(cards)
            await db.flush()
    except SAIntegrityError as exc:
        raise ConflictError(detail="خطا در ثبت نسخه‌های فایل (تکراری)") from exc

    await logger.ainfo(
        "digital_file_cards_added",
        product_id=str(product_id),
        copies=copies,
        asset=str(file_path),
    )
    return cards


async def reencrypt_all_cards(db: AsyncSession, *, batch_size: int = 500) -> dict[str, Any]:
    """Key-rotation sweep: re-encrypt every stored payload with the active key.

    Decryption transparently accepts ``DIGITAL_CARDS_PREVIOUS_KEYS``; after
    rotating the active key this endpoint moves pin and serial payloads onto
    it batch by batch. Payloads that cannot be decrypted with any configured
    key are reported, never silently skipped.
    """
    from sqlalchemy import select as sa_select

    stmt = sa_select(DigitalCard.id, DigitalCard.pin_ciphertext, DigitalCard.serial_ciphertext)
    rows = (await db.execute(stmt)).all()

    reencrypted = 0
    already_current = 0
    failures: list[str] = []

    for row in rows:
        try:
            new_pin = encrypt_pin(decrypt_pin(row.pin_ciphertext))
            new_serial = None
            if row.serial_ciphertext:
                new_serial = encrypt_pin(decrypt_pin(row.serial_ciphertext))
        except ValueError:
            failures.append(str(row.id))
            continue

        if new_pin != row.pin_ciphertext or (
            row.serial_ciphertext is not None and new_serial != row.serial_ciphertext
        ):
            card = await db.get(DigitalCard, row.id, with_for_update=True)
            if card is None:
                failures.append(str(row.id))
                continue
            card.pin_ciphertext = new_pin
            if new_serial is not None:
                card.serial_ciphertext = new_serial
            reencrypted += 1
        else:
            already_current += 1

        if (reencrypted + already_current) % batch_size == 0:
            await db.flush()

    await db.flush()
    await logger.ainfo(
        "digital_cards_reencrypted",
        reencrypted=reencrypted,
        already_current=already_current,
        failures=len(failures),
    )
    return {
        "reencrypted": reencrypted,
        "already_current": already_current,
        "failed_ids": failures,
    }
