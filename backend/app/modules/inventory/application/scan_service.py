"""Barcode scanning: resolve a scanned code to a variant.

ERP benchmark gap analysis (feature #26 Barcode/scanning, P1). The
``ProductVariant.barcode`` column already existed but nothing ever read it —
a barcode you cannot look up is a field, not a feature.

Scope, deliberately narrow: this module **resolves codes and builds the line
list** a receiving or picking screen submits. It does not own the stock write
— that stays with ``physical_ops_service``, which already has the ledger,
the guards and the tests. A scanning feature that wrote stock itself would be
a second path to the same fact.

Pure helpers first, because the interesting rules are all normalisation:
scanners disagree about whitespace, leading zeros and the check-digit
separator, and getting those wrong is how a scan "finds nothing" for a
product that is plainly there.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.catalog.domain.models import Product, ProductStatus, ProductVariant
from app.modules.inventory.domain.models import InventoryItem

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Codes shorter than this are almost certainly a mis-scan or a keyboard
#: artefact rather than a real barcode (EAN-8 is the shortest common format).
MIN_BARCODE_LENGTH = 6

#: Hard cap on a scan list, mirroring the receiving flow's own limit. A
#: scanner stuck on a barcode can emit hundreds of repeats a second.
MAX_SCAN_LINES = 200


def normalise_barcode(raw: str) -> str:
    """Normalise a scanned code to the form stored in the database.

    Scanners are inconsistent in ways that all look like "not found":

    * trailing newlines and carriage returns (most USB scanners append one);
    * surrounding whitespace from a wedge or a manual paste;
    * Persian/Arabic-Indic digits, when someone types the number by hand.

    Hyphens and spaces *inside* the code are stripped too: the same EAN is
    printed with and without separators depending on the label stock.
    """
    if not raw:
        return ""
    # Persian/Arabic-Indic digits -> ASCII, so a hand-typed code matches.
    persian = "۰۱۲۳۴۵۶۷۸۹"
    arabic = "٠١٢٣٤٥٦٧٨٩"
    table = {ord(p): str(i) for i, p in enumerate(persian)}
    table.update({ord(a): str(i) for i, a in enumerate(arabic)})
    translated = raw.translate(table)

    return "".join(ch for ch in translated.strip() if ch not in " -\t\r\n")


def validate_scan_code(raw: str) -> str:
    """Normalise and validate one scan. Pure; raises on a code too short."""
    code = normalise_barcode(raw)
    if not code:
        raise ValidationError("بارکد خالی است", error_code="EMPTY_BARCODE")
    if len(code) < MIN_BARCODE_LENGTH:
        raise ValidationError(
            f"بارکد نامعتبر است (حداقل {MIN_BARCODE_LENGTH} نویسه)",
            error_code="BARCODE_TOO_SHORT",
        )
    return code


def merge_scans(codes: Iterable[str]) -> list[tuple[str, int]]:
    """Collapse repeated scans of the same code into ``[(code, count)]``.

    Order of first appearance is preserved: an operator scanning a shelf
    expects the receiving list to read in the order they walked it, not
    sorted by barcode.
    """
    counts: dict[str, int] = {}
    order: list[str] = []
    for raw in codes:
        code = normalise_barcode(raw)
        if not code:
            continue
        if code not in counts:
            counts[code] = 0
            order.append(code)
        counts[code] += 1
    return [(code, counts[code]) for code in order]


@dataclass
class ResolvedScan:
    """One resolved scan: the variant, its stock, and how many were scanned."""

    code: str
    quantity: int
    variant_id: uuid.UUID
    sku: str
    product_name: str
    #: ``ProductVariant.price`` verbatim -- the raw DB column, which is **Rial**
    #: (verified against live data: ``order_items.unit_price`` equals this column
    #: exactly). The catalog API divides by 10 on the way out, so a consumer of
    #: this raw value must do the same. The name is correct; leave it alone.
    price_rial: int
    on_hand: int = 0
    reserved: int = 0
    is_active: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def available(self) -> int:
        return max(0, self.on_hand - self.reserved)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "quantity": self.quantity,
            "variant_id": str(self.variant_id),
            "sku": self.sku,
            "product_name": self.product_name,
            "price_rial": self.price_rial,
            "on_hand": self.on_hand,
            "reserved": self.reserved,
            "available": self.available,
            "is_active": self.is_active,
            "warnings": self.warnings,
        }


async def resolve_barcode(
    db: AsyncSession,
    code: str,
    *,
    quantity: int = 1,
    warehouse_id: uuid.UUID | None = None,
) -> ResolvedScan:
    """Look one barcode up and attach its live stock position.

    A vendored product (``vendor_id`` set) is included: the catalogue serves
    marketplace items too, and refusing to resolve them would make scanning
    silently useless on half a real catalogue.
    """
    normalised = validate_scan_code(code)

    row = (
        await db.execute(
            select(ProductVariant, Product)
            .join(Product, ProductVariant.product_id == Product.id)
            .where(ProductVariant.barcode == normalised)
        )
    ).first()

    if row is None:
        raise NotFoundError(
            resource="ProductVariant",
            detail=f"بارکدی با کد «{normalised}» یافت نشد",
        )

    variant, product = row
    warnings: list[str] = []

    if not variant.is_active:
        warnings.append("این گونه غیرفعال است")
    if product.status != ProductStatus.ACTIVE:
        warnings.append("محصول در وضعیت فعال نیست")

    # Stock is per (variant, warehouse), so a variant held in three warehouses
    # has three rows. The scanner is standing in one of them; summing across
    # all of them would tell a picker they can reach stock that is in another
    # city. The warehouse is therefore a required argument, not a filter.
    item_stmt = select(InventoryItem).where(InventoryItem.variant_id == variant.id)
    if warehouse_id is not None:
        item_stmt = item_stmt.where(InventoryItem.warehouse_id == warehouse_id)
    items = (await db.execute(item_stmt)).scalars().all()

    if not items and warehouse_id is not None:
        warnings.append("این کالا در این انبار موجودی ثبت‌شده ندارد")

    on_hand = sum(int(i.available) for i in items)
    # ``reserved`` on the row is the live reservation count the inventory
    # service maintains; reading it directly beats summing reservation rows
    # (which would miss holds taken through other paths).
    reserved = sum(int(i.reserved) for i in items)

    return ResolvedScan(
        code=normalised,
        quantity=quantity,
        variant_id=variant.id,
        sku=variant.sku,
        product_name=product.name,
        price_rial=int(variant.price),
        on_hand=on_hand,
        reserved=reserved,
        is_active=variant.is_active,
        warnings=warnings,
    )


async def resolve_scan_batch(
    db: AsyncSession,
    codes: Iterable[str],
    *,
    warehouse_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Resolve a whole scan session, reporting per-code failures.

    A session is not rejected because one code is unknown: a receiving
    operator who scans 40 boxes and mistypes one needs the other 39, plus a
    clear note of which one failed. Failing the batch would lose the good
    work and teach them to scan nothing.
    """
    merged = merge_scans(codes)
    if len(merged) > MAX_SCAN_LINES:
        raise ValidationError(
            f"تعداد اسکن‌ها بیش از حد مجاز است (حداکثر {MAX_SCAN_LINES})",
            error_code="TOO_MANY_SCANS",
        )

    resolved: list[ResolvedScan] = []
    unresolved: list[dict[str, str]] = []

    for code, quantity in merged:
        try:
            resolved.append(
                await resolve_barcode(
                    db, code, quantity=quantity, warehouse_id=warehouse_id
                )
            )
        except (NotFoundError, ValidationError) as exc:
            unresolved.append(
                {
                    "code": code,
                    "reason": getattr(exc, "detail", None) or str(exc),
                    "endpoint": getattr(exc, "error_code", None) or "NOT_FOUND",
                }
            )

    return {
        "resolved": [r.to_dict() for r in resolved],
        "unresolved": unresolved,
        "total_scanned": sum(q for _c, q in merged),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
    }


def build_receipt_lines(scans: list[ResolvedScan]) -> list[tuple[str, int]]:
    """The ``(variant_id, quantity)`` list ``physical_ops_service`` expects. Pure.

    This is the seam: scanning decides *what*, the physical-ops service owns
    *how the stock moves*. Keeping the conversion a pure function means the
    hand-off is testable without a database.
    """
    return [(str(scan.variant_id), scan.quantity) for scan in scans]